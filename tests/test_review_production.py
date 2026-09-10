"""Local-only review fixtures; synthetic media never stands in for human review."""

import json
import subprocess
from pathlib import Path

import pytest

from manim_lib.review import (
    ReviewError, accept_production, artifact_reference, inspect_production,
    media_tolerance, probe_media, read_json, resolve_ffmpeg, sha256_file,
    utc_now, validate_frame_evidence, validate_human_evidence,
    validate_video_timing, verify_acceptance, write_json,
)
from scripts.extract_narration_frames import extract_review
from scripts.review_production import main


@pytest.fixture(scope="module")
def media_files(tmp_path_factory):
    root = tmp_path_factory.mktemp("review_media")
    ffmpeg = resolve_ffmpeg()
    for audio, filename in ((True, "spoken.mp4"), (False, "silent.mp4")):
        command = [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1"]
        if audio:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if audio:
            command += ["-c:a", "aac"]
        subprocess.run(command + [str(root / filename)], check=True, capture_output=True)
    return root


@pytest.fixture
def manifest(tmp_path, media_files):
    timeline = tmp_path / "timeline.json"
    write_json(timeline, {
        "schema_version": 1, "run_id": "review-test", "scene_duration": 1,
        "blocks": [{"index": 0, "start": 0, "end": 1, "duration": 1,
                    "text": "Synthetic local fixture", "beat_id": "example"}],
        "events": [{"time": 0.5, "label": "midpoint", "beat_id": "example"}],
    })
    path = tmp_path / "manifest.json"
    write_json(path, {
        "schema_version": 1, "run_id": "review-test", "profile": "production",
        "status": "rendered", "artifacts": {
            "video": artifact_reference(media_files / "spoken.mp4"),
            "timeline": artifact_reference(timeline),
        },
    })
    return path


def human_evidence(record, digest):
    return {
        "schema_version": 1, "run_id": record["run_id"], "review_sha256": digest,
        "reviewer": "Test reviewer (synthetic fixture only)", "reviewed_at": utc_now(),
        "decision": "accept",
        "confirmations": {
            "watched_full_video": True, "listened_full_audio": True,
            "visual_quality": True, "synchronization": True, "teaching_correctness": True,
        },
        "audiovisual_notes": "Synthetic unit-test attestation, not a real review.",
        "teaching_notes": "Fixture tests validation only, not comprehension.",
        "findings": [],
    }


def prepared_review(manifest, tmp_path):
    record = inspect_production(manifest)
    index = extract_review(
        Path(record["artifacts"]["video"]["path"]),
        Path(record["artifacts"]["timeline"]["path"]), tmp_path / "frames",
    )
    record["frame_evidence"] = artifact_reference(index)
    record_path = tmp_path / "review.json"
    write_json(record_path, record)
    evidence_path = tmp_path / "human.json"
    write_json(evidence_path, human_evidence(record, sha256_file(record_path)))
    return record_path, evidence_path


def test_inspection_is_not_human_acceptance(manifest):
    record = inspect_production(manifest)
    assert record["status"] == "technically_verified"
    assert record["human_review"] is None
    assert record["technical"]["status"] == "passed"
    assert "audio_presence_and_duration" in record["technical"]["checks"]
    assert record["media"]["video_duration"] == pytest.approx(1)


def test_probe_uses_existing_pyav_when_ffprobe_is_absent(media_files, monkeypatch):
    monkeypatch.setattr("manim_lib.review.shutil.which", lambda _: None)
    media = probe_media(media_files / "spoken.mp4")
    assert media["audio_duration"] == pytest.approx(1, abs=0.03)
    assert media["video_duration"] == pytest.approx(1)
    assert media["fps"] == 10


def test_ffprobe_path_returns_stream_not_container_duration(media_files, monkeypatch):
    monkeypatch.setattr("manim_lib.review.shutil.which", lambda _: "ffprobe")
    response = {"streams": [
        {"codec_type": "video", "duration": "1", "start_time": "0", "avg_frame_rate": "10/1"},
        {"codec_type": "audio", "duration": "1", "start_time": "0"},
    ], "format": {"duration": "99"}}
    monkeypatch.setattr("manim_lib.review.subprocess.run", lambda *a, **k: subprocess.CompletedProcess(
        a, 0, stdout=json.dumps(response),
    ))
    assert probe_media(media_files / "spoken.mp4")["video_duration"] == 1


def test_rejects_stale_timeline_hash(manifest):
    timeline = Path(read_json(manifest)["artifacts"]["timeline"]["path"])
    timeline.write_text(timeline.read_text() + " ")
    with pytest.raises(ReviewError, match="SHA-256 mismatch"):
        inspect_production(manifest)


def test_rejects_stale_video_hash(manifest):
    data = read_json(manifest)
    data["artifacts"]["video"]["sha256"] = "0" * 64
    write_json(manifest, data)
    with pytest.raises(ReviewError, match="SHA-256 mismatch"):
        inspect_production(manifest)


@pytest.mark.parametrize("run_id", ["other-run", None])
def test_manifest_review_requires_run_bound_timeline(manifest, run_id):
    data = read_json(manifest)
    timeline_path = Path(data["artifacts"]["timeline"]["path"])
    timeline = read_json(timeline_path)
    if run_id is None:
        timeline.pop("run_id")
    else:
        timeline["run_id"] = run_id
    write_json(timeline_path, timeline)
    data["artifacts"]["timeline"] = artifact_reference(timeline_path)
    write_json(manifest, data)
    with pytest.raises(ReviewError, match="run_id"):
        inspect_production(manifest)


def test_production_requires_audio_but_draft_does_not(manifest, media_files):
    data = read_json(manifest)
    data["artifacts"]["video"] = artifact_reference(media_files / "silent.mp4")
    write_json(manifest, data)
    with pytest.raises(ReviewError, match="audio stream"):
        inspect_production(manifest)
    data["profile"] = "draft"
    write_json(manifest, data)
    assert inspect_production(manifest)["profile"] == "draft"


def test_video_duration_must_match_timeline(manifest):
    data = read_json(manifest)
    timeline = Path(data["artifacts"]["timeline"]["path"])
    contents = read_json(timeline)
    contents["scene_duration"] = 3
    write_json(timeline, contents)
    data["artifacts"]["timeline"] = artifact_reference(timeline)
    write_json(manifest, data)
    with pytest.raises(ReviewError, match="Video duration"):
        inspect_production(manifest)


@pytest.mark.parametrize("change", [
    {"audio_duration": None}, {"audio_duration": 0.5},
    {"audio_start": 0.5}, {"video_start": 0.5},
])
def test_audio_coverage_and_zero_origin_are_required(change):
    media = {"video_duration": 2, "audio_duration": 2, "audio_start": 0,
             "video_start": 0, "fps": 30}
    media.update(change)
    with pytest.raises(ReviewError):
        validate_video_timing(media, 2, require_audio=True)


def test_media_tolerance_is_two_frames_or_100_ms():
    assert media_tolerance(10) == 0.2
    assert media_tolerance(60) == 0.1


def test_acceptance_requires_frame_evidence(manifest, tmp_path):
    record = inspect_production(manifest)
    record_path = tmp_path / "review.json"
    write_json(record_path, record)
    evidence = tmp_path / "human.json"
    write_json(evidence, human_evidence(record, sha256_file(record_path)))
    with pytest.raises(ReviewError, match="frame_evidence"):
        accept_production(manifest, record_path, evidence)


def test_real_extraction_and_explicit_acceptance_are_durable(manifest, tmp_path):
    record_path, evidence = prepared_review(manifest, tmp_path)
    original_digest = sha256_file(record_path)
    result = accept_production(manifest, record_path, evidence)
    assert result["status"] == "accepted"
    assert result["technical_review_sha256"] == original_digest
    assert result["human_review"]["reviewer"].startswith("Test reviewer")
    accepted = tmp_path / "accepted.json"
    write_json(accepted, result)
    assert verify_acceptance(manifest, accepted) == result
    assert sha256_file(record_path) == original_digest
    with pytest.raises(ReviewError, match="technically_verified"):
        accept_production(manifest, accepted, evidence)


def test_acceptance_rejects_stale_record(manifest, tmp_path):
    record_path, evidence = prepared_review(manifest, tmp_path)
    record = read_json(record_path)
    record["media"]["video_duration"] = 99
    write_json(record_path, record)
    with pytest.raises(ReviewError, match="stale or altered"):
        accept_production(manifest, record_path, evidence)


def test_acceptance_rejects_missing_or_altered_frame(manifest, tmp_path):
    record_path, evidence = prepared_review(manifest, tmp_path)
    record = read_json(record_path)
    index = read_json(Path(record["frame_evidence"]["path"]))
    Path(index["frames"][0]["file"]).write_bytes(b"stale")
    with pytest.raises(ReviewError, match="SHA-256 mismatch"):
        accept_production(manifest, record_path, evidence)


def test_index_cannot_silently_drop_transition_frames(manifest, tmp_path):
    record_path, _ = prepared_review(manifest, tmp_path)
    record = read_json(record_path)
    index_path = Path(record["frame_evidence"]["path"])
    index = read_json(index_path)
    index["frames"].pop()
    index["frame_count"] -= 1
    write_json(index_path, index)
    with pytest.raises(ReviewError, match="incomplete"):
        validate_frame_evidence(index_path, record)


@pytest.fixture
def simple_record():
    return {"run_id": "test", "profile": "production", "created_at": utc_now(),
            "media": {"video_duration": 12}}


@pytest.mark.parametrize("field,value", [
    ("reviewer", ""), ("reviewed_at", "yesterday"), ("reviewed_at", "2026-01-01T00:00:00"),
    ("reviewed_at", "2099-01-01T00:00:00Z"), ("reviewed_at", "2000-01-01T00:00:00Z"),
    ("decision", "maybe"), ("run_id", "stale"), ("review_sha256", "stale"),
    ("findings", None), ("teaching_notes", ""), ("audiovisual_notes", ""),
])
def test_human_evidence_must_be_explicit_and_current(simple_record, field, value):
    evidence = human_evidence(simple_record, "digest")
    evidence[field] = value
    with pytest.raises(ReviewError):
        validate_human_evidence(evidence, simple_record, "digest")


@pytest.mark.parametrize("confirmation", [
    "watched_full_video", "listened_full_audio", "visual_quality",
    "synchronization", "teaching_correctness",
])
def test_no_confirmation_is_inferred(simple_record, confirmation):
    evidence = human_evidence(simple_record, "digest")
    evidence["confirmations"].pop(confirmation)
    with pytest.raises(ReviewError, match="confirmations"):
        validate_human_evidence(evidence, simple_record, "digest")


def finding(**overrides):
    result = {
        "id": "F1", "time_seconds": 1.5, "severity": "blocker", "status": "open",
        "description": "Meaning changes incorrectly.", "expected_behavior": "Preserve semantics.",
    }
    result.update(overrides)
    return result


@pytest.mark.parametrize("severity", ["blocker", "major"])
def test_unresolved_blockers_and_major_findings_prevent_acceptance(simple_record, severity):
    evidence = human_evidence(simple_record, "digest")
    evidence["findings"] = [finding(severity=severity)]
    with pytest.raises(ReviewError, match="Unresolved"):
        validate_human_evidence(evidence, simple_record, "digest")


@pytest.mark.parametrize("overrides", [
    {"time_seconds": float("nan")}, {"time_seconds": -1}, {"time_seconds": 13},
    {"expected_behavior": ""}, {"description": ""}, {"severity": "unknown"},
    {"status": "waived"}, {"status": "resolved"},
])
def test_findings_require_actionable_timed_evidence(simple_record, overrides):
    evidence = human_evidence(simple_record, "digest")
    evidence["findings"] = [finding(**overrides)]
    with pytest.raises(ReviewError):
        validate_human_evidence(evidence, simple_record, "digest")


def test_resolved_finding_requires_attributed_resolution(simple_record):
    evidence = human_evidence(simple_record, "digest")
    evidence["findings"] = [finding(
        status="resolved", resolution="Verified corrected at this timestamp.",
        resolved_by="Test reviewer", resolved_at=evidence["reviewed_at"],
    )]
    validate_human_evidence(evidence, simple_record, "digest")


def test_cli_inspect_and_accept_failure_exit_clearly(manifest, tmp_path, capsys):
    record = tmp_path / "review.json"
    assert main(["inspect", str(manifest), "--output", str(record)]) == 0
    assert "NOT human accepted" in capsys.readouterr().out
    with pytest.raises(SystemExit) as result:
        main(["accept", str(manifest), "--record", str(record), "--evidence", str(tmp_path / "absent.json")])
    assert result.value.code == 2
    assert "frame_evidence" in capsys.readouterr().err
    assert read_json(record)["status"] == "technically_verified"


def test_cli_acceptance_does_not_write_without_explicit_evidence(manifest, tmp_path, capsys):
    record, evidence = prepared_review(manifest, tmp_path)
    invalid = read_json(evidence)
    invalid["confirmations"]["teaching_correctness"] = False
    write_json(evidence, invalid)
    before = record.read_bytes()
    with pytest.raises(SystemExit):
        main(["accept", str(manifest), "--record", str(record), "--evidence", str(evidence)])
    assert "confirmations" in capsys.readouterr().err
    assert record.read_bytes() == before


def test_teaching_artifact_binding_without_teaching_module(manifest, tmp_path):
    record, evidence = prepared_review(manifest, tmp_path)
    contract = tmp_path / "teaching.json"
    validation = tmp_path / "teaching-validation.json"
    write_json(contract, {"title": "Tiny contract fixture"})
    write_json(validation, {"schema_version": 1, "status": "passed",
                            "contract": artifact_reference(contract), "run_id": "review-test"})
    human = read_json(evidence)
    human["teaching_contract_sha256"] = sha256_file(contract)
    write_json(evidence, human)
    result = accept_production(manifest, record, evidence, teaching_contract=contract, teaching_validation=validation)
    assert result["teaching"]["contract"] == artifact_reference(contract)
    contract.write_text('{"changed":true}')
    with pytest.raises(ReviewError, match="SHA-256 mismatch"):
        accept_production(manifest, record, evidence, teaching_contract=contract, teaching_validation=validation)


def test_cli_accept_preserves_technical_record_and_verifies_all_evidence(manifest, tmp_path):
    record, evidence = prepared_review(manifest, tmp_path)
    before = record.read_bytes()
    assert main(["accept", str(manifest), "--record", str(record), "--evidence", str(evidence)]) == 0
    accepted = record.with_name("review.accepted.json")
    assert record.read_bytes() == before
    assert main(["verify", str(manifest), "--record", str(accepted)]) == 0
    human = read_json(evidence)
    human["reviewer"] = "Changed later"
    write_json(evidence, human)
    with pytest.raises(ReviewError, match="SHA-256 mismatch"):
        verify_acceptance(manifest, accepted)


def test_modified_embedded_human_attestation_is_detected(manifest, tmp_path):
    record, evidence = prepared_review(manifest, tmp_path)
    result = accept_production(manifest, record, evidence)
    result["human_review"]["teaching_notes"] = "An altered claim"
    accepted = tmp_path / "accepted.json"
    write_json(accepted, result)
    with pytest.raises(ReviewError, match="altered: human_review"):
        verify_acceptance(manifest, accepted)
