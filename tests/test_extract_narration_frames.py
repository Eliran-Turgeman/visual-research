"""Tests for the narration-review frame extraction script.

These exercise only the pure, ffmpeg-free logic: timestamp selection and
timeline/manifest validation. No subprocess or real video/frame is ever
touched here.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from extract_narration_frames import (  # noqa: E402
    Block,
    Timeline,
    TimelineValidationError,
    build_index,
    compute_review_timestamps,
    frame_filename,
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
    assert len(entries) == 3 * len(timeline.blocks)
    phases_seen = {entry["phase"] for entry in entries}
    assert phases_seen == {"start", "mid", "end"}


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
