"""Offline profile, wrapper and artifact integrity tests; never call live TTS."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from manim_lib import production as p


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("MANIM_", "OPENROUTER_", "OPENAI_", "AZURE_")):
            monkeypatch.delenv(name)


def test_draft_never_chooses_paid_provider_from_credentials():
    settings = p.resolve_settings(environ={
        "OPENROUTER_API_KEY": "do-not-serialize",
        "OPENAI_API_KEY": "also-secret",
    })
    assert settings == {"quality": "-ql", "provider": "none"}
    assert p.resolve_settings(environ={}) == settings


@pytest.mark.parametrize("env,provider", [({}, None), ({}, "none"), ({"MANIM_TTS_PROVIDER": "none"}, None)])
def test_production_requires_explicit_non_silent_provider(env, provider):
    with pytest.raises(p.RenderError, match="explicit non-silent"):
        p.resolve_settings(profile="production", provider=provider, environ=env)


@pytest.mark.parametrize("provider", p.PROVIDERS[1:])
def test_provider_alternatives_and_profile_quality(provider):
    settings = p.resolve_settings(profile="production", provider=provider, environ={})
    assert settings["provider"] == provider
    assert settings["quality"] == "-qh"
    assert p.resolve_settings(environ={"MANIM_TTS_PROVIDER": provider})["provider"] == provider


def test_quality_precedence_and_validation():
    assert p.resolve_settings(environ={"MANIM_QUALITY": "-qk"})["quality"] == "-qk"
    assert p.resolve_settings(quality="-qm", environ={"MANIM_QUALITY": "-qk"})["quality"] == "-qm"
    with pytest.raises(p.RenderError, match="Quality"):
        p.resolve_settings(quality="-ql --preview")


def test_configuration_allowlist():
    settings = p.resolve_settings(
        provider="openrouter", voice="en-US-Test", speed=1.1,
        style="cheerful", style_degree=0.8,
        environ={"OPENROUTER_TTS_MODEL": "model/voice", "OPENROUTER_API_KEY": "secret"},
    )
    assert settings == {
        "quality": "-ql", "provider": "openrouter", "model": "model/voice",
        "voice": "en-US-Test", "speed": 1.1, "style": "cheerful", "style_degree": 0.8,
    }
    assert "secret" not in json.dumps(settings)


@pytest.mark.parametrize("kwargs", [
    {"provider": "gtts", "voice": "alloy"},
    {"provider": "openai", "style": "cheerful"},
    {"provider": "openrouter", "speed": "nan"},
    {"provider": "openrouter", "speed": "fast"},
    {"provider": "openrouter", "speed": 3},
    {"provider": "openai", "speed": 5},
    {"provider": "openrouter", "style_degree": 1},
    {"provider": "openrouter", "style": "cheerful", "style_degree": 3},
    {"provider": "azure", "voice": 'bad"xml'},
    {"provider": "unknown"},
    {"api_key": "secret"},
])
def test_invalid_settings_fail_before_synthesis(kwargs):
    with pytest.raises(p.RenderError):
        p.resolve_settings(environ={}, **kwargs)


@pytest.mark.parametrize("provider,missing", [
    ("openrouter", "OPENROUTER_API_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("azure", "AZURE_SUBSCRIPTION_KEY"),
])
def test_credentials_preflight_before_dependency_import(provider, missing, tmp_path, monkeypatch):
    source = tmp_path / "scene.py"
    source.write_text("pass", encoding="utf-8")
    monkeypatch.setattr(p.importlib, "import_module", lambda _: pytest.fail("imports before credentials"))
    with pytest.raises(p.RenderError, match=missing):
        p.preflight(source, p.resolve_settings(provider=provider), environ={})


def test_azure_requires_region(tmp_path, monkeypatch):
    source = tmp_path / "scene.py"
    source.write_text("pass", encoding="utf-8")
    with pytest.raises(p.RenderError, match="AZURE_SERVICE_REGION"):
        p.preflight(source, p.resolve_settings(provider="azure"), environ={"AZURE_SUBSCRIPTION_KEY": "key"})


def test_preflight_missing_dependency_is_actionable(tmp_path, monkeypatch):
    source = tmp_path / "scene.py"
    source.write_text("pass", encoding="utf-8")
    def missing(_):
        raise ImportError("dependency")
    monkeypatch.setattr(p.importlib, "import_module", missing)
    with pytest.raises(p.RenderError, match="pip install -e"):
        p.preflight(source, p.resolve_settings())


def test_ffmpeg_prefers_native_then_imageio(monkeypatch):
    import imageio_ffmpeg
    monkeypatch.setattr(p.shutil, "which", lambda _: "native-ffmpeg")
    monkeypatch.setattr(imageio_ffmpeg, "get_ffmpeg_exe", lambda: "imageio-ffmpeg")
    assert p.find_ffmpeg() == "native-ffmpeg"
    monkeypatch.setattr(p.shutil, "which", lambda _: None)
    assert p.find_ffmpeg() == "imageio-ffmpeg"


def test_native_tools_preflight(tmp_path, monkeypatch):
    source = tmp_path / "scene.py"
    source.write_text('MathTex("x")', encoding="utf-8")
    monkeypatch.setattr(p.importlib, "import_module", lambda _: None)
    monkeypatch.setattr(p, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(p, "_checked", lambda *a, **kw: SimpleNamespace(stdout="ffmpeg version test\n"))
    monkeypatch.setattr(p.shutil, "which", lambda _: None)
    with pytest.raises(p.RenderError, match="latex is required"):
        p.preflight(source, p.resolve_settings())


def timeline(run_id="run-test", duration=1.0):
    return {
        "schema_version": 1, "run_id": run_id, "scene_duration": duration,
        "blocks": [{"index": 0, "start": 0.0, "end": duration, "duration": duration,
                    "text": "Local narration", "beat_id": "worked-example"}],
        "events": [{"time": duration / 2, "label": "State changes", "beat_id": "worked-example"}],
    }


def test_timeline_identity_and_legacy_compatibility():
    legacy = timeline()
    for name in ("schema_version", "run_id", "events"):
        legacy.pop(name)
    assert p.validate_timeline(legacy) is legacy
    with pytest.raises(p.RenderError, match="run_id"):
        p.validate_timeline(legacy, run_id="new-run")
    assert p.validate_timeline(timeline(), run_id="run-test")


@pytest.mark.parametrize("change", [
    {"scene_duration": float("nan")}, {"scene_duration": 0}, {"events": [{"time": 2, "label": "late"}]},
    {"blocks": [{"index": 0, "start": 0, "end": 1, "duration": 2, "text": "wrong"}]},
    {"blocks": [{"index": 0, "start": -1, "end": 1, "text": "wrong"}]},
])
def test_timeline_rejects_invalid_timing(change):
    data = timeline()
    data.update(change)
    with pytest.raises(p.RenderError):
        p.validate_timeline(data)


@pytest.fixture
def local_video(tmp_path):
    ffmpeg = p.find_ffmpeg()
    def generate(name="video.mp4", audio=False):
        path = tmp_path / name
        command = [ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi",
                   "-i", "color=c=blue:s=64x64:r=15:d=1"]
        if audio:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1", str(path)]
        subprocess.run(command, check=True, capture_output=True)
        return path
    return generate


@pytest.mark.parametrize("audio", [False, True])
def test_validate_local_encoded_media(local_video, audio):
    path = local_video(audio=audio)
    result = p.validate_media(path, ffmpeg=p.find_ffmpeg(), expect_audio=audio, scene_duration=1)
    assert result["has_audio"] is audio
    assert result["duration"] == pytest.approx(1, abs=0.01)
    assert result["width"] == 64
    with pytest.raises(p.RenderError, match="duration"):
        p.validate_media(path, ffmpeg=p.find_ffmpeg(), expect_audio=audio, scene_duration=4)
    with pytest.raises(p.RenderError, match="stream"):
        p.validate_media(path, ffmpeg=p.find_ffmpeg(), expect_audio=not audio, scene_duration=1)


@pytest.mark.parametrize("content", [None, b"", b"not an mp4"])
def test_missing_empty_corrupt_video(tmp_path, content):
    path = tmp_path / "broken.mp4"
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(p.RenderError, match="missing|empty|corrupt"):
        p.validate_media(path, ffmpeg=p.find_ffmpeg(), expect_audio=False, scene_duration=1)


@pytest.fixture
def fake_render(tmp_path, monkeypatch, local_video):
    source = tmp_path / "source.py"
    source.write_text("class LocalScene: pass", encoding="utf-8")
    video = local_video("fixture.mp4")
    monkeypatch.setattr(p, "preflight", lambda *a, **kw: {"ffmpeg": p.find_ffmpeg(), "ffmpeg_version": "fixture ffmpeg"})
    monkeypatch.setattr(p, "source_snapshot", lambda *args: {"git_commit": "abc123", "dirty": False})
    original_checked = p._checked
    seen = {}
    def checked(command, *, label, **kwargs):
        if label != "Manim render":
            return original_checked(command, label=label, **kwargs)
        env = kwargs["env"]
        seen.update(command=command, env=env)
        path = Path(env["MANIM_TIMELINE_PATH"])
        path.write_text(json.dumps(timeline(env["MANIM_RUN_ID"])), encoding="utf-8")
        shutil.copyfile(video, path.parent / "video.mp4")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(p, "_checked", checked)
    return source, tmp_path / "runs", seen


def test_manifest_config_redaction_hashes_identity_and_metrics(fake_render, monkeypatch):
    source, output, seen = fake_render
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-credential-not-config")
    monkeypatch.setenv("UNRELATED_SECRET", "another-never-recorded")
    monkeypatch.setenv("OPENROUTER_TTS_STYLE", "stale-style")
    manifest_path = p.render(source, "LocalScene", output_dir=output, run_id="run-test", quality="-qm")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "rendered"
    assert manifest["profile"] == "draft"
    assert manifest["run_id"] == "run-test"
    assert manifest["settings"] == {"quality": "-qm", "provider": "none"}
    assert manifest["metrics"]["render_seconds"] > 0
    assert manifest["environment"]["python"]
    assert manifest["environment"]["manim"]
    assert manifest["source"]["git_commit"] == "abc123"
    assert "secret-credential" not in manifest_path.read_text()
    assert "another-never-recorded" not in manifest_path.read_text()
    assert "OPENROUTER_TTS_STYLE" not in seen["env"]
    assert seen["env"]["MANIM_TTS_PROVIDER"] == "none"
    assert seen["env"]["MANIM_RUN_ID"] == "run-test"
    assert seen["env"]["MANIM_TIMELINE_PATH"] == str(manifest_path.parent / "timeline.json")
    assert seen["command"][0] == sys.executable
    assert "-qm" in seen["command"]
    for name in ("video", "timeline"):
        artifact = manifest["artifacts"][name]
        assert artifact["sha256"] == hashlib.sha256((manifest_path.parent / artifact["path"]).read_bytes()).hexdigest()
    assert "accepted" not in manifest
    with pytest.raises(p.RenderError, match="already exists"):
        p.render(source, "LocalScene", output_dir=output, run_id="run-test")


@pytest.mark.parametrize("failure", ["missing-timeline", "stale-timeline", "missing-video", "nonzero"])
def test_failed_subprocess_or_artifacts_never_become_rendered(fake_render, monkeypatch, failure):
    source, output, _ = fake_render
    def checked(command, *, label, **kwargs):
        if failure == "nonzero":
            raise p.RenderError("Manim render exited with code 7.", 7)
        path = Path(kwargs["env"]["MANIM_TIMELINE_PATH"])
        if failure != "missing-timeline":
            run_id = "stale" if failure == "stale-timeline" else "run-test"
            path.write_text(json.dumps(timeline(run_id)), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(p, "_checked", checked)
    with pytest.raises(p.RenderError):
        p.render(source, "LocalScene", output_dir=output, run_id="run-test")
    manifest = json.loads((output / "run-test" / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["artifacts"] == {}
    assert manifest["metrics"]["render_seconds"] > 0


def test_checked_subprocess_preserves_failure_exit_code():
    with pytest.raises(p.RenderError) as exc:
        p._checked([sys.executable, "-c", "raise SystemExit(7)"], label="test")
    assert exc.value.exit_code == 7


def test_cli_parsing_and_exit_behavior(monkeypatch, tmp_path):
    seen = {}
    def render(**kwargs):
        seen.update(kwargs)
        return tmp_path / "manifest.json"
    monkeypatch.setattr(p, "render", render)
    assert p.main(["scene with spaces.py", "A", "--profile", "production", "--provider", "gtts", "--quality=-qm", "--source-file", "narration.txt"]) == 0
    assert seen["scene_file"] == Path("scene with spaces.py")
    assert seen["quality"] == "-qm"
    assert seen["profile"] == "production"
    assert seen["source_files"] == [Path("narration.txt")]
    def fail(**kwargs):
        raise p.RenderError("subprocess failed", 7)
    monkeypatch.setattr(p, "render", fail)
    assert p.main(["scene.py", "A"]) == 7


def test_powershell_wrapper_forwards_arguments_and_exit_codes(tmp_path):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        pytest.skip("PowerShell is not installed")
    recorder = tmp_path / "record.py"
    result = tmp_path / "args.json"
    recorder.write_text(
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['ARGUMENT_RECORD']).write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(7)\n", encoding="utf-8",
    )
    wrapper_dir = tmp_path / "scripts"
    wrapper_dir.mkdir()
    shutil.copyfile(p.ROOT / "scripts" / "render.ps1", wrapper_dir / "render.ps1")
    shutil.copyfile(recorder, wrapper_dir / "render.py")
    env = {**os.environ, "MANIM_PYTHON": sys.executable, "ARGUMENT_RECORD": str(result)}
    arguments = ["scene with spaces.py", "A", "--profile", "draft", "--quality=-qm"]
    completed = subprocess.run(
        [powershell, "-NoProfile", "-File", str(wrapper_dir / "render.ps1"), *arguments],
        env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 7, completed.stderr
    assert json.loads(result.read_text()) == arguments


def test_bash_wrapper_forwards_arguments_and_exit_codes(tmp_path):
    bash = shutil.which("bash")
    if os.name == "nt":
        git = shutil.which("git")
        candidate = Path(git).parents[1] / "bin" / "bash.exe" if git else None
        bash = str(candidate) if candidate and candidate.exists() else None
    if not bash:
        pytest.skip("A local Bash is not installed")
    wrapper = tmp_path / "render.sh"
    shutil.copyfile(p.ROOT / "scripts" / "render.sh", wrapper)
    (tmp_path / "render.py").write_text(
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['ARGUMENT_RECORD']).write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(7)\n", encoding="utf-8",
    )
    result = tmp_path / "args.json"
    env = {**os.environ, "MANIM_PYTHON": sys.executable, "ARGUMENT_RECORD": str(result)}
    arguments = ["scene with spaces.py", "A", "--provider", "none", "--quality=-qh"]
    completed = subprocess.run([bash, str(wrapper), *arguments], env=env, capture_output=True, text=True)
    assert completed.returncode == 7, completed.stderr
    assert json.loads(result.read_text()) == arguments


def test_ddtree_wrapper_uses_explicit_draft_and_preserves_silent_quality(tmp_path):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        pytest.skip("PowerShell is not installed")
    example_dir = tmp_path / "examples" / "ddtree_full"
    example_dir.mkdir(parents=True)
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    shutil.copyfile(p.ROOT / "examples" / "ddtree_full" / "render.ps1", example_dir / "render.ps1")
    shutil.copyfile(p.ROOT / "scripts" / "render.ps1", script_dir / "render.ps1")
    (script_dir / "render.py").write_text(
        "import json, os, pathlib, sys\n"
        "pathlib.Path(os.environ['ARGUMENT_RECORD']).write_text(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    result = tmp_path / "args.json"
    env = {**os.environ, "MANIM_PYTHON": sys.executable, "ARGUMENT_RECORD": str(result)}
    completed = subprocess.run(
        [powershell, "-NoProfile", "-File", str(example_dir / "render.ps1"), "-Quality", "-ql", "-Silent"],
        env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    arguments = json.loads(result.read_text())
    assert "--quality=-ql" in arguments
    assert arguments[arguments.index("--profile") + 1] == "draft"
    assert arguments[arguments.index("--provider") + 1] == "none"
    assert "--require-tex" in arguments


def test_real_silent_draft_smoke_is_run_bound_without_credentials(tmp_path, monkeypatch):
    source = tmp_path / "local_scene.py"
    source.write_text(
        "from manim import Circle, Create\n"
        "from manim_lib.narrated_scene import NarratedScene\n"
        "class LocalScene(NarratedScene):\n"
        "    def construct(self):\n"
        "        with self.narrate('One local draft.', beat_id='local'):\n"
        "            self.play(Create(Circle()), run_time=0.2)\n"
        "            self.record_visual_event('Circle appears')\n",
        encoding="utf-8",
    )
    # Even a present key must not change the silent profile. Never synthesize.
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-test-do-not-use")
    manifest_path = p.render(source, "LocalScene", output_dir=tmp_path / "runs", run_id="smoke")
    manifest = json.loads(manifest_path.read_text())
    data = json.loads((manifest_path.parent / "timeline.json").read_text())
    assert manifest["status"] == "rendered"
    assert manifest["settings"]["provider"] == "none"
    assert manifest["artifacts"]["video"]["has_audio"] is False
    assert data["run_id"] == "smoke"
    assert data["scene_duration"] >= 1.8 - 1 / 15
    assert data["blocks"][0]["beat_id"] == "local"
    assert data["events"][0]["beat_id"] == "local"


@pytest.mark.parametrize("provider", ["gtts", "external-gtts"])
def test_real_production_mux_uses_only_locally_generated_audio(tmp_path, provider):
    audio = tmp_path / "fixture.mp3"
    subprocess.run(
        [p.find_ffmpeg(), "-nostdin", "-v", "error", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", str(audio)],
        check=True, capture_output=True,
    )
    source = tmp_path / "local_audio_scene.py"
    source.write_text(
        "import shutil\n"
        "from types import SimpleNamespace\n"
        "import gtts\n"
        f"gtts.gTTS = lambda *args, **kwargs: SimpleNamespace(save=lambda path: shutil.copyfile({str(audio)!r}, path))\n"
        "from manim import Circle, Create\n"
        "from manim_lib.narrated_scene import NarratedScene\n"
        "class LocalAudioScene(NarratedScene):\n"
        "    def construct(self):\n"
        "        with self.narrate('Local fixture only.', beat_id='local-audio'):\n"
        "            self.play(Create(Circle()), run_time=0.2)\n"
        "            self.record_visual_event('Circle appears')\n",
        encoding="utf-8",
    )
    manifest_path = p.render(
        source, "LocalAudioScene", profile="production", provider=provider,
        quality="-ql", output_dir=tmp_path / "runs", run_id="local-audio",
    )
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "rendered"
    assert manifest["profile"] == "production"
    assert manifest["settings"]["provider"] == provider
    video = manifest["artifacts"]["video"]
    assert video["has_audio"]
    assert video["audio_duration"] > 0
    assert abs(video["audio_duration"] - video["duration"]) < 0.15
    assert list((manifest_path.parent / "audio").glob("*.mp3"))


def test_source_snapshot_tracks_imports_storyboards_and_declared_inputs(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    files = {
        "scene.py": "from imported import Example",
        "imported.py": "class Example: pass",
        "storyboard.md": "Worked example",
        "narration.txt": "Explain the mechanism",
        ".env": "PRIVATE_KEY=never-fingerprint",
        "credentials.bin": "never-fingerprint",
    }
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    external = tmp_path / "external_storyboard.json"
    external.write_text('{"beat":"worked"}', encoding="utf-8")
    monkeypatch.setattr(p, "ROOT", root)
    def git(command, **kwargs):
        output = "revision\n" if command[1] == "rev-parse" else (
            "\0".join([*files, "deleted.py"]) + "\0" if command[1] == "ls-files" else " M imported.py\n"
        )
        return SimpleNamespace(returncode=0, stdout=output)
    monkeypatch.setattr(p.subprocess, "run", git)
    snapshot = p.source_snapshot(root / "scene.py", (external,))
    assert snapshot["git_commit"] == "revision"
    assert snapshot["dirty"] is True
    assert snapshot["tracked_files_available"]
    entries = {entry["path"]: entry for entry in snapshot["files"]}
    assert entries["imported.py"]["sha256"] == hashlib.sha256(files["imported.py"].encode()).hexdigest()
    assert entries["storyboard.md"]["sha256"]
    assert entries["narration.txt"]["sha256"]
    assert entries[str(external)]["sha256"]
    assert entries["deleted.py"]["state"] == "missing"
    assert ".env" not in entries
    assert "credentials.bin" not in entries
    p._verify_source_snapshot(snapshot)
    (root / "imported.py").write_text("changed imported dependency", encoding="utf-8")
    with pytest.raises(p.RenderError, match="changed during rendering"):
        p._verify_source_snapshot(snapshot)


def test_source_snapshot_without_git_and_missing_declared_input(tmp_path, monkeypatch):
    source = tmp_path / "scene.py"
    source.write_text("pass", encoding="utf-8")
    monkeypatch.setattr(p.shutil, "which", lambda _: None)
    snapshot = p.source_snapshot(source)
    assert snapshot["git_commit"] is None
    assert snapshot["dirty"] is None
    assert not snapshot["tracked_files_available"]
    assert len(snapshot["files"]) == 1
    with pytest.raises(p.RenderError, match="Declared source"):
        p.source_snapshot(source, (tmp_path / "missing.md",))
    secret = tmp_path / ".env"
    secret.write_text("SECRET=do-not-fingerprint", encoding="utf-8")
    with pytest.raises(p.RenderError, match="allowlisted"):
        p.source_snapshot(source, (secret,))


def test_changed_source_during_render_fails_manifest(fake_render, monkeypatch):
    source, output, _ = fake_render
    snapshot = {
        "root": str(source.parent),
        "files": [{"path": source.name, "sha256": "different-content"}],
    }
    monkeypatch.setattr(p, "source_snapshot", lambda *args: snapshot)
    with pytest.raises(p.RenderError, match="changed during rendering"):
        p.render(source, "LocalScene", output_dir=output, run_id="changed-input")
    manifest = json.loads((output / "changed-input" / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["artifacts"] == {}
