"""Timeline arithmetic, bounded sampling and extraction-integrity regressions."""

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from extract_narration_frames import (  # noqa: E402
    Block,
    Timeline,
    TimelineValidationError,
    build_index,
    build_contact_sheets,
    compute_review_timestamps,
    frame_filename,
    extract_frame,
    load_timeline,
    validate_cli_inputs,
    validate_timeline,
)


def make_timeline(**overrides) -> dict:
    timeline = {
        "scene_duration": 20.0,
        "blocks": [
            {"index": 0, "start": 0.0, "end": 5.0, "duration": 5.0, "text": "intro"},
            {"index": 1, "start": 5.0, "end": 12.5, "duration": 7.5, "text": "body"},
            {"index": 2, "start": 12.5, "end": 20.0, "duration": 7.5, "text": "outro"},
        ],
    }
    timeline.update(overrides)
    return timeline


# --------------------------------------------------------------------------
# compute_review_timestamps
# --------------------------------------------------------------------------


def test_timestamps_are_strictly_ordered_and_inside_block():
    result = compute_review_timestamps(10.0, 20.0, scene_duration=100.0)
    assert 10.0 < result["start"] < result["mid"] < result["end"] < 20.0


def test_timestamps_avoid_exact_scene_boundaries():
    result = compute_review_timestamps(0.0, 100.0, scene_duration=100.0)
    assert result["start"] > 0.0
    assert result["end"] < 100.0


def test_midpoint_is_true_block_center():
    result = compute_review_timestamps(4.0, 10.0, scene_duration=50.0)
    assert result["mid"] == pytest.approx(7.0)


def test_short_block_still_produces_distinct_or_valid_timestamps():
    # A very short block cannot fit three well-separated samples, but the
    # function must not raise, and every timestamp must stay within bounds.
    result = compute_review_timestamps(10.0, 10.05, scene_duration=50.0)
    assert 10.0 <= result["start"] <= 10.05
    assert 10.0 <= result["mid"] <= 10.05
    assert 10.0 <= result["end"] <= 10.05


def test_zero_duration_block_does_not_raise():
    result = compute_review_timestamps(5.0, 5.0, scene_duration=50.0)
    assert result["start"] == result["mid"] == result["end"] == pytest.approx(5.0)


def test_boundary_offset_is_capped_for_long_blocks():
    result = compute_review_timestamps(0.0, 1000.0, scene_duration=1000.0)
    # The inward nudge must stay bounded even for a very long block, so the
    # start/end samples remain "near" the boundary rather than drifting
    # toward the midpoint.
    assert result["start"] <= 0.4 + 1e-6
    assert result["end"] >= 1000.0 - 0.4 - 1e-6 - 0.02


def test_rejects_end_before_start():
    with pytest.raises(ValueError):
        compute_review_timestamps(5.0, 1.0, scene_duration=50.0)


def test_rejects_non_positive_scene_duration():
    with pytest.raises(ValueError):
        compute_review_timestamps(0.0, 1.0, scene_duration=0.0)


# --------------------------------------------------------------------------
# frame_filename
# --------------------------------------------------------------------------


def test_frame_filename_is_deterministic_and_contains_index_and_phase():
    assert frame_filename(3, "mid", index_width=2) == "block03_mid.jpg"


def test_frame_filename_rejects_unknown_phase():
    with pytest.raises(ValueError):
        frame_filename(0, "climax", index_width=2)


# --------------------------------------------------------------------------
# validate_timeline / load_timeline
# --------------------------------------------------------------------------


def test_validate_timeline_accepts_well_formed_document():
    timeline = validate_timeline(make_timeline())
    assert isinstance(timeline, Timeline)
    assert timeline.scene_duration == 20.0
    assert len(timeline.blocks) == 3
    assert timeline.blocks[0] == Block(0, 0.0, 5.0, 5.0, "intro")


def test_validate_timeline_rejects_non_dict_root():
    with pytest.raises(TimelineValidationError, match="JSON object"):
        validate_timeline(["not", "a", "dict"])


def test_validate_timeline_rejects_missing_scene_duration():
    data = make_timeline()
    del data["scene_duration"]
    with pytest.raises(TimelineValidationError, match="scene_duration"):
        validate_timeline(data)


def test_validate_timeline_rejects_non_positive_scene_duration():
    with pytest.raises(TimelineValidationError, match="positive"):
        validate_timeline(make_timeline(scene_duration=0))


def test_validate_timeline_rejects_empty_blocks():
    with pytest.raises(TimelineValidationError, match="non-empty"):
        validate_timeline(make_timeline(blocks=[]))


def test_validate_timeline_rejects_missing_blocks_key():
    data = make_timeline()
    del data["blocks"]
    with pytest.raises(TimelineValidationError, match="non-empty"):
        validate_timeline(data)


def test_validate_timeline_rejects_non_numeric_start():
    data = make_timeline()
    data["blocks"][0]["start"] = "zero"
    with pytest.raises(TimelineValidationError, match="non-numeric 'start'"):
        validate_timeline(data)


def test_validate_timeline_rejects_end_before_start():
    data = make_timeline()
    data["blocks"][0]["end"] = -1.0
    with pytest.raises(TimelineValidationError, match="end"):
        validate_timeline(data)


def test_validate_timeline_rejects_negative_start():
    data = make_timeline()
    data["blocks"][0]["start"] = -5.0
    with pytest.raises(TimelineValidationError, match="negative"):
        validate_timeline(data)


def test_validate_timeline_rejects_block_past_scene_duration():
    data = make_timeline()
    data["blocks"][-1]["end"] = 1000.0
    with pytest.raises(TimelineValidationError, match="scene_duration"):
        validate_timeline(data)


def test_validate_timeline_rejects_blank_text():
    data = make_timeline()
    data["blocks"][0]["text"] = "   "
    with pytest.raises(TimelineValidationError, match="text"):
        validate_timeline(data)


def test_validate_timeline_rejects_duplicate_index():
    data = make_timeline()
    data["blocks"][1]["index"] = 0
    with pytest.raises(TimelineValidationError, match="Duplicate"):
        validate_timeline(data)


def test_validate_timeline_rejects_overlapping_blocks():
    data = make_timeline()
    data["blocks"][1]["start"] = 1.0  # Now overlaps block 0's [0, 5) span.
    with pytest.raises(TimelineValidationError, match="overlap"):
        validate_timeline(data)


def test_validate_timeline_defaults_duration_from_start_and_end():
    data = make_timeline()
    del data["blocks"][0]["duration"]
    timeline = validate_timeline(data)
    assert timeline.blocks[0].duration == pytest.approx(5.0)


def test_load_timeline_reports_invalid_json(tmp_path):
    bad = tmp_path / "timeline.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(TimelineValidationError, match="not valid JSON"):
        load_timeline(bad)


def test_load_timeline_reports_missing_file(tmp_path):
    with pytest.raises(TimelineValidationError):
        load_timeline(tmp_path / "missing.json")


def test_load_timeline_round_trips_a_real_file(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text(json.dumps(make_timeline()), encoding="utf-8")
    data = load_timeline(path)
    timeline = validate_timeline(data)
    assert len(timeline.blocks) == 3


# --------------------------------------------------------------------------
# build_index
# --------------------------------------------------------------------------


def test_build_index_produces_three_entries_per_block():
    timeline = validate_timeline(make_timeline())
    entries = build_index(timeline, Path("frames"))
    assert len([entry for entry in entries if entry["phase"] != "boundary"]) == 3 * len(timeline.blocks)
    assert len(entries) > 3 * len(timeline.blocks)
    phases_seen = {entry["phase"] for entry in entries}
    assert phases_seen == {"start", "mid", "end", "boundary"}


def test_build_index_entries_reference_source_block_text_and_timestamps():
    timeline = validate_timeline(make_timeline())
    entries = build_index(timeline, Path("frames"))
    block_zero_entries = [entry for entry in entries if entry["block_index"] == 0]
    assert len(block_zero_entries) == 3
    for entry in block_zero_entries:
        assert entry["text"] == "intro"
        assert entry["block_start"] == 0.0
        assert entry["block_end"] == 5.0
        assert 0.0 <= entry["timestamp"] <= 5.0


def test_build_index_filenames_are_unique():
    timeline = validate_timeline(make_timeline())
    entries = build_index(timeline, Path("frames"))
    files = [entry["file"] for entry in entries]
    assert len(files) == len(set(files))


# --------------------------------------------------------------------------
# validate_cli_inputs
# --------------------------------------------------------------------------


def test_validate_cli_inputs_rejects_missing_video(tmp_path):
    timeline = tmp_path / "timeline.json"
    timeline.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="does not exist"):
        validate_cli_inputs(tmp_path / "missing.mp4", timeline, tmp_path / "out")


def test_validate_cli_inputs_rejects_empty_video(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"")
    timeline = tmp_path / "timeline.json"
    timeline.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="empty"):
        validate_cli_inputs(video, timeline, tmp_path / "out")


def test_validate_cli_inputs_rejects_missing_timeline(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")
    with pytest.raises(SystemExit, match="does not exist"):
        validate_cli_inputs(video, tmp_path / "missing.json", tmp_path / "out")


def test_validate_cli_inputs_rejects_output_dir_that_is_a_file(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")
    timeline = tmp_path / "timeline.json"
    timeline.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.write_text("not a directory", encoding="utf-8")
    with pytest.raises(SystemExit, match="not a directory"):
        validate_cli_inputs(video, timeline, output_dir)


def test_validate_cli_inputs_accepts_well_formed_paths(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")
    timeline = tmp_path / "timeline.json"
    timeline.write_text("{}", encoding="utf-8")
    # Should not raise.
    validate_cli_inputs(video, timeline, tmp_path / "out")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 10**1000])
@pytest.mark.parametrize("field", ["scene_duration", "start", "end", "duration"])
def test_rejects_nonfinite_numbers(field, value):
    data = make_timeline()
    target = data if field == "scene_duration" else data["blocks"][0]
    target[field] = value
    with pytest.raises(TimelineValidationError, match="finite"):
        validate_timeline(data)


@pytest.mark.parametrize("index", [-1, 2, True])
def test_rejects_invalid_indices(index):
    data = make_timeline()
    data["blocks"][0]["index"] = index
    with pytest.raises(TimelineValidationError, match="index"):
        validate_timeline(data)


def test_does_not_sort_contradictory_input():
    data = make_timeline()
    data["blocks"] = list(reversed(data["blocks"]))
    for index, block in enumerate(data["blocks"]):
        block["index"] = index
    with pytest.raises(TimelineValidationError, match="order"):
        validate_timeline(data)


@pytest.mark.parametrize("duration", [-1, 0, 4.99, 6.0])
def test_rejects_inconsistent_or_nonpositive_duration(duration):
    data = make_timeline()
    data["blocks"][0]["duration"] = duration
    with pytest.raises(TimelineValidationError, match="duration"):
        validate_timeline(data)


def test_duration_tolerance_is_one_millisecond():
    data = make_timeline()
    data["blocks"][0]["duration"] += 0.001
    validate_timeline(data)
    data["blocks"][0]["duration"] += 0.0001
    with pytest.raises(TimelineValidationError, match="1 ms"):
        validate_timeline(data)


@pytest.mark.parametrize("events", [
    None, [{}], [{"time": float("nan"), "label": "bad"}],
    [{"time": -1, "label": "bad"}], [{"time": 21, "label": "bad"}],
    [{"time": 1, "label": ""}],
    [{"time": 2, "label": "second"}, {"time": 1, "label": "first"}],
])
def test_rejects_invalid_events(events):
    with pytest.raises(TimelineValidationError):
        validate_timeline(make_timeline(events=events))


@pytest.mark.parametrize("overrides", [
    {"run_id": None}, {"run_id": ""}, {"schema_version": True}, {"schema_version": 2},
])
def test_rejects_invalid_optional_metadata(overrides):
    with pytest.raises(TimelineValidationError):
        validate_timeline(make_timeline(**overrides))


def test_plan_preserves_beats_and_event_boundaries_and_endpoints():
    data = make_timeline(run_id="run-1", schema_version=1, events=[
        {"time": 7.0, "label": "replace", "beat_id": "replacement"},
        {"time": 7.0, "label": "same-time highlight"},
    ])
    data["blocks"][0]["beat_id"] = "intro"
    timeline = validate_timeline(data)
    entries = build_index(timeline, Path("frames"), fps=25)
    assert timeline.run_id == "run-1"
    assert entries[0]["beat_id"] == "intro"
    assert any(e["timestamp"] == 0 for e in entries)
    assert any(e["timestamp"] == pytest.approx(19.96) for e in entries)
    event_entries = [
        e for e in entries if any(s["kind"] == "event" for s in e.get("sample_sources", []))
    ]
    assert len(event_entries) == 2
    assert {e["timestamp"] for e in event_entries} == {6.96, 7.04}
    assert all(len(e["sample_sources"]) == 2 for e in event_entries)


def test_large_plan_fails_instead_of_omitting_evidence():
    timeline = validate_timeline(make_timeline())
    with pytest.raises(TimelineValidationError, match="exceeding limit"):
        build_index(timeline, Path("frames"), max_frames=3)


def test_short_scene_samples_only_usable_frame():
    timeline = validate_timeline({"scene_duration": 0.02, "blocks": [
        {"index": 0, "start": 0, "end": 0.02, "text": "one frame"},
    ]})
    assert {e["timestamp"] for e in build_index(timeline, Path("frames"), fps=25)} == {0}


def test_ffmpeg_success_without_a_jpeg_is_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("extract_narration_frames.subprocess.run", lambda *a, **k: None)
    with pytest.raises(ValueError, match="nonempty"):
        extract_frame("ffmpeg", tmp_path / "video.mp4", 0, tmp_path / "frame.jpg")


def test_stale_frame_is_not_success(tmp_path, monkeypatch):
    frame = tmp_path / "frame.jpg"
    Image.new("RGB", (8, 8)).save(frame)
    monkeypatch.setattr("extract_narration_frames.subprocess.run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(ValueError, match="stale"):
        extract_frame("ffmpeg", tmp_path / "video.mp4", 0, frame)
    assert frame.exists()


def test_contact_sheet_does_not_hide_missing_frame(tmp_path):
    with pytest.raises(ValueError, match="nonempty"):
        build_contact_sheets([{"file": str(tmp_path / "missing.jpg")}], tmp_path)


def test_contact_sheet_rejects_corrupt_frame(tmp_path):
    frame = tmp_path / "bad.jpg"
    frame.write_bytes(b"not a jpeg")
    with pytest.raises(ValueError, match="not a JPEG"):
        build_contact_sheets([{"file": str(frame)}], tmp_path)


def test_contact_sheets_include_boundary_entries(tmp_path):
    frame = tmp_path / "valid.jpg"
    Image.new("RGB", (32, 18)).save(frame)
    entries = [{"file": str(frame), "block_index": None, "phase": "boundary",
                "timestamp": 0, "text": "first frame"}] * 25
    sheets = build_contact_sheets(entries, tmp_path)
    assert len(sheets) == 2
    assert all(path.stat().st_size > 0 for path in sheets)


def test_rejects_existing_output_directory(tmp_path):
    video, timeline, output = tmp_path / "video.mp4", tmp_path / "timeline.json", tmp_path / "out"
    video.write_bytes(b"fake")
    timeline.write_text("{}")
    output.mkdir()
    (output / "index.json").write_text("stale")
    with pytest.raises(SystemExit, match="must be empty"):
        validate_cli_inputs(video, timeline, output)
