"""A theory-first Jev explainer built as one evolving evaluation workbench."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    AnimationGroup,
    Arrow,
    Circle,
    Create,
    Cross,
    Dot,
    FadeIn,
    FadeOut,
    Indicate,
    Line,
    Rectangle,
    RoundedRectangle,
    Text,
    VGroup,
)

from manim_lib import (
    ACCENT,
    BACKGROUND,
    DANGER,
    NEUTRAL,
    PRIMARY,
    SPACING,
    STROKES,
    SUCCESS,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    CalibrationPlot,
    CodeBlock,
    DecisionResult,
    DecisionRouter,
    DecisionState,
    NarratedScene,
    ProbabilityDistribution,
    QuestionCard,
    StructuredState,
    SystemNode,
    animate_parallel_evaluation,
)

try:
    from .storyboard import (
        BEATS,
        CASE_ID,
        JUDGMENTS,
        POLICY_THRESHOLDS,
        STATE_FIELDS,
        route_support_case,
    )
except ImportError:
    from storyboard import (
        BEATS,
        CASE_ID,
        JUDGMENTS,
        POLICY_THRESHOLDS,
        STATE_FIELDS,
        route_support_case,
    )


def _fit(text: Text, width: float, height: float) -> Text:
    factor = min(
        1.0,
        width / text.width if text.width else 1.0,
        height / text.height if text.height else 1.0,
    )
    if factor < 1:
        text.scale(factor)
    return text


def capsule(
    text: str,
    *,
    width: float,
    height: float = 0.72,
    color=NEUTRAL.base,
    font_size: float = 21,
) -> VGroup:
    body = RoundedRectangle(
        width=width,
        height=height,
        corner_radius=0.13,
        fill_color=SURFACE,
        fill_opacity=0.97,
        stroke_color=color,
        stroke_width=STROKES.normal.width,
    )
    label = _fit(
        Text(text, font_size=font_size, color=TEXT_PRIMARY),
        width - 2 * SPACING.sm,
        height - 2 * SPACING.xs,
    ).move_to(body)
    group = VGroup(body, label)
    group.semantic_text = text
    return group


def arrow_between(left, right, *, color=NEUTRAL.base) -> Arrow:
    return Arrow(
        left.get_right(),
        right.get_left(),
        buff=0.13,
        color=color,
        stroke_width=STROKES.normal.width,
        max_tip_length_to_length_ratio=0.10,
    )


class ResultBundle(VGroup):
    """A readable typed result plus a separate probability caption."""

    def __init__(
        self,
        key: str,
        answer,
        answer_type,
        probability_caption: str,
        *,
        confidence: float | None,
        width: float = 2.55,
    ):
        self.result = DecisionResult(
            key,
            answer,
            answer_type=answer_type,
            confidence=confidence,
            state=DecisionState.RESOLVED,
            width=width,
            height=1.18,
            font_size=21,
        )
        self.result.source_label.move_to(self.result.card.get_top() + DOWN * 0.14)
        self.result.answer_label.move_to(
            self.result.card.get_center() + LEFT * 0.33 + DOWN * 0.02
        )
        self.result.type_label.move_to(
            self.result.card.get_right()
            + LEFT * (SPACING.sm + self.result.type_label.width / 2)
            + DOWN * 0.02
        )
        self.result.confidence_label.move_to(
            self.result.card.get_bottom() + UP * 0.13
        )
        self.probability_caption = _fit(
            Text(probability_caption, font_size=15, color=TEXT_SECONDARY),
            width,
            0.24,
        )
        super().__init__(self.result, self.probability_caption)
        self.arrange(DOWN, buff=0.10)

    @property
    def input_anchor(self):
        return self.result.input_anchor


class JobComparison:
    """Two different jobs on a shared visual grammar."""

    def __init__(self):
        self.generation_label = Text(
            "GENERATION", font_size=17, color=TEXT_SECONDARY
        ).move_to((-5.6, 2.45, 0))
        self.prompt = capsule("prompt", width=2.0).move_to((-4.65, 1.35, 0))
        self.generator = SystemNode(
            "generative model", width=2.25, height=1.0, font_size=20
        ).move_to((0, 1.35, 0))
        self.generated = capsule(
            "new text: token → token → token",
            width=3.25,
            color=PRIMARY.base,
        ).move_to((4.55, 1.35, 0))
        self.generation_arrows = VGroup(
            arrow_between(self.prompt, self.generator),
            arrow_between(self.generator, self.generated, color=PRIMARY.base),
        )
        self.generation = VGroup(
            self.generation_label,
            self.prompt,
            self.generator,
            self.generated,
            self.generation_arrows,
        )

        self.evaluation_label = Text(
            "EVALUATION", font_size=17, color=TEXT_SECONDARY
        ).move_to((-5.6, -0.25, 0))
        self.supplied = capsule(
            "supplied state + question",
            width=3.0,
            color=ACCENT.base,
        ).move_to((-4.35, -1.35, 0))
        self.evaluator = SystemNode(
            "evaluator", width=2.25, height=1.0, font_size=20
        ).move_to((0, -1.35, 0))
        self.judgment = capsule(
            "typed judgment + probability",
            width=3.25,
            color=SUCCESS.base,
        ).move_to((4.55, -1.35, 0))
        self.evaluation_arrows = VGroup(
            arrow_between(self.supplied, self.evaluator, color=ACCENT.base),
            arrow_between(self.evaluator, self.judgment, color=SUCCESS.base),
        )
        self.evaluation = VGroup(
            self.evaluation_label,
            self.supplied,
            self.evaluator,
            self.judgment,
            self.evaluation_arrows,
        )
        self.group = VGroup(self.generation, self.evaluation)
        self.collision_objects = [
            self.prompt,
            self.generator,
            self.generated,
            self.supplied,
            self.evaluator,
            self.judgment,
        ]


class RolePicture:
    """The evaluator boundary and explicit non-agent responsibilities."""

    def __init__(self):
        self.state_question = capsule(
            "state + focused question", width=3.1, color=ACCENT.base
        ).move_to((-4.5, 0.65, 0))
        self.model = SystemNode(
            "Jev · System One", width=2.65, height=1.18, font_size=23
        ).move_to((0, 0.65, 0))
        self.result = capsule(
            "typed decision + probabilities", width=3.25, color=SUCCESS.base
        ).move_to((4.55, 0.65, 0))
        self.arrows = VGroup(
            arrow_between(self.state_question, self.model, color=ACCENT.base),
            arrow_between(self.model, self.result, color=SUCCESS.base),
        )
        self.not_items = VGroup(
            *[
                capsule(text, width=2.55, height=0.64, color=DANGER.base, font_size=18)
                for text in ("not a text writer", "not a code generator", "not an agent loop")
            ]
        ).arrange(RIGHT, buff=0.45).move_to((0, -1.65, 0))
        self.crosses = VGroup(
            *[
                Cross(item[0], stroke_color=DANGER.light, stroke_width=2.2)
                for item in self.not_items
            ]
        )
        self.group = VGroup(
            self.state_question,
            self.model,
            self.result,
            self.arrows,
            self.not_items,
            self.crosses,
        )
        self.collision_objects = [
            self.state_question,
            self.model,
            self.result,
            *self.not_items,
        ]


class ContractPicture:
    """The state + atomic typed question -> typed result contract."""

    def __init__(self):
        self.state = StructuredState(
            {
                "content": ("Content", "text or structured JSON", "state"),
                "context": ("Context", "relevant facts", "state"),
            },
            width=3.2,
            field_height=0.68,
            field_buff=0.10,
            font_size=18,
        ).move_to((-4.75, 0.3, 0))
        self.plus = Text("+", font_size=34, color=TEXT_SECONDARY).move_to(
            (-2.65, 0.3, 0)
        )
        self.question = QuestionCard.choice(
            "question_id",
            "Which declared option?",
            ["A", "B", "C"],
            width=3.35,
            height=1.45,
            font_size=20,
        ).move_to((-0.55, 0.3, 0))
        self.model = SystemNode(
            "Jev", width=1.2, height=1.1, font_size=22
        ).move_to((2.15, 0.3, 0))
        self.result = ResultBundle(
            "question_id",
            "A",
            str,
            "probabilities over A · B · C",
            confidence=0.72,
            width=2.65,
        ).move_to((4.85, 0.3, 0))
        self.arrows = VGroup(
            arrow_between(self.question, self.model, color=ACCENT.base),
            arrow_between(self.model, self.result, color=SUCCESS.base),
        )
        self.declared = capsule(
            "answer space declared before evaluation",
            width=4.2,
            height=0.62,
            color=PRIMARY.base,
            font_size=18,
        ).move_to((0, -2.15, 0))
        self.group = VGroup(
            self.state,
            self.plus,
            self.question,
            self.model,
            self.result,
            self.arrows,
            self.declared,
        )
        self.collision_objects = [
            self.state,
            self.plus,
            self.question,
            self.model,
            self.result,
            self.declared,
        ]


class AtomicPicture:
    """One broad request decomposed into independent atomic questions."""

    def __init__(self):
        self.broad = QuestionCard.noul(
            "broad",
            "Analyze this and decide what to do",
            output_space="too many judgments hidden in one answer",
            width=6.0,
            height=1.45,
            font_size=22,
        ).move_to((0, 1.65, 0))
        self.broad.card.set_stroke(DANGER.base)
        self.atomic = VGroup(
            QuestionCard.choice(
                "category", "Which category?", ["A", "B", "C"],
                width=3.3, height=1.35, font_size=19,
            ),
            QuestionCard.score(
                "severity", "Which severity level?", (0, 5),
                width=3.3, height=1.35, font_size=19,
            ),
            QuestionCard.noul(
                "claim", "Is this statement true?",
                width=3.3, height=1.35, font_size=19,
            ),
        ).arrange(RIGHT, buff=0.65).move_to((0, -1.15, 0))
        self.arrows = VGroup(
            *[
                Arrow(
                    self.broad.get_bottom(),
                    card.get_top(),
                    buff=0.14,
                    color=PRIMARY.dim,
                    stroke_width=STROKES.normal.width,
                    max_tip_length_to_length_ratio=0.10,
                )
                for card in self.atomic
            ]
        )
        self.group = VGroup(self.broad, self.arrows, self.atomic)
        self.collision_objects = [self.broad, *self.atomic]


class PrimitivePicture:
    """Choice, Score, and Noul as three distinct typed contracts."""

    def __init__(self):
        rows = (1.75, 0.0, -1.75)
        self.questions = {
            "choice": QuestionCard.choice(
                "choice", "Which declared option?", ["A", "B", "C"],
                width=4.0, height=1.30, font_size=20,
            ),
            "score": QuestionCard.score(
                "score", "Which ordered level?", (0, 5),
                width=4.0, height=1.30, font_size=20,
            ),
            "noul": QuestionCard.noul(
                "noul", "Is one statement true?",
                width=4.0, height=1.30, font_size=20,
            ),
        }
        self.results = {
            "choice": ResultBundle(
                "choice", "A", str, "distribution over declared options",
                confidence=0.72, width=3.0,
            ),
            "score": ResultBundle(
                "score", 4, int, "distribution over ordered levels",
                confidence=0.61, width=3.0,
            ),
            "noul": ResultBundle(
                "noul", 0.88, float, "yes probability · no extra confidence",
                confidence=None, width=3.0,
            ),
        }
        for question, result, y in zip(
            self.questions.values(), self.results.values(), rows
        ):
            question.move_to((-3.45, y, 0))
            result.move_to((3.5, y, 0))
        self.arrows = VGroup(
            *[
                arrow_between(self.questions[key], self.results[key], color=ACCENT.base)
                for key in self.questions
            ]
        )
        self.group = VGroup(
            *self.questions.values(), self.arrows, *self.results.values()
        )
        self.collision_objects = [
            *self.questions.values(),
            *self.results.values(),
        ]


class ParallelPicture:
    """One state, three independent lanes, and no answer-to-answer edges."""

    def __init__(self):
        rows = (1.65, 0.0, -1.65)
        self.state = StructuredState(
            {
                "content": ("Content", "shared input", "state"),
                "context": ("Context", "shared facts", "state"),
            },
            width=2.55,
            field_height=0.68,
            field_buff=0.10,
            font_size=17,
        ).move_to((-5.25, 0, 0))
        self.questions = {
            "choice": QuestionCard.choice(
                "choice", "Which option?", ["A", "B", "C"],
                width=2.8, height=1.18, font_size=18,
            ),
            "score": QuestionCard.score(
                "score", "Which level?", (0, 5),
                width=2.8, height=1.18, font_size=18,
            ),
            "noul": QuestionCard.noul(
                "noul", "Is it true?", width=2.8, height=1.18, font_size=18,
            ),
        }
        self.results = {
            "choice": ResultBundle(
                "choice", "A", str, "option probabilities", confidence=0.72,
                width=2.35,
            ),
            "score": ResultBundle(
                "score", 4, int, "level probabilities", confidence=0.61,
                width=2.35,
            ),
            "noul": ResultBundle(
                "noul", 0.88, float, "yes probability", confidence=None,
                width=2.35,
            ),
        }
        for question, result, y in zip(
            self.questions.values(), self.results.values(), rows
        ):
            question.move_to((-2.05, y, 0))
            result.move_to((4.65, y, 0))
        self.model = SystemNode(
            "Jev", width=0.78, height=5.15, font_size=20
        ).move_to((1.25, 0, 0))
        self.lane_inputs = {
            key: Dot((self.model.body.get_left()[0], y, 0), radius=0.045, color=PRIMARY.light)
            for key, y in zip(self.questions, rows)
        }
        self.lane_outputs = {
            key: Dot((self.model.body.get_right()[0], y, 0), radius=0.045, color=ACCENT.light)
            for key, y in zip(self.questions, rows)
        }
        self.fanout = {
            key: Arrow(
                self.state.get_right(),
                question.input_anchor,
                buff=0.12,
                color=NEUTRAL.base,
                stroke_width=STROKES.hairline.width,
                max_tip_length_to_length_ratio=0.08,
            )
            for key, question in self.questions.items()
        }
        self.into_model = VGroup(
            *[
                Line(
                    self.questions[key].output_anchor,
                    self.lane_inputs[key].get_center(),
                    color=PRIMARY.dim,
                    stroke_width=STROKES.normal.width,
                )
                for key in self.questions
            ]
        )
        self.out_of_model = VGroup(
            *[
                Line(
                    self.lane_outputs[key].get_center(),
                    self.results[key].input_anchor,
                    color=ACCENT.dim,
                    stroke_width=STROKES.normal.width,
                )
                for key in self.questions
            ]
        )
        self.same_state_label = capsule(
            "same state · independent lanes · parallel evaluation",
            width=5.4,
            height=0.58,
            color=PRIMARY.base,
            font_size=17,
        ).move_to((-1.1, -3.05, 0))
        self.base = VGroup(
            self.state,
            *self.fanout.values(),
            *self.questions.values(),
            self.into_model,
            self.model,
            *self.lane_inputs.values(),
            *self.lane_outputs.values(),
            self.out_of_model,
            self.same_state_label,
        )
        self.result_group = VGroup(*self.results.values())
        self.group = VGroup(self.base, self.result_group)
        self.collision_objects = [
            self.state,
            *self.questions.values(),
            self.model,
            *self.results.values(),
            self.same_state_label,
        ]


class ConfidencePicture:
    """Probability distributions first; confidence as a derived summary."""

    def __init__(self):
        self.peaked = ProbabilityDistribution(
            {"A": ("A", 0.80), "B": ("B", 0.12), "C": ("C", 0.08)},
            max_bar_width=2.2,
            bar_height=0.34,
            font_size=22,
        ).move_to((-3.5, 0.45, 0))
        self.spread = ProbabilityDistribution(
            {"A": ("A", 0.40), "B": ("B", 0.33), "C": ("C", 0.27)},
            max_bar_width=2.2,
            bar_height=0.34,
            font_size=22,
        ).move_to((3.5, 0.45, 0))
        self.peaked_title = Text(
            "outcome probabilities", font_size=22, color=TEXT_PRIMARY
        ).next_to(self.peaked, UP, buff=0.45)
        self.spread_title = self.peaked_title.copy().next_to(
            self.spread, UP, buff=0.45
        )
        self.high = capsule(
            "concentrated shape → higher confidence",
            width=4.2,
            color=SUCCESS.base,
            font_size=18,
        ).next_to(self.peaked, DOWN, buff=0.45)
        self.low = capsule(
            "spread shape → lower confidence",
            width=4.2,
            color=ACCENT.base,
            font_size=18,
        ).next_to(self.spread, DOWN, buff=0.45)
        self.distinction = Text(
            "probabilities describe outcomes · confidence summarizes the distribution",
            font_size=20,
            color=TEXT_SECONDARY,
        ).move_to((0, -2.85, 0))
        self.group = VGroup(
            self.peaked,
            self.spread,
            self.peaked_title,
            self.spread_title,
            self.high,
            self.low,
            self.distinction,
        )
        self.collision_objects = [
            self.peaked,
            self.spread,
            self.peaked_title,
            self.spread_title,
            self.high,
            self.low,
            self.distinction,
        ]


class CalibrationPicture:
    """An aggregate calibration view plus one explicitly uncertain case."""

    def __init__(self):
        self.plot = CalibrationPlot(
            {
                "low bin": (0.3, 0.3),
                "middle bin": (0.55, 0.56),
                "high bin": (0.8, 0.8),
            },
            width=4.0,
            height=2.65,
        ).scale(0.9).move_to((-3.35, 0.15, 0))
        self.group_panel = RoundedRectangle(
            width=4.3,
            height=2.7,
            corner_radius=0.16,
            fill_color=SURFACE,
            fill_opacity=0.96,
            stroke_color=PRIMARY.dim,
            stroke_width=STROKES.normal.width,
        ).move_to((3.55, 0.35, 0))
        self.group_title = Text(
            "illustrative 0.8 group", font_size=22, color=TEXT_PRIMARY
        ).move_to(self.group_panel.get_top() + DOWN * 0.35)
        self.outcomes = VGroup(
            *[
                Circle(
                    radius=0.22,
                    fill_color=SUCCESS.base if index < 8 else DANGER.base,
                    fill_opacity=0.88,
                    stroke_width=0,
                )
                for index in range(10)
            ]
        ).arrange_in_grid(rows=2, cols=5, buff=(0.28, 0.35)).move_to(
            self.group_panel.get_center() + DOWN * 0.15
        )
        self.group_note = _fit(
            Text(
                "8 correct across 10 comparable cases",
                font_size=18,
                color=TEXT_SECONDARY,
            ),
            self.group_panel.width - 0.35,
            0.28,
        ).move_to(self.group_panel.get_bottom() + UP * 0.35)
        self.single_case = capsule(
            "one case at 0.8 can still be wrong",
            width=4.5,
            color=DANGER.base,
            font_size=19,
        ).move_to((3.55, -2.35, 0))
        self.group = VGroup(
            self.plot,
            self.group_panel,
            self.group_title,
            self.outcomes,
            self.group_note,
            self.single_case,
        )
        self.collision_objects = [self.plot, VGroup(
            self.group_panel, self.group_title, self.outcomes, self.group_note
        ), self.single_case]


class ControlPicture:
    """Typed judgments stop at code; code selects side effects."""

    def __init__(self):
        self.judgments = VGroup(
            capsule("Choice result", width=2.55, color=SUCCESS.base),
            capsule("Score result", width=2.55, color=SUCCESS.base),
            capsule("Noul result", width=2.55, color=SUCCESS.base),
        ).arrange(DOWN, buff=0.38).move_to((-4.75, 0.35, 0))
        self.code = CodeBlock(
            [
                "if confidence < floor:",
                "    route_to_review()",
                "elif policy_allows(answer):",
                "    perform_action()",
            ],
            width=4.8,
            line_height=0.52,
            font_size=20,
        ).move_to((0, 0.35, 0))
        self.review = capsule(
            "review", width=2.4, color=ACCENT.base
        ).move_to((5.0, 1.15, 0))
        self.action = capsule(
            "controlled side effect", width=2.8, color=SUCCESS.base
        ).move_to((5.0, -0.65, 0))
        self.boundary = Line(
            (3.15, -2.0, 0),
            (3.15, 2.65, 0),
            color=NEUTRAL.dim,
            stroke_width=STROKES.hairline.width,
        )
        self.boundary_label = Text(
            "code owns control",
            font_size=17,
            color=TEXT_SECONDARY,
        ).next_to(self.boundary, UP, buff=0.15)
        self.arrows = VGroup(
            *[
                Arrow(
                    result.get_right(),
                    self.code.get_left(),
                    buff=0.12,
                    color=NEUTRAL.base,
                    stroke_width=STROKES.hairline.width,
                    max_tip_length_to_length_ratio=0.08,
                )
                for result in self.judgments
            ],
            arrow_between(self.code, self.review, color=ACCENT.base),
            arrow_between(self.code, self.action, color=SUCCESS.base),
        )
        self.group = VGroup(
            self.judgments,
            self.code,
            self.boundary,
            self.boundary_label,
            self.review,
            self.action,
            self.arrows,
        )
        self.collision_objects = [
            *self.judgments,
            self.code,
            self.review,
            self.action,
        ]


class SupportPicture:
    """The final worked example, using the same contract and control boundary."""

    def __init__(self):
        rows = (1.65, 0.0, -1.55)
        self.case_label = Text(
            f"worked example · {CASE_ID}", font_size=19, color=TEXT_SECONDARY
        )
        self.state = StructuredState(
            STATE_FIELDS,
            width=2.9,
            field_height=0.63,
            field_buff=0.08,
            font_size=16,
        ).move_to((-5.15, 0.15, 0))
        self.case_label.next_to(self.state, UP, buff=0.18)
        self.questions = {
            "route": QuestionCard.choice(
                "route", "Which handling team?",
                ["billing", "technical", "account"],
                width=2.9, height=1.22, font_size=18,
            ),
            "urgency": QuestionCard.score(
                "urgency", "How urgent is this?", (0, 5),
                width=2.9, height=1.22, font_size=18,
            ),
            "refund_requested": QuestionCard.noul(
                "refund_requested", "The customer requests a refund",
                width=2.9, height=1.22, font_size=18,
            ),
        }
        self.results = {
            "route": ResultBundle(
                "route", JUDGMENTS.route, str, "P(billing) = 0.78",
                confidence=JUDGMENTS.route_confidence, width=2.4,
            ),
            "urgency": ResultBundle(
                "urgency", JUDGMENTS.urgency, int, "P(level 4) = 0.54",
                confidence=JUDGMENTS.urgency_confidence, width=2.4,
            ),
            "refund_requested": ResultBundle(
                "refund_requested", JUDGMENTS.refund_requested, float,
                "yes probability · no confidence",
                confidence=None, width=2.4,
            ),
        }
        for question, result, y in zip(
            self.questions.values(), self.results.values(), rows
        ):
            question.move_to((-1.75, y, 0))
            result.move_to((4.75, y, 0))
        self.model = SystemNode(
            "Jev", width=0.76, height=5.05, font_size=20
        ).move_to((1.15, 0, 0))
        self.fanout = VGroup(
            *[
                Arrow(
                    self.state.get_right(),
                    question.input_anchor,
                    buff=0.12,
                    color=NEUTRAL.base,
                    stroke_width=STROKES.hairline.width,
                    max_tip_length_to_length_ratio=0.08,
                )
                for question in self.questions.values()
            ]
        )
        self.question_edges = VGroup(
            *[
                Line(
                    question.output_anchor,
                    (self.model.body.get_left()[0], y, 0),
                    color=PRIMARY.dim,
                    stroke_width=STROKES.normal.width,
                )
                for question, y in zip(self.questions.values(), rows)
            ]
        )
        self.result_edges = VGroup(
            *[
                Line(
                    (self.model.body.get_right()[0], y, 0),
                    result.input_anchor,
                    color=ACCENT.dim,
                    stroke_width=STROKES.normal.width,
                )
                for result, y in zip(self.results.values(), rows)
            ]
        )
        self.policy = self._policy_panel().move_to((0.9, -3.18, 0))
        self.destinations = {
            "priority_refund": capsule(
                "priority refund", width=2.45, height=0.62, color=SUCCESS.base
            ).move_to((4.75, -2.74, 0)),
            "manual_review": capsule(
                "manual review", width=2.45, height=0.62, color=ACCENT.base
            ).move_to((4.75, -3.43, 0)),
        }
        self.router = DecisionRouter(
            self.policy,
            self.destinations,
            selected_color=SUCCESS.base,
        )
        self.selected_route = route_support_case()
        self.router.select_route(self.selected_route)
        self.policy.set_z_index(2)
        for edge in self.router.route_edges.values():
            edge.set_z_index(0)
        for highlight in self.router.route_highlights.values():
            highlight.set_z_index(1)
        for destination in self.destinations.values():
            destination.set_z_index(2)
        self.policy_inputs = VGroup(
            *[
                Line(
                    result.get_bottom(),
                    self.policy.get_top() + RIGHT * offset,
                    color=NEUTRAL.dim,
                    stroke_width=STROKES.hairline.width,
                )
                for result, offset in zip(self.results.values(), (-0.8, 0, 0.8))
            ]
        )
        self.caution = capsule(
            "schema-valid ≠ correct  ·  confidence ≠ certainty",
            width=4.6,
            color=DANGER.base,
            font_size=18,
        ).move_to((-4.25, -3.18, 0))
        self.base = VGroup(
            self.case_label,
            self.state,
            self.fanout,
            *self.questions.values(),
            self.question_edges,
            self.model,
            self.result_edges,
        )
        self.result_group = VGroup(*self.results.values())
        self.policy_group = VGroup(
            self.policy_inputs, self.router, self.caution
        )
        self.group = VGroup(self.base, self.result_group, self.policy_group)
        self.input_collision_objects = [
            VGroup(self.case_label, self.state),
            *self.questions.values(),
            self.model,
        ]
        self.final_collision_objects = [
            VGroup(self.case_label, self.state),
            *self.questions.values(),
            self.model,
            *self.results.values(),
            self.policy,
            *self.destinations.values(),
            self.caution,
        ]

    def _policy_panel(self):
        rules = (
            f"route = billing · conf ≥ {POLICY_THRESHOLDS['route_confidence']:.2f}",
            f"urgency ≥ {POLICY_THRESHOLDS['urgency']}",
            f"refund yes ≥ {POLICY_THRESHOLDS['refund_requested']:.2f}",
        )
        body = RoundedRectangle(
            width=3.25,
            height=1.18,
            corner_radius=0.14,
            fill_color=SURFACE,
            fill_opacity=0.98,
            stroke_color=SUCCESS.base,
            stroke_width=STROKES.normal.width,
        )
        title = Text("deterministic policy", font_size=18, color=SUCCESS.light)
        lines = VGroup(
            *[Text(f"✓  {rule}", font_size=14, color=TEXT_PRIMARY) for rule in rules]
        ).arrange(DOWN, buff=0.08, aligned_edge=LEFT)
        VGroup(title, lines).arrange(
            DOWN, buff=0.08, aligned_edge=LEFT
        ).move_to(body)
        return VGroup(body, title, lines)


class JevSystemOneWorkflow(NarratedScene):
    """Build the mental model first, then run one support record through it."""

    review_timeline_path = Path(
        "media/review/jev_system_one_workflow/timeline.json"
    )
    external_voiceover_subdir = "jev_system_one_workflow_external"

    def _transition(self, tracker, current, target):
        self.paced(
            tracker,
            AnimationGroup(
                FadeOut(current, shift=LEFT * 0.10),
                FadeIn(target, shift=RIGHT * 0.10),
                lag_ratio=0.12,
            ),
            fraction=0.55,
            maximum=3.0,
        )
        return target

    def construct(self):
        title = Text(
            "Jev: judgment inside software",
            font_size=31,
            color=TEXT_PRIMARY,
        ).move_to((0, 3.58, 0))
        self.stages = {}

        comparison = JobComparison()
        self.stages["comparison"] = comparison
        with self.narrate(BEATS[0].narration, beat_id=BEATS[0].id) as tracker:
            self.paced(
                tracker,
                FadeIn(title, shift=DOWN * 0.1),
                FadeIn(comparison.group),
                fraction=0.58,
            )
            self.record_visual_event("two-jobs-visible")
        current = comparison.group

        role = RolePicture()
        self.stages["role"] = role
        with self.narrate(BEATS[1].narration, beat_id=BEATS[1].id) as tracker:
            current = self._transition(tracker, current, role.group)
            self.record_visual_event("system-one-boundary-visible")

        contract = ContractPicture()
        self.stages["contract"] = contract
        with self.narrate(BEATS[2].narration, beat_id=BEATS[2].id) as tracker:
            current = self._transition(tracker, current, contract.group)
            self.record_visual_event("typed-contract-visible")

        atomic = AtomicPicture()
        self.stages["atomic"] = atomic
        with self.narrate(BEATS[3].narration, beat_id=BEATS[3].id) as tracker:
            current = self._transition(tracker, current, atomic.group)
            self.record_visual_event("broad-question-decomposed")

        primitives = PrimitivePicture()
        self.stages["primitives"] = primitives
        with self.narrate(BEATS[4].narration, beat_id=BEATS[4].id) as tracker:
            current = self._transition(tracker, current, primitives.group)
            self.paced(
                tracker,
                Indicate(primitives.questions["choice"], color=PRIMARY.light),
                Indicate(primitives.results["choice"], color=SUCCESS.light),
                fraction=0.24,
                maximum=1.2,
            )
            self.record_visual_event("choice-contract-visible")

        with self.narrate(BEATS[5].narration, beat_id=BEATS[5].id) as tracker:
            self.paced(
                tracker,
                AnimationGroup(
                    Indicate(primitives.questions["score"], color=PRIMARY.light),
                    Indicate(primitives.results["score"], color=SUCCESS.light),
                    lag_ratio=0,
                ),
                AnimationGroup(
                    Indicate(primitives.questions["noul"], color=PRIMARY.light),
                    Indicate(primitives.results["noul"], color=SUCCESS.light),
                    lag_ratio=0,
                ),
                fraction=0.58,
            )
            self.record_visual_event("score-noul-contracts-visible")

        parallel = ParallelPicture()
        self.stages["parallel"] = parallel
        with self.narrate(BEATS[6].narration, beat_id=BEATS[6].id) as tracker:
            current = self._transition(tracker, current, parallel.base)
            self.paced(
                tracker,
                animate_parallel_evaluation(
                    parallel.fanout,
                    parallel.questions,
                    parallel.results,
                ),
                fraction=0.35,
                maximum=1.8,
            )
            self.add(parallel.result_group)
            current = parallel.group
            self.record_visual_event("parallel-independent-results")

        confidence = ConfidencePicture()
        self.stages["confidence"] = confidence
        with self.narrate(BEATS[7].narration, beat_id=BEATS[7].id) as tracker:
            current = self._transition(tracker, current, confidence.group)
            self.record_visual_event("probability-confidence-separated")

        calibration = CalibrationPicture()
        self.stages["calibration"] = calibration
        with self.narrate(BEATS[8].narration, beat_id=BEATS[8].id) as tracker:
            current = self._transition(tracker, current, calibration.group)
            self.record_visual_event("aggregate-calibration-visible")

        control = ControlPicture()
        self.stages["control"] = control
        with self.narrate(BEATS[9].narration, beat_id=BEATS[9].id) as tracker:
            current = self._transition(tracker, current, control.group)
            control.code.focus_line(1)
            self.paced(
                tracker,
                Indicate(control.code, color=ACCENT.light),
                fraction=0.24,
                maximum=1.2,
            )
            self.record_visual_event("code-control-boundary-visible")

        support = SupportPicture()
        self.picture = support
        self.stages["support"] = support
        with self.narrate(BEATS[10].narration, beat_id=BEATS[10].id) as tracker:
            current = self._transition(tracker, current, support.base)
            self.record_visual_event("support-state-and-questions-visible")

        with self.narrate(BEATS[11].narration, beat_id=BEATS[11].id) as tracker:
            self.paced(
                tracker,
                animate_parallel_evaluation(
                    {
                        key: arrow
                        for key, arrow in zip(support.questions, support.fanout)
                    },
                    support.questions,
                    support.results,
                ),
                fraction=0.34,
                maximum=1.8,
            )
            self.add(support.result_group)
            self.paced(
                tracker,
                Create(support.policy_inputs),
                FadeIn(support.router),
                FadeIn(support.caution, shift=UP * 0.1),
                fraction=0.38,
                maximum=2.0,
            )
            self.add(support.policy_group)
            self.record_visual_event(
                f"route-selected:{support.selected_route}"
            )
