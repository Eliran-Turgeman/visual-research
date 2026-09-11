"""Offline diagnostics tests: no Manim, native tools, credentials or TTS required."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("installation_doctor", ROOT / "manim_lib" / "doctor.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)
p = d.production


def by_id(report):
    return {check["id"]: check for check in report["checks"]}


@pytest.fixture
def healthy(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("MANIM_", "OPENAI_", "OPENROUTER_", "AZURE_")):
            monkeypatch.delenv(name)
    imported = []
    monkeypatch.setattr(p, "check_module", lambda module, provider, **kw: imported.append((module, provider, kw)))
    monkeypatch.setattr(p, "find_ffmpeg", lambda: "local-ffmpeg")
    monkeypatch.setattr(p, "_checked", lambda *a, **kw: SimpleNamespace(stdout="ffmpeg version fixture\n"))
    monkeypatch.setattr(p.shutil, "which", lambda _: None)
    monkeypatch.setattr(d.importlib.metadata, "version", lambda _: "1.2.3")
    return imported


def test_default_silent_ignores_provider_environment_and_keys(healthy):
    report = d.diagnose(environ={
        "MANIM_TTS_PROVIDER": "azure", "MANIM_QUALITY": "invalid",
        "OPENAI_API_KEY": "secret", "OPENROUTER_API_KEY": "secret",
        "AZURE_SUBSCRIPTION_KEY": "secret", "AZURE_TTS_SPEED": "invalid",
    })
    assert report["ok"]
    assert report["provider"] == "none"
    assert [module for module, _, _ in healthy] == ["manim", "av"]
    assert all(options == {"isolated": True} for _, _, options in healthy)
    checks = by_id(report)
    assert checks["credentials"]["status"] == "skipped"
    assert checks["tool:latex"]["status"] == checks["tool:dvisvgm"]["status"] == "skipped"
    assert "secret" not in json.dumps(report)


@pytest.mark.parametrize("provider", p.PROVIDERS)
def test_only_selected_provider_requirements_are_checked(provider, healthy):
    env = {name: "offline-test-value" for name in p.CREDENTIALS.get(provider, ())}
    report = d.diagnose(provider=provider, environ=env)
    assert report["ok"]
    assert [module for module, _, _ in healthy] == list(p.required_modules(provider))
    credential_ids = [item["id"] for item in report["checks"] if item["id"].startswith("credential:")]
    assert credential_ids == [f"credential:{name}" for name in p.CREDENTIALS.get(provider, ())]
    assert "offline-test-value" not in json.dumps(report)


def test_collects_all_independent_errors_and_redacts_exceptions(healthy, monkeypatch, capsys):
    def fail(*args, **kwargs):
        print("exception-secret")
        print("stderr-secret", file=sys.stderr)
        raise OSError("exception-secret DLL failed")

    monkeypatch.setattr(p, "check_module", fail)
    monkeypatch.setattr(p, "find_ffmpeg", fail)
    report = d.diagnose(provider="azure", require_tex=True, environ={})
    checks = by_id(report)
    for identifier in (
        "module:manim", "module:av", "module:manim_voiceover",
        "module:azure.cognitiveservices.speech", "ffmpeg", "tool:latex",
        "tool:dvisvgm", "credential:AZURE_SUBSCRIPTION_KEY", "credential:AZURE_SERVICE_REGION",
    ):
        assert checks[identifier]["status"] == "error"
        assert checks[identifier]["remediation"]
    assert not report["ok"]
    assert "exception-secret" not in json.dumps(report)
    assert "stderr-secret" not in json.dumps(report)
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("version,supported", [
    ((3, 10, 99), False), ((3, 11, 0), True), ((3, 12, 0), True),
    ((3, 13, 9), True), ((3, 14, 0), False), ((4, 0, 0), False),
])
def test_python_version_boundaries(version, supported, healthy, monkeypatch):
    monkeypatch.setattr(p.sys, "version_info", version)
    report = d.diagnose(environ={})
    assert report["ok"] is supported
    assert by_id(report)["python"]["status"] == ("pass" if supported else "error")


@pytest.mark.parametrize("system,command", [
    ("Windows", "winget install"), ("Darwin", "brew install"), ("Linux", "sudo apt-get"),
])
def test_platform_remediation_is_actionable(system, command, healthy, monkeypatch):
    def fail(*args, **kwargs):
        raise ImportError()

    monkeypatch.setattr(p, "check_module", fail)
    monkeypatch.setattr(p, "find_ffmpeg", fail)
    checks = by_id(d.diagnose(provider="external-gtts", require_tex=True, environ={}, system=system))
    assert command in " ".join(checks["module:manim"]["remediation"])
    assert command in " ".join(checks["ffmpeg"]["remediation"])
    assert command in " ".join(checks["tool:latex"]["remediation"])
    assert 'python -m pip install -e ".[voiceover-gtts]"' in " ".join(checks["module:gtts"]["remediation"])
    assert "imageio-ffmpeg" in " ".join(checks["ffmpeg"]["remediation"])
    if system == "Linux":
        assert "python3-dev" in " ".join(checks["module:manim"]["remediation"])


def test_unknown_platform_has_honest_generic_guidance():
    assert "system package manager" in d.installation_guidance("tex", "Other")[0]


@pytest.mark.parametrize("provider", ("openrouter", "openai", "azure"))
def test_skip_credentials_does_not_skip_provider_imports(provider, healthy):
    report = d.diagnose(provider=provider, skip_credentials=True, environ={})
    assert report["ok"]
    assert report["credential_policy"] == "skip"
    assert [module for module, _, _ in healthy] == list(p.required_modules(provider))
    for name in p.CREDENTIALS[provider]:
        check = by_id(report)[f"credential:{name}"]
        assert check["status"] == "skipped"
        assert "unverified" in check["message"]


def test_skip_credentials_still_fails_on_missing_provider(healthy, monkeypatch):
    def import_module(module, *args, **kwargs):
        if module == "openai":
            raise ImportError()

    monkeypatch.setattr(p, "check_module", import_module)
    report = d.diagnose(provider="openrouter", skip_credentials=True, environ={})
    assert not report["ok"]
    assert by_id(report)["module:openai"]["status"] == "error"
    assert by_id(report)["credential:OPENROUTER_API_KEY"]["status"] == "skipped"


@pytest.mark.parametrize("value", ("", "   ", "\n"))
def test_blank_credentials_fail(value, healthy):
    report = d.diagnose(provider="openai", environ={"OPENAI_API_KEY": value})
    assert by_id(report)["credential:OPENAI_API_KEY"]["status"] == "error"
    assert not report["ok"]


def test_selected_settings_reuse_production_validation_without_exposing_values(healthy):
    report = d.diagnose(
        provider="openrouter", skip_credentials=True,
        environ={"OPENROUTER_TTS_SPEED": "SECRET-bad-speed", "OPENROUTER_API_KEY": "SECRET-key"},
    )
    assert by_id(report)["settings"]["status"] == "error"
    assert not report["ok"]
    assert "SECRET" not in json.dumps(report)


@pytest.mark.parametrize("constructor", ("Tex", "MathTex", "SingleStringMathTex", "BulletedList", "Title"))
def test_direct_tex_scene_matches_render_preflight(constructor, healthy, tmp_path):
    scene = tmp_path / "scene.py"
    scene.write_text(f'raise AssertionError("must not execute")\n{constructor}("x")', encoding="utf-8")
    report = d.diagnose(scene=scene, environ={})
    assert by_id(report)["scene"]["status"] == "pass"
    assert by_id(report)["tool:latex"]["status"] == "error"
    assert not report["ok"]


def test_non_tex_scene_keeps_tex_optional(healthy, tmp_path):
    scene = tmp_path / "scene.py"
    scene.write_text('raise AssertionError("must not execute")\nText("x")', encoding="utf-8")
    assert d.diagnose(scene=scene, environ={})["ok"]
    assert not d.diagnose(scene=scene, require_tex=True, environ={})["ok"]


@pytest.mark.parametrize("source,requires_tex", [
    ('# MathTex("x")\nText("Use Tex(x)")', False),
    ('"""Tex("x")"""\nText("x")', False),
    ('from manim import MathTex as Formula\nFormula("x")', True),
    ('import manim as m\nm.MathTex("x")', True),
    ('Text("x")', False),
])
def test_tex_detection_ignores_literals_and_understands_aliases(source, requires_tex, healthy, tmp_path):
    scene = tmp_path / "scene.py"
    scene.write_text(source, encoding="utf-8-sig")
    assert p.scene_requires_tex(scene) is requires_tex
    report = d.diagnose(scene=scene, environ={})
    assert (by_id(report)["tool:latex"]["status"] == "error") is requires_tex


@pytest.mark.parametrize("kind", ("missing", "directory", "extension", "encoding", "syntax"))
def test_bad_scene_is_error_without_exposing_path(kind, healthy, tmp_path):
    scene = tmp_path / "SECRET-scene.py"
    if kind == "directory":
        scene.mkdir()
    elif kind == "extension":
        scene = scene.with_suffix(".txt")
        scene.write_text("pass", encoding="utf-8")
    elif kind == "encoding":
        scene.write_bytes(b"\xff")
    elif kind == "syntax":
        scene.write_text("class :\n", encoding="utf-8")
    report = d.diagnose(scene=scene, require_tex=True, environ={})
    assert not report["ok"]
    assert by_id(report)["scene"]["status"] == "error"
    assert by_id(report)["tool:latex"]["status"] == "error"
    assert "SECRET-scene" not in json.dumps(report)


def test_required_tex_checks_both_installed_tools(healthy, monkeypatch):
    seen = []
    monkeypatch.setattr(p, "check_tex_tool", seen.append)
    report = d.diagnose(require_tex=True, environ={})
    assert seen == ["latex", "dvisvgm"]
    assert report["ok"]


@pytest.mark.parametrize("error", (ImportError, OSError, RuntimeError, ValueError))
def test_shared_in_process_import_detects_native_failures(error, monkeypatch):
    def broken(module):
        raise error("native DLL / SECRET")

    monkeypatch.setattr(p.importlib, "import_module", broken)
    with pytest.raises(p.RenderError, match="Cannot import av") as captured:
        p.check_module("av", "none")
    assert "SECRET" not in str(captured.value)


@pytest.mark.parametrize("failure", ("crash", "timeout", "missing-executable"))
def test_isolated_import_failures_are_errors_not_success(failure, monkeypatch):
    def run(command, **kwargs):
        assert command[0] == sys.executable
        assert command[-1] == "av"
        assert kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["timeout"] == 30
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 30)
        if failure == "missing-executable":
            raise FileNotFoundError("SECRET")
        return SimpleNamespace(returncode=86)

    monkeypatch.setattr(p.subprocess, "run", run)
    with pytest.raises(p.RenderError, match="Cannot import av"):
        p.check_module("av", "none", isolated=True)


def test_ffmpeg_system_preferred_without_loading_fallback(monkeypatch):
    monkeypatch.setattr(p.shutil, "which", lambda _: "native-ffmpeg")
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    assert p.find_ffmpeg() == "native-ffmpeg"


def test_ffmpeg_fallback_used_when_system_is_absent(monkeypatch):
    monkeypatch.setattr(p.shutil, "which", lambda _: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", SimpleNamespace(get_ffmpeg_exe=lambda: "bundled-ffmpeg"))
    assert p.find_ffmpeg() == "bundled-ffmpeg"


@pytest.mark.parametrize("failure", ("missing", "native", "no-binary"))
def test_ffmpeg_fallback_failures_are_actionable(failure, monkeypatch):
    monkeypatch.setattr(p.shutil, "which", lambda _: None)
    if failure == "missing":
        monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    else:
        def broken():
            raise (OSError if failure == "native" else RuntimeError)("SECRET")
        monkeypatch.setitem(sys.modules, "imageio_ffmpeg", SimpleNamespace(get_ffmpeg_exe=broken))
    with pytest.raises(p.RenderError, match="FFmpeg is required") as captured:
        p.find_ffmpeg()
    assert "SECRET" not in str(captured.value)


@pytest.mark.parametrize("output", ("", "\n", "not ffmpeg\n"))
def test_ffmpeg_empty_or_invalid_version_is_failure(output, healthy, monkeypatch):
    monkeypatch.setattr(p, "_checked", lambda *a, **kw: SimpleNamespace(stdout=output))
    assert by_id(d.diagnose(environ={}))["ffmpeg"]["status"] == "error"
    with pytest.raises(p.RenderError, match="version"):
        p.check_ffmpeg()


@pytest.mark.parametrize("failure", ("exit", "timeout", "missing"))
def test_shared_native_tool_execution_failures(failure, monkeypatch):
    def run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 30)
        if failure == "missing":
            raise OSError("SECRET")
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(p.subprocess, "run", run)
    with pytest.raises(p.RenderError) as captured:
        p._checked(["tool", "--version"], label="Tool preflight", timeout=30)
    assert "SECRET" not in str(captured.value)


def test_json_schema_determinism_and_exit_codes(healthy, capsys):
    assert d.main(["--json"]) == 0
    first = capsys.readouterr().out
    assert d.main(["--json"]) == 0
    assert capsys.readouterr().out == first
    report = json.loads(first)
    assert report["schema_version"] == 1
    assert report["ok"]
    assert all({"id", "status", "message", "remediation"} <= check.keys() for check in report["checks"])
    assert d.main(["--require-tex", "--json"]) == 1
    assert not json.loads(capsys.readouterr().out)["ok"]


def test_text_output_honestly_marks_skips_and_errors(healthy, capsys):
    assert d.main(["--provider", "azure", "--skip-credentials"]) == 0
    output = capsys.readouterr().out
    assert "[SKIPPED] credential:AZURE_SUBSCRIPTION_KEY" in output
    assert "unverified" in output
    assert d.main(["--require-tex"]) == 1
    output = capsys.readouterr().out
    assert "[ERROR] tool:latex" in output
    assert "Fix:" in output
    assert "Installation checks failed." in output


def cli(tmp_path, *arguments, env=None):
    environ = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("MANIM_", "OPENAI_", "OPENROUTER_", "AZURE_"))
    }
    environ.update(PATH="", PYTHONPATH=str(tmp_path))
    environ.update(env or {})
    return subprocess.run(
        [sys.executable, "-S", str(ROOT / "scripts" / "doctor.py"), *arguments],
        cwd=tmp_path, env=environ, capture_output=True, text=True, timeout=60,
    )


def test_cli_help_is_stdlib_only(tmp_path):
    result = cli(tmp_path, "--help")
    assert result.returncode == 0
    assert "--skip-credentials" in result.stdout
    assert "default: none" in result.stdout
    assert not result.stderr


def test_cli_missing_modules_and_tools_produces_failed_json(tmp_path):
    result = cli(tmp_path, "--json")
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert not report["ok"]
    checks = by_id(report)
    for identifier in ("module:manim", "module:av", "ffmpeg"):
        assert checks[identifier]["status"] == "error"
        assert checks[identifier]["remediation"]
    assert checks["credentials"]["status"] == "skipped"
    assert not result.stderr


@pytest.mark.parametrize("version", ((3, 10, 0), (3, 14, 0)))
def test_cli_unsupported_python_is_failed_json_in_stdlib_isolation(version, tmp_path):
    bootstrap = (
        "import runpy, sys\n"
        f"sys.version_info = {version!r}\n"
        "def forbid_package_import(event, args):\n"
        "    if event == 'import' and args[0].split('.')[0] == 'manim_lib':\n"
        "        raise AssertionError('Doctor must not import eager package exports')\n"
        "sys.addaudithook(forbid_package_import)\n"
        "sys.argv = sys.argv[1:]\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", bootstrap, str(ROOT / "scripts" / "doctor.py"), "--json"],
        cwd=tmp_path, env={**os.environ, "PATH": "", "PYTHONPATH": str(tmp_path)},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert not report["ok"]
    check = by_id(report)["python"]
    assert check["status"] == "error"
    assert "unsupported" in check["message"] and ">=3.11,<3.14" in check["message"]
    assert check["remediation"]
    assert not result.stderr


@pytest.mark.parametrize("arguments", [
    ("--provider", "SECRET-unknown"), ("--scene",), ("--unknown-SECRET",),
])
def test_cli_bad_arguments_are_failed_json_not_tracebacks(arguments, tmp_path):
    result = cli(tmp_path, *arguments, "--json")
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert not report["ok"]
    assert report["checks"][0]["id"] == "arguments"
    assert "SECRET" not in result.stdout
    assert not result.stderr


@pytest.mark.parametrize("failure", ("exception", "crash"))
def test_cli_native_import_failure_output_cannot_leak_secrets(failure, tmp_path):
    ending = "raise OSError(os.environ['OPENAI_API_KEY'])" if failure == "exception" else "os._exit(86)"
    (tmp_path / "manim.py").write_text(
        "import os, sys\n"
        "assert 'manim_lib' not in sys.modules\n"
        "print(os.environ['OPENAI_API_KEY'], flush=True)\n"
        "os.write(2, os.environ['OPENAI_API_KEY'].encode())\n"
        f"{ending}\n",
        encoding="utf-8",
    )
    result = cli(tmp_path, "--json", env={"OPENAI_API_KEY": "SECRET-native-output"})
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert by_id(report)["module:manim"]["status"] == "error"
    assert "SECRET" not in result.stdout + result.stderr
    assert report["provider"] == "none"


def test_cli_success_and_skipped_credentials_offline(tmp_path):
    for module in ("manim", "av", "manim_voiceover", "openai"):
        (tmp_path / f"{module}.py").write_text(
            "import os, sys\nassert 'manim_lib' not in sys.modules\n"
            "print('SECRET-successful-import', flush=True)\n"
            "os.write(2, b'SECRET-native-stderr')\n",
            encoding="utf-8",
        )
    # Emulate the bundled executable without requiring a platform-native test binary.
    (tmp_path / "imageio_ffmpeg.py").write_text(
        "import subprocess\nfrom types import SimpleNamespace\n"
        "_run = subprocess.run\n"
        "def run(command, **kwargs):\n"
        "    if command == ['offline-ffmpeg', '-version']:\n"
        "        return SimpleNamespace(returncode=0, stdout='ffmpeg version fixture\\n')\n"
        "    return _run(command, **kwargs)\n"
        "subprocess.run = run\n"
        "def get_ffmpeg_exe():\n    return 'offline-ffmpeg'\n",
        encoding="utf-8",
    )
    result = cli(tmp_path, "--provider", "openrouter", "--skip-credentials", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr
    assert "SECRET" not in result.stdout
    report = json.loads(result.stdout)
    assert report["ok"]
    checks = by_id(report)
    assert checks["module:openai"]["status"] == "pass"
    assert checks["credential:OPENROUTER_API_KEY"]["status"] == "skipped"
    result = cli(tmp_path, "--provider", "openrouter", "--json")
    assert result.returncode == 1
    assert "SECRET" not in result.stdout
    assert by_id(json.loads(result.stdout))["credential:OPENROUTER_API_KEY"]["status"] == "error"
    assert not result.stderr
