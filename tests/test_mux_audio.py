"""Tiny FFmpeg fixtures exercise external muxing without speech services."""

import subprocess
from pathlib import Path

import pytest

from examples.ddtree_dflash.mux_audio import main, mux_audio, validate_pairing
from manim_lib.review import (
    ReviewError, artifact_reference, probe_media, read_json, resolve_ffmpeg,
    sha256_file, write_json,
)


@pytest.fixture(scope="module")
def media_files(tmp_path_factory):
    root = tmp_path_factory.mktemp("mux_media")
    ffmpeg = resolve_ffmpeg()
    subprocess.run([
        ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(root / "silent.mp4"),
    ], check=True, capture_output=True)
    subprocess.run([
        ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.5",
        str(root / "speech.wav"),
    ], check=True, capture_output=True)
    return root


@pytest.fixture
def bundle(tmp_path, media_files):
    video = media_files / "silent.mp4"
    audio = media_files / "speech.wav"
    manifest = tmp_path / "external.json"
    timeline = tmp_path / "timeline.json"
    write_json(manifest, {
        "scene_duration": 2,
        "tracks": [{"file": str(audio), "start": 0.2, "duration": 0.5, "text": "first"},
                   {"file": str(audio), "start": 1.0, "duration": 0.5, "text": "second"}],
    })
    write_json(timeline, {
        "scene_duration": 2,
        "blocks": [{"index": 0, "start": 0.2, "end": 0.7, "text": "first"},
                   {"index": 1, "start": 1.0, "end": 1.5, "text": "second"}],
    })
    return video, manifest, timeline


def versioned(bundle):
    video, path, _ = bundle
    manifest = read_json(path)
    manifest.update(schema_version=1, run_id="mux-test", video=artifact_reference(video))
    for track in manifest["tracks"]:
        track["sha256"] = sha256_file(Path(track["file"]))
    write_json(path, manifest)


def test_mux_preserves_visual_hold_and_pads_full_audio(bundle, tmp_path):
    video, manifest, timeline = bundle
    output = mux_audio(video, tmp_path / "out.mp4", manifest, timeline_path=timeline)
    media = probe_media(output)
    assert media["video_duration"] == pytest.approx(2)
    assert media["audio_duration"] == pytest.approx(2, abs=0.03)
    assert media["fps"] == 10
    receipt = read_json(output.with_suffix(".mp4.mux.json"))
    assert receipt["pairing"] == "legacy_timeline_checked"
    assert receipt["output"] == artifact_reference(output)
    # The final hold is silent, while the actual delayed narration is audible.
    import av
    import numpy as np
    with av.open(str(output)) as container:
        signal = np.concatenate([frame.to_ndarray().reshape(-1) for frame in container.decode(audio=0)])
    assert np.max(np.abs(signal[int(0.3 * 48000):int(0.5 * 48000)])) > 0.01
    assert np.max(np.abs(signal[int(1.7 * 48000):int(1.9 * 48000)])) < 0.001
    with av.open(str(video)) as original, av.open(str(output)) as muxed:
        old = list(original.decode(video=0))
        new = list(muxed.decode(video=0))
        assert len(new) == len(old) == 20
        assert np.array_equal(new[-1].to_ndarray(), old[-1].to_ndarray())


def test_legacy_manifest_requires_explicit_timeline(bundle):
    video, manifest, _ = bundle
    with pytest.raises(ReviewError, match="Legacy.*--timeline"):
        validate_pairing(video, manifest)


def test_versioned_manifest_binds_video_and_tracks(bundle, tmp_path):
    versioned(bundle)
    video, manifest, _ = bundle
    output = mux_audio(video, tmp_path / "bound.mp4", manifest, run_id="mux-test")
    assert read_json(output.with_suffix(".mp4.mux.json"))["pairing"] == "hash_bound"


def test_wrong_run_or_video_hash_is_rejected(bundle):
    versioned(bundle)
    video, path, _ = bundle
    with pytest.raises(ReviewError, match="run_id"):
        validate_pairing(video, path, run_id="stale")
    manifest = read_json(path)
    manifest["video"]["sha256"] = "0" * 64
    write_json(path, manifest)
    with pytest.raises(ReviewError, match="SHA-256 mismatch"):
        validate_pairing(video, path)


def test_wrong_track_hash_is_rejected(bundle):
    versioned(bundle)
    video, path, _ = bundle
    manifest = read_json(path)
    manifest["tracks"][0]["sha256"] = "0" * 64
    write_json(path, manifest)
    with pytest.raises(ReviewError, match="SHA-256 mismatch"):
        validate_pairing(video, path)


@pytest.mark.parametrize("change", [
    {"start": -1}, {"start": float("nan")}, {"duration": float("inf")},
    {"duration": -1}, {"duration": 0}, {"duration": 0.9},
    {"start": 1.8}, {"text": "stale narration"}, {"file": "missing.wav"},
])
def test_invalid_or_stale_tracks_are_rejected(bundle, change):
    video, path, timeline = bundle
    manifest = read_json(path)
    manifest["tracks"][0].update(change)
    # Deliberately permit NaN/Inf to test rejection of hostile legacy JSON.
    import json
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ReviewError):
        validate_pairing(video, path, timeline_path=timeline)


def test_overlapping_tracks_are_rejected(bundle):
    video, path, timeline = bundle
    manifest = read_json(path)
    manifest["tracks"][1]["start"] = 0.4
    write_json(path, manifest)
    with pytest.raises(ReviewError, match="overlapping"):
        validate_pairing(video, path, timeline_path=timeline)


def test_wrong_scene_duration_is_rejected(bundle):
    video, path, timeline = bundle
    manifest = read_json(path)
    manifest["scene_duration"] = 9
    write_json(path, manifest)
    with pytest.raises(ReviewError, match="Video duration"):
        validate_pairing(video, path, timeline_path=timeline)


def test_missing_track_is_not_silently_skipped(bundle):
    video, path, timeline = bundle
    manifest = read_json(path)
    manifest["tracks"].pop()
    write_json(path, manifest)
    with pytest.raises(ReviewError, match="track count"):
        validate_pairing(video, path, timeline_path=timeline)


def test_existing_output_is_not_replaced(bundle, tmp_path):
    video, manifest, timeline = bundle
    output = tmp_path / "existing.mp4"
    output.write_bytes(b"existing artifact")
    with pytest.raises(ReviewError, match="already exists"):
        mux_audio(video, output, manifest, timeline_path=timeline)
    assert output.read_bytes() == b"existing artifact"


def test_cli_requires_explicit_manifest(bundle, tmp_path):
    video, _, _ = bundle
    with pytest.raises(SystemExit) as result:
        main([str(video), str(tmp_path / "out.mp4")])
    assert result.value.code == 2


def test_subprocess_success_without_output_cannot_publish(bundle, tmp_path, monkeypatch):
    video, manifest, timeline = bundle
    monkeypatch.setattr("examples.ddtree_dflash.mux_audio.subprocess.run", lambda *a, **k: None)
    with pytest.raises(ReviewError, match="missing or empty"):
        mux_audio(video, tmp_path / "out.mp4", manifest, timeline_path=timeline)
    assert not (tmp_path / "out.mp4").exists()


def test_relative_tracks_resolve_against_manifest_directory(bundle, tmp_path):
    import shutil
    video, path, timeline = bundle
    manifest = read_json(path)
    audio = tmp_path / "relative.wav"
    shutil.copyfile(manifest["tracks"][0]["file"], audio)
    for track in manifest["tracks"]:
        track["file"] = audio.name
    write_json(path, manifest)
    _, _, tracks = validate_pairing(video, path, timeline_path=timeline)
    assert all(Path(track["file"]) == audio for track in tracks)
