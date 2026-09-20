"""Theory arc, semantics, geometry, and rendered-event checks for Jev."""

from __future__ import annotations

import json

import pytest
from manim import tempconfig

from examples.jev_system_one_workflow.scene import (
    AtomicPicture,
    CalibrationPicture,
    ConfidencePicture,
    ContractPicture,
    ControlPicture,
    JevSystemOneWorkflow,
    JobComparison,
    ParallelPicture,
    PrimitivePicture,
    RolePicture,
    SupportPicture,
)
from examples.jev_system_one_workflow.storyboard import (
    BEATS,
    JUDGMENTS,
    POLICY_THRESHOLDS,
    ToyJudgments,
    route_support_case,
)
from manim_lib import (
    QuestionKind,
    assert_no_overlaps,
    assert_within_safe_frame,
)
from manim_lib.teaching import load_contract, validate_contract


@pytest.fixture(scope="module")
def rendered_scene(tmp_path_factory):
    output = tmp_path_factory.mktemp("jev_theory_workflow")
    with pytest.MonkeyPatch.context() as patch, tempconfig(
        {
            "dry_run": True,
            "skip_animations": True,
            "quality": "low_quality",
            "media_dir": str(output),
            "verbosity": "ERROR",
            "progress_bar": "none",
        }
    ):
        patch.setenv("MANIM_TTS_PROVIDER", "none")
        patch.delenv("MANIM_TIMELINE_PATH", raising=False)
        scene = JevSystemOneWorkflow()
        scene.review_timeline_path = output / "timeline.json"
        scene.render()
    return scene


def test_teaching_contract_is_complete_and_uses_supported_checks():
    document = load_contract(
        "examples/jev_system_one_workflow/teaching.json"
    )
    report = validate_contract(document)
    assert report["valid"], report["errors"]
    assert len(document["beats"]) == 12
    assert document["timeline_mapping"] == "complete"
    assert {check["kind"] for check in report["checks"]} == {
        "probability_graphic"
    }
    assert all(check["passed"] for check in report["checks"])
    assert "policy-threshold check kind" in document["assumptions"][1]


def test_arc_is_theory_first_and_two_to_three_minutes_in_silent_timing():
    assert [beat.id for beat in BEATS[:4]] == [
        "generation-versus-evaluation",
        "system-one-role",
        "typed-contract",
        "atomic-questions",
    ]
    assert BEATS[10].id == "support-example-input"
    assert all("CS 1042" not in beat.narration for beat in BEATS[:10])
    words = sum(len(beat.narration.split()) for beat in BEATS)
    assert 285 <= words <= 430
    estimated_seconds = sum(
        max(1.8, len(beat.narration.split()) / 2.65) for beat in BEATS
    )
    assert 108 <= estimated_seconds <= 180


def test_narration_covers_required_limits_without_vendor_benchmarks():
    narration = " ".join(beat.narration for beat in BEATS).lower()
    required = (
        "generation and evaluation are different jobs",
        "does not write explanations",
        "atomic typed question",
        "independently and in parallel",
        "no separate confidence",
        "calibration is checked across groups",
        "code owns thresholds",
        "not an autonomous agent",
        "schema can be valid while the judgment is wrong",
        "confidence is not certainty",
    )
    for phrase in required:
        assert phrase in narration
    for forbidden in (
        "times faster",
        "times cheaper",
        "cost per",
        "latency",
        "always correct",
        "can't hallucinate",
        "cannot hallucinate",
    ):
        assert forbidden not in narration


def test_primitive_semantics_and_confidence_scope_are_explicit():
    picture = PrimitivePicture()
    assert [card.kind for card in picture.questions.values()] == [
        QuestionKind.CHOICE,
        QuestionKind.SCORE,
        QuestionKind.NOUL,
    ]
    assert picture.results["choice"].result.confidence == 0.72
    assert picture.results["score"].result.confidence == 0.61
    noul = picture.results["noul"].result
    assert noul.answer == 0.88
    assert noul.confidence is None
    assert noul.confidence_label.text == ""
    assert "no extra confidence" in (
        picture.results["noul"].probability_caption.original_text
    )


def test_parallel_picture_has_shared_state_and_no_answer_dependencies():
    picture = ParallelPicture()
    assert len(picture.state.fields) == 2
    assert set(picture.questions) == set(picture.results) == {
        "choice",
        "score",
        "noul",
    }
    assert len(picture.fanout) == 3
    assert len(picture.into_model) == 3
    assert len(picture.out_of_model) == 3
    assert all(
        picture.state.get_right()[0] < arrow.get_start()[0]
        < picture.questions[key].get_left()[0]
        for key, arrow in picture.fanout.items()
    )


def test_confidence_and_calibration_visuals_preserve_the_distinction():
    confidence = ConfidencePicture()
    assert confidence.peaked.entries["A"].value == 0.80
    assert confidence.spread.entries["A"].value == 0.40
    assert "summarizes the distribution" in confidence.distinction.original_text

    calibration = CalibrationPicture()
    assert calibration.plot.bins["high bin"].confidence == 0.8
    assert calibration.plot.bins["high bin"].accuracy == 0.8
    colors = [circle.get_fill_color() for circle in calibration.outcomes]
    assert len(colors) == 10
    assert "can still be wrong" in calibration.single_case.semantic_text


def test_code_and_not_model_owns_routing_and_side_effects():
    control = ControlPicture()
    assert "if confidence < floor:" == control.code.line(1).source
    assert "perform_action()" in control.code.line(4).source

    support = SupportPicture()
    assert route_support_case() == "priority_refund"
    assert support.selected_route == support.router.selected_route
    assert support.router.selected_route == "priority_refund"
    lower_confidence = ToyJudgments(
        route_confidence=POLICY_THRESHOLDS["route_confidence"] - 0.01
    )
    assert route_support_case(lower_confidence) == "manual_review"
    assert support.results["refund_requested"].result.confidence is None


@pytest.mark.parametrize(
    "picture",
    [
        JobComparison(),
        RolePicture(),
        ContractPicture(),
        AtomicPicture(),
        PrimitivePicture(),
        ParallelPicture(),
        ConfidencePicture(),
        CalibrationPicture(),
        ControlPicture(),
    ],
)
def test_theory_compositions_are_safe_and_non_overlapping(picture):
    assert_within_safe_frame(picture.group, margin=0.10)
    assert_no_overlaps(picture.collision_objects)


def test_support_compositions_are_safe_and_non_overlapping():
    picture = SupportPicture()
    assert_within_safe_frame(picture.group, margin=0.10)
    assert_no_overlaps(picture.input_collision_objects)
    assert_no_overlaps(picture.final_collision_objects)


def test_silent_dry_render_records_the_replaced_twelve_beat_arc(rendered_scene):
    assert [block["beat_id"] for block in rendered_scene._review_blocks] == [
        beat.id for beat in BEATS
    ]
    assert 108 <= rendered_scene.time <= 180
    assert [
        (event["beat_id"], event["label"])
        for event in rendered_scene._review_events
    ] == [
        ("generation-versus-evaluation", "two-jobs-visible"),
        ("system-one-role", "system-one-boundary-visible"),
        ("typed-contract", "typed-contract-visible"),
        ("atomic-questions", "broad-question-decomposed"),
        ("choice-semantics", "choice-contract-visible"),
        ("score-and-noul-semantics", "score-noul-contracts-visible"),
        ("shared-state-parallelism", "parallel-independent-results"),
        (
            "probability-versus-confidence",
            "probability-confidence-separated",
        ),
        ("calibration-is-aggregate", "aggregate-calibration-visible"),
        ("code-owns-control", "code-control-boundary-visible"),
        (
            "support-example-input",
            "support-state-and-questions-visible",
        ),
        ("support-example-route", "route-selected:priority_refund"),
    ]
    assert rendered_scene.picture.router.selected_route == route_support_case()
    timeline = json.loads(
        rendered_scene.review_timeline_path.read_text(encoding="utf-8")
    )
    assert timeline["events"] == rendered_scene._review_events
