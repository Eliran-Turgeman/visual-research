import numpy as np
import pytest
from manim import LEFT, RIGHT, linear

from manim_lib.contracts import OptionSet, SchemaBoundary
from manim_lib.decisions import (
    DecisionResult,
    DecisionState,
    QuestionCard,
    QuestionKind,
)
from manim_lib.layout import contains
from manim_lib.probability import ProbabilityDistribution
from manim_lib.theme import DANGER


def test_question_constructors_share_shape_and_expose_semantics():
    choice = QuestionCard.choice("route", "Choose the next route", ["fast", "safe"])
    score = QuestionCard.score("risk", "Estimate risk", (0, 10))
    noul = QuestionCard.noul("positive", "The review is positive")
    assert [card.kind for card in (choice, score, noul)] == [
        QuestionKind.CHOICE,
        QuestionKind.SCORE,
        QuestionKind.NOUL,
    ]
    assert choice.output_space == "choices: fast | safe"
    assert score.output_space == "score: [0, 10]"
    assert noul.output_space == "truth likelihood: [0, 1]"
    for card in (choice, score, noul):
        assert card.key_label.text == card.key
        assert contains(card.card, card.instruction_label)
        assert np.allclose(card.input_anchor, card.card.get_left())
        assert np.allclose(card.output_anchor, card.card.get_right())


def test_question_anchors_and_active_state_follow_transforms():
    card = QuestionCard.choice(
        "route",
        "Choose a route with a deliberately long instruction that must fit",
        ["fast", "safe"],
    ).scale(0.7).shift(RIGHT * 2)
    points = card.card.get_all_points().copy()
    assert card.input_anchor[0] < card.output_anchor[0]
    assert card.set_active(True) is card
    assert card.active
    assert card.card.get_all_points() == pytest.approx(points)
    assert card.set_active(False) is card
    assert not card.active
    with pytest.raises(ValueError):
        QuestionCard.choice("empty", "No choices", [])
    with pytest.raises(ValueError):
        QuestionCard.score("bad", "Bad range", (1, 1))


def test_decision_result_validates_before_mutating_and_preserves_identity():
    result = DecisionResult(
        "risk",
        2,
        answer_type=int,
        confidence=0.4,
        state=DecisionState.ACTIVE,
    ).scale(0.75).shift(LEFT)
    objects = tuple(result.submobjects)
    answer = result.answer_label
    confidence = result.confidence_label
    card_points = result.card.get_all_points().copy()
    with pytest.raises(TypeError, match="answer_type"):
        result.set_answer("high")
    with pytest.raises(ValueError, match="between 0 and 1"):
        result.set_confidence(2)
    assert result.answer == 2
    assert result.confidence == 0.4
    assert result.card.get_all_points() == pytest.approx(card_points)

    result.set_answer(7).set_confidence(0.9).set_state(DecisionState.RESOLVED)
    assert result.answer == 7
    assert result.answer_label is answer
    assert result.confidence_label is confidence
    assert result.confidence == 0.9
    assert result.state is DecisionState.RESOLVED
    assert tuple(result.submobjects) == objects
    assert result.card.get_all_points() == pytest.approx(card_points)


def test_decision_distribution_and_noul_confidence_are_optional():
    distribution = ProbabilityDistribution({"yes": ("yes", 0.7), "no": ("no", 0.3)})
    result = DecisionResult(
        "choice", "yes", answer_type=str, distribution=distribution
    )
    assert result.distribution is distribution
    assert distribution in result.submobjects
    assert result.confidence is None
    assert result.confidence_label.get_fill_opacity() == 0

    noul_result = DecisionResult("positive", 0.72, answer_type=float)
    assert noul_result.confidence is None
    assert noul_result.confidence_label.text == ""
    assert noul_result.state is DecisionState.PENDING


def test_decision_animate_methods_complete_with_semantic_state():
    result = DecisionResult("route", "fast", answer_type=str)
    objects = tuple(result.submobjects)
    animation = (
        result.animate(rate_func=linear)
        .set_answer("safe")
        .set_confidence(0.8)
        .set_state(DecisionState.RESOLVED)
        .build()
    )
    animation.begin()
    animation.interpolate(1)
    animation.finish()
    assert result.answer == "safe"
    assert result.confidence == 0.8
    assert result.state is DecisionState.RESOLVED
    assert tuple(result.submobjects) == objects


def test_option_set_uses_typed_membership_and_visual_violation():
    options = OptionSet([True, 1, "1"])
    assert options.accepts(True)
    assert options.accepts(1)
    assert options.accepts("1")
    assert not options.accepts(1.0)
    assert options.highlight_allowed(1) is options
    assert options.highlighted_value == 1
    options.show_violation("other")
    assert options.violating_value == "other"
    assert options.violation_label.get_fill_opacity() > 0
    for option in options.options:
        assert option.box.get_stroke_color().to_hex() == DANGER.base.upper()


def test_schema_boundary_represents_declared_structure_only():
    boundary = SchemaBoundary("route schema", ["fast", "safe"])
    assert boundary.declared_values == ("fast", "safe")
    assert boundary.accepts("safe")
    assert not boundary.accepts("best")
    assert boundary.highlight_allowed("safe") is boundary
    assert not boundary.violating
    assert boundary.show_violation("best") is boundary
    assert boundary.violating
    assert boundary.boundary.get_center() == pytest.approx(
        SchemaBoundary("route schema", ["fast", "safe"]).boundary.get_center()
    )
    assert boundary.boundary.get_all_points() == pytest.approx(
        SchemaBoundary("route schema", ["fast", "safe"]).boundary.get_all_points()
    )
