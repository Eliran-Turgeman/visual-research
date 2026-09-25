from array import array
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import urllib.error
import wave

import av
from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


narrate, frames, new_project = (load(name) for name in ("narrate", "frames", "new_project"))


def wav_file(path, *, silent=False, count=12000):
    values = array("h", (0 if silent else int(5000 * math.sin(i * .07)) for i in range(count)))
    if sys.byteorder == "big":
        values.byteswap()
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        stream.writeframes(values.tobytes())


def body_key(text):
    body = {**narrate.SETTINGS, "input": text}
    key = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return body, key


def cached_clip(cache, text):
    cache.mkdir(parents=True, exist_ok=True)
    body, key = body_key(text)
    mp3, wav, metadata = (cache / f"{key}.{ext}" for ext in ("mp3", "wav", "json"))
    mp3.write_bytes(b"test-existing-paid-mp3")
    wav_file(wav)
    metadata.write_text(json.dumps({
        "request": body, "generation_id": "generation-example",
        "mp3_sha256": narrate.digest(mp3), "wav_sha256": narrate.digest(wav),
    }), encoding="utf-8")
    return mp3, wav, metadata


@pytest.fixture
def storyboard(tmp_path):
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps([
        {"id": "a", "narration": "First operation.", "purpose": "Explain"},
        {"id": "b", "narration": "Second operation."},
    ]), encoding="utf-8")
    return path


def test_cache_only_never_calls_provider(storyboard, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-be-used")
    monkeypatch.setattr(narrate, "request_audio", lambda body: pytest.fail("Paid call"))
    assert narrate.main([str(storyboard)]) == 1
    assert not (storyboard.parent / "audio" / "manifest.json").exists()


def test_reuses_exact_cache_and_measures_audio(storyboard, monkeypatch):
    cache = storyboard.parent / "audio" / "cache"
    cached_clip(cache, "First operation.")
    cached_clip(cache, "Second operation.")
    monkeypatch.setattr(narrate, "request_audio", lambda body: pytest.fail("Paid call"))
    result = narrate.prepare(storyboard, cache.parent)
    assert set(result["beats"]) == {"a", "b"}
    assert result["beats"]["a"]["duration"] == .25
    assert result["beats"]["a"]["request"] == {**narrate.SETTINGS, "input": "First operation."}
    assert (cache.parent / result["beats"]["a"]["wav"]).is_file()
    assert narrate.prepare(storyboard, cache.parent, beat="a")["beats"] == result["beats"]


def test_generates_only_explicit_selected_beat(storyboard, monkeypatch):
    requests = []
    monkeypatch.setattr(narrate, "request_audio",
                        lambda body: (requests.append(body) or b"mp3" * 300, "generation-1"))

    def convert(command, **kwargs):
        wav_file(Path(command[-1]))
        assert command[command.index("-ar") + 1] == "48000"
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(narrate.subprocess, "run", convert)
    output = storyboard.parent / "audio"
    result = narrate.prepare(storyboard, output, generate=True, beat="a")
    assert set(result["beats"]) == {"a"}
    assert len(requests) == 1
    narrate.prepare(storyboard, output, generate=True, beat="a")
    assert len(requests) == 1
    assert not list(output.rglob("*.part*"))


def test_conversion_failure_preserves_paid_audio_for_retry(storyboard, monkeypatch):
    requests = []
    monkeypatch.setattr(narrate, "request_audio",
                        lambda body: (requests.append(body) or b"mp3" * 300, "generation-1"))
    monkeypatch.setattr(narrate.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1, stderr="bad codec"))
    output = storyboard.parent / "audio"
    with pytest.raises(ValueError, match="conversion failed"):
        narrate.prepare(storyboard, output, generate=True, beat="a")
    assert len(list((output / "cache").glob("*.mp3"))) == 1

    def convert(command, **kwargs):
        wav_file(Path(command[-1]))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(narrate.subprocess, "run", convert)
    assert "a" in narrate.prepare(storyboard, output, beat="a")["beats"]
    assert len(requests) == 1


@pytest.mark.parametrize("which", ["mp3", "wav", "json"])
def test_altered_cache_never_triggers_paid_replacement(storyboard, monkeypatch, which):
    cache = storyboard.parent / "audio" / "cache"
    paths = cached_clip(cache, "First operation.")
    paths[("mp3", "wav", "json").index(which)].write_text("[]", encoding="utf-8")
    monkeypatch.setattr(narrate, "request_audio", lambda body: pytest.fail("Paid call"))
    with pytest.raises(ValueError, match="cache"):
        narrate.prepare(storyboard, cache.parent, generate=True, beat="a")


@pytest.mark.parametrize("payload", [
    [], {}, [{"id": "a"}], [{"id": 1, "narration": "text"}],
    [{"id": "a", "narration": " "}],
    [{"id": "a", "narration": "one"}, {"id": "a", "narration": "two"}],
])
def test_invalid_storyboard_does_not_create_audio(storyboard, payload):
    storyboard.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        narrate.prepare(storyboard, storyboard.parent / "audio", generate=True)
    assert not (storyboard.parent / "audio").exists()


def test_unknown_beat_is_an_error(storyboard):
    with pytest.raises(ValueError, match="Unknown beat"):
        narrate.prepare(storyboard, storyboard.parent / "audio", beat="missing")


@pytest.mark.parametrize("silent,count", [(True, 12000), (False, 0), (False, 100)])
def test_invalid_audio_is_not_success(tmp_path, silent, count):
    path = tmp_path / "clip.wav"
    wav_file(path, silent=silent, count=count)
    with pytest.raises(ValueError):
        narrate.audio_stats(path)


def test_api_errors_never_expose_secrets(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")

    def fail(request, **kwargs):
        assert request.get_header("Authorization") == "Bearer private-test-key"
        raise urllib.error.HTTPError(request.full_url, 401, "secret-provider-message",
                                     {}, io.BytesIO(b"private-test-key"))

    monkeypatch.setattr(narrate.urllib.request, "urlopen", fail)
    with pytest.raises(ValueError, match="HTTP 401") as error:
        narrate.request_audio({**narrate.SETTINGS, "input": "Hello"})
    assert "private-test-key" not in str(error.value)
    assert "secret-provider-message" not in str(error.value)


def test_missing_key_is_explicit(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is missing"):
        narrate.request_audio({})


def test_new_project_copies_only_skill_utilities_and_environment(tmp_path):
    destination = new_project.create(tmp_path / "new video")
    files = {path.relative_to(destination) for path in destination.rglob("*") if path.is_file()}
    assert files == {
        Path("pyproject.toml"), Path("uv.lock"), Path(".python-version"), Path(".gitignore"),
        Path("AGENTS.md"), Path("brief.md"), Path("scripts/narrate.py"), Path("scripts/frames.py"),
        Path(".github/skills/technical-manim-explainer/SKILL.md"),
        Path(".github/skills/technical-manim-explainer/MANIM_GUIDE.md"),
    }
    assert (destination / "uv.lock").read_bytes() == (ROOT / "uv.lock").read_bytes()
    assert "SKILL.md" in (destination / "AGENTS.md").read_text()
    for name in ("SKILL.md", "MANIM_GUIDE.md"):
        assert (destination / ".github" / "skills" / new_project.SKILL / name).read_bytes() == (
            ROOT / "skills" / new_project.SKILL / name
        ).read_bytes()
    brief = (destination / "brief.md").read_text()
    assert "concepts they already know" in brief
    assert "predict or explain" in brief
    assert "misconception" in brief
    assert "Familiar example" in brief
    assert "Broader task, bottleneck" in brief
    assert "silent draft" in brief


def test_new_project_preserves_custom_brief_bytes(tmp_path):
    source = tmp_path / "brief.md"
    source.write_bytes(b"\xef\xbb\xbf# A topic\r\n")
    destination = new_project.create(tmp_path / "native", source)
    assert (destination / "brief.md").read_bytes() == source.read_bytes()


def test_new_project_refuses_overwrite_and_repository_context(tmp_path):
    with pytest.raises(ValueError, match="already exists"):
        new_project.create(tmp_path)
    with pytest.raises(ValueError, match="outside this repository"):
        new_project.create(ROOT / "do-not-create")
    other = tmp_path / "other"
    other.mkdir()
    (other / ".git").write_text("gitdir: elsewhere")
    with pytest.raises(ValueError, match="Git checkouts"):
        new_project.create(other / "native")


def test_bad_brief_fails_before_export(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_bytes(b"\xff")
    with pytest.raises(ValueError):
        new_project.create(tmp_path / "native", brief)
    assert not (tmp_path / "native").exists()


def test_exporter_has_no_runtime_dependency(tmp_path):
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "scripts" / "new_project.py"), str(tmp_path / "native")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "video.mp4"
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=10)
        stream.width, stream.height, stream.pix_fmt = 160, 90, "yuv420p"
        for index in range(10):
            frame = av.VideoFrame.from_image(Image.new("RGB", (160, 90), (index * 20, 40, 80)))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def test_frames_include_endpoints_and_requested_times(video):
    output = video.parent / "review"
    result = frames.extract(video, output, [.2, .5])
    assert result["fps"] == 10
    assert (result["width"], result["height"]) == (160, 90)
    assert result["has_audio"] is False
    assert [sample["actual"] for sample in result["frames"]] == [0, .2, .5, .9]
    assert Image.open(output / result["contact_sheets"][0]).size == (1200, 500)
    assert (output / "frames.json").is_file()


def test_frames_default_to_eight_samples(video):
    assert len(frames.extract(video, video.parent / "review", [])["frames"]) == 8


@pytest.mark.parametrize("time", [-1, float("nan"), float("inf"), 1, 100])
def test_bad_frame_times_fail_before_output(video, time):
    output = video.parent / "review"
    with pytest.raises(ValueError):
        frames.extract(video, output, [time])
    assert not output.exists()


def test_frames_never_overwrite_a_review(video):
    with pytest.raises(ValueError, match="already exists"):
        frames.extract(video, video.parent, [])


def test_corrupt_video_reports_failure(tmp_path, capsys):
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"not a video")
    assert frames.main([str(path), "--output", str(tmp_path / "review")]) == 1
    assert "Frame extraction failed" in capsys.readouterr().err
