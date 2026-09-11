"""Offline regression tests for the real-render CI artifact gate."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "verify_installation_smoke", Path(__file__).with_name("verify_installation_smoke.py")
)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def test_accepts_base_only_environment(monkeypatch):
    def absent(_name):
        raise verifier.metadata.PackageNotFoundError

    monkeypatch.setattr(verifier.metadata, "version", absent)
    verifier.verify_base_environment()


@pytest.mark.parametrize("installed", verifier.OPTIONAL_DISTRIBUTIONS)
def test_rejects_preinstalled_optional_extras(monkeypatch, installed):
    def version(name):
        if name == installed:
            return "1.0"
        raise verifier.metadata.PackageNotFoundError

    monkeypatch.setattr(verifier.metadata, "version", version)
    with pytest.raises(ValueError, match="not base-only"):
        verifier.verify_base_environment()


@pytest.fixture
def smoke_run(tmp_path):
    run = tmp_path / "install-smoke"
    run.mkdir()
    (run / "video.mp4").write_bytes(b"unit-test-placeholder-not-a-real-video")
    timeline = {
        "run_id": run.name,
        "scene_duration": 1.8,
        "blocks": [{"beat_id": "installation"}],
        "events": [{"time": 0.3, "label": "Text is visible"}],
    }
    (run / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    artifacts = {
        name: {
            "path": filename,
            "sha256": hashlib.sha256((run / filename).read_bytes()).hexdigest(),
        }
        for name, filename in (("video", "video.mp4"), ("timeline", "timeline.json"))
    }
    artifacts["video"].update(
        has_audio=False, duration=1.8, frame_rate=15, width=854, height=480
    )
    manifest = {
        "status": "rendered",
        "run_id": run.name,
        "scene_name": "InstallationSmoke",
        "profile": "draft",
        "settings": {"provider": "none"},
        "artifacts": artifacts,
    }
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run, manifest


def test_matching_rendered_artifacts_pass(smoke_run):
    run, _ = smoke_run
    verifier.verify_run(run)


@pytest.mark.parametrize(
    "keys,value,message",
    [
        (("status",), "rendering", "not rendered"),
        (("run_id",), "other-run", "run IDs"),
        (("scene_name",), "OtherScene", "Wrong smoke scene"),
        (("profile",), "production", "silent draft"),
        (("settings", "provider"), "openrouter", "silent draft"),
        (("artifacts", "video", "path"), "other.mp4", "unexpected video"),
        (("artifacts", "video", "sha256"), "wrong", "video hash"),
        (("artifacts", "timeline", "sha256"), "wrong", "timeline hash"),
        (("artifacts", "video", "has_audio"), True, "contains audio"),
        (("artifacts", "video", "duration"), 4, "durations"),
        (("artifacts", "video", "duration"), 0, "invalid timing"),
        (("artifacts", "video", "frame_rate"), 0, "invalid timing"),
        (("artifacts", "video", "width"), 0, "dimensions"),
    ],
)
def test_rejects_wrong_or_stale_manifest(smoke_run, keys, value, message):
    run, original = smoke_run
    manifest = copy.deepcopy(original)
    target = manifest
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        verifier.verify_run(run)


@pytest.mark.parametrize("filename", ["video.mp4", "timeline.json"])
def test_rejects_artifact_replaced_after_render(smoke_run, filename):
    run, _ = smoke_run
    with (run / filename).open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="hash"):
        verifier.verify_run(run)


@pytest.mark.parametrize("value", [None, b""])
def test_rejects_missing_or_empty_video(smoke_run, value):
    run, _ = smoke_run
    video = run / "video.mp4"
    video.unlink()
    if value is not None:
        video.write_bytes(value)
    with pytest.raises(ValueError, match="video artifact"):
        verifier.verify_run(run)


@pytest.mark.parametrize(
    "key,value,message",
    [
        ("run_id", "other-run", "run IDs"),
        ("blocks", [], "no narration blocks"),
        ("events", [], "no narration blocks"),
        ("blocks", [{"beat_id": "other"}], "installation beat"),
    ],
)
def test_rejects_unrelated_or_empty_timeline(smoke_run, key, value, message):
    run, manifest = smoke_run
    path = run / "timeline.json"
    timeline = json.loads(path.read_text(encoding="utf-8"))
    timeline[key] = value
    path.write_text(json.dumps(timeline), encoding="utf-8")
    manifest["artifacts"]["timeline"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        verifier.verify_run(run)
