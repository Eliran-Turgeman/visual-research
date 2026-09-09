"""Test the geometry and semantics of the speculative decoding timeline."""

import numpy as np
import pytest
from manim import tempconfig

from examples.speculative_decoding_timeline.scene import (
    NARRATION,
    ROW_Y,
    TIMELINE_LENGTH,
    TIMING,
    WORDS,
    ZOOM,
    TokenMark,
    ToyTiming,
    DecodingTimelinePicture,
    SpeculativeDecodingTimeline,
)
from manim_lib import assert_no_overlaps, assert_within_safe_frame


def test_toy_clock_includes_drafting_before_verification():
    assert TIMING.baseline_end == pytest.approx(3.0)
    assert TIMING.draft_end == pytest.approx(0.6)
    assert TIMING.speculative_end == pytest.approx(1.6)
    p = DecodingTimelinePicture()
    assert p.verifier.start_time == p.drafts[-1].end_time
    assert p.verifier.end_time == TIMING.speculative_end
    for previous, current in zip(p.drafts, p.drafts[1:]):
        assert current.start_time == previous.end_time


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_toy_durations_raise(value):
    with pytest.raises(ValueError, match="positive and finite"):
        ToyTiming(draft_step=value)


def test_baseline_and_speculation_use_one_undistorted_time_scale():
    p = DecodingTimelinePicture()
    assert p.baseline.width >= TIMELINE_LENGTH
    assert p.verifier.track.width == pytest.approx(p.baseline_intervals[0].track.width)
    x0 = p.clock.point_at(0)[0]
    assert (p.speculative_finish_x - x0) / (p.baseline_finish_x - x0) == pytest.approx(
        TIMING.speculative_end / TIMING.baseline_end
    )
    assert p.saved_time[0].width == pytest.approx(
        TIMELINE_LENGTH * (TIMING.baseline_end - TIMING.speculative_end)
        / TIMING.baseline_end
    )


def test_progress_tracks_current_geometry_after_closeup_and_restore():
    p = DecodingTimelinePicture()
    interval = p.baseline_intervals[0]
    interval.scale(ZOOM).shift(np.array([2.0, -1.0, 0.0]))
    ids = tuple(id(part) for part in interval)
    for alpha in (0, 0.3, 0.8, 1):
        interval.set_progress(alpha)
        assert interval.fill.width == pytest.approx(interval.track.width * alpha)
        assert interval.cursor.get_center()[0] == pytest.approx(
            interval.track.get_left()[0] + interval.track.width * alpha
        )
        assert tuple(id(part) for part in interval) == ids
    interval.finish()
    assert interval.cursor.get_stroke_opacity() == 0
    with pytest.raises(ValueError):
        interval.set_progress(1.1)


def test_acceptance_preserves_marker_and_label_identity():
    candidate = TokenMark("can", (0, 0, 0))
    marker, word = candidate.dot, candidate.word_label
    candidate.accept()
    assert candidate.accepted
    assert candidate.dot is marker
    assert candidate.word_label is word
    assert candidate.word == WORDS[0]
    assert candidate.dot.get_fill_color() == candidate.dot.get_stroke_color()


def test_opening_and_final_layout_fit_without_shrinking_the_whole_scene():
    p = DecodingTimelinePicture()
    opening = p.stages[0].copy().scale(ZOOM).move_to((0, 0.4, 0))
    assert_within_safe_frame(opening, margin=0.4, label="opening")
    for index, candidate in enumerate(p.candidates):
        candidate.shift(p.accepted_position(index) - candidate.dot.get_center())
        assert candidate.dot.get_center()[1] == ROW_Y[index]
    objects = [
        p.baseline, p.upper_label, p.lower_label, p.scale_note,
        p.assumption, p.verifier, p.verify_caption,
        p.same_prefix, p.prefix, p.payoff, p.saved_time,
        *p.candidates, *p.drafts,
    ]
    for mob in objects:
        assert_within_safe_frame(mob, margin=0.35)
    # Candidate markers intentionally overlap their verification region.
    assert_no_overlaps([
        p.upper_label, p.lower_label, p.assumption, p.scale_note,
        p.verify_caption, p.same_prefix, p.prefix, p.payoff,
        *p.baseline_tokens, *p.candidates,
    ])
    assert_no_overlaps([p.baseline, p.verifier, p.saved_time])
    assert_no_overlaps([p.verifier, p.verify_caption])


def test_draft_markers_and_words_do_not_collide_when_fanned_into_rows():
    p = DecodingTimelinePicture()
    for index, candidate in enumerate(p.candidates):
        candidate.shift(p.candidate_row_position(index) - candidate.dot.get_center())
        assert_within_safe_frame(candidate, margin=0.35)
    assert_no_overlaps(p.candidates)
    assert p.candidates[-1].dot.z_index > p.verifier.track.z_index


def test_earlier_drafts_wait_for_the_shared_target_pass():
    p = DecodingTimelinePicture()
    assert len(p.lead_ins) == len(WORDS) - 1
    for index, line in enumerate(p.lead_ins):
        assert line.get_start() == pytest.approx(p.candidate_row_position(index))
        assert line.get_end()[0] == pytest.approx(p.verifier.track.get_left()[0])


def test_concise_narration_and_explicit_all_accepted_assumption():
    assert 60 <= sum(len(block.split()) for block in NARRATION) <= 75
    assert "all three are accepted" in NARRATION[-1]
    assert "one after another" in NARRATION[2]
    assert "together" in NARRATION[4]


def test_scene_finishes_with_the_same_objects_at_the_expected_completion_points(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "none")
    with tempconfig({"dry_run": True, "skip_animations": True, "quality": "low_quality"}):
        scene = SpeculativeDecodingTimeline()
        scene.review_timeline_path = tmp_path / "timeline.json"
        scene.render()
    p = scene.picture
    assert scene.review_timeline_path.exists()
    assert len(scene._review_blocks) == len(NARRATION)
    assert 24 <= scene.time <= 33
    assert p.baseline in scene.mobjects
    for index, candidate in enumerate(p.candidates):
        assert candidate.accepted
        assert candidate.dot.get_center() == pytest.approx(p.accepted_position(index))
        assert candidate in scene.mobjects
        assert_within_safe_frame(candidate, margin=0.35)
    for index, interval in enumerate(p.baseline_intervals):
        assert interval.progress == 1
        assert interval.track.get_right()[0] == pytest.approx(
            p.clock.point_at((index + 1) * TIMING.target_pass)[0]
        )
    assert_within_safe_frame(p.baseline, margin=0.35)
