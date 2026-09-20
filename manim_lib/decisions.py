"""Visual primitives for questions and their identity-stable decisions."""

from __future__ import annotations

from enum import Enum
import math
from typing import Any

import numpy as np
from manim import DOWN, LEFT, RIGHT, RoundedRectangle, Text, VGroup

from .probability import ProbabilityDistribution
from .state import ContentPolicy, _display, _make_fitted_text, _replace_text
from .theme import (
    ACCENT,
    DANGER,
    NEUTRAL,
    PRIMARY,
    SPACING,
    STROKES,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class QuestionKind(str, Enum):
    CHOICE = "choice"
    SCORE = "score"
    NOUL = "noul"


class DecisionState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    RESOLVED = "resolved"
    ABSTAINED = "abstained"


_DECISION_COLORS = {
    DecisionState.PENDING: NEUTRAL.base,
    DecisionState.ACTIVE: ACCENT.base,
    DecisionState.RESOLVED: SUCCESS.base,
    DecisionState.ABSTAINED: DANGER.base,
}


class QuestionCard(VGroup):
    """One question shape shared by choice, score, and NOUL constructors."""

    def __init__(
        self,
        key: str,
        instruction: str,
        kind: QuestionKind,
        output_space: str,
        *,
        active: bool = False,
        width: float = 5.6,
        height: float = 1.55,
        font_size: float = 22,
        content_policy: ContentPolicy | str = ContentPolicy.WRAP,
    ) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("question key must be a non-empty string")
        if not isinstance(instruction, str) or not instruction:
            raise ValueError("instruction must be a non-empty string")
        if not isinstance(output_space, str) or not output_space:
            raise ValueError("output_space must be a non-empty string")
        if not isinstance(kind, QuestionKind):
            raise TypeError("kind must be a QuestionKind")
        if not all(math.isfinite(v) and v > 0 for v in (width, height, font_size)):
            raise ValueError("card dimensions and font size must be positive and finite")
        super().__init__()
        self.key = key
        self.instruction = instruction
        self.kind = kind
        self.output_space = output_space
        self.active = active

        self.card = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.14,
            fill_color=SURFACE,
            fill_opacity=0.96,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.normal.width,
        )
        self.kind_badge = RoundedRectangle(
            width=1.0,
            height=0.34,
            corner_radius=0.08,
            fill_color=SURFACE_ELEVATED,
            fill_opacity=1,
            stroke_color=PRIMARY.dim,
            stroke_width=STROKES.hairline.width,
        )
        self.kind_label = _make_fitted_text(
            kind.value.upper(),
            font_size=14,
            color=PRIMARY.light,
            max_width=0.82,
            max_height=0.22,
            policy=ContentPolicy.FIT,
            max_lines=1,
        ).move_to(self.kind_badge)
        self.key_label = _make_fitted_text(
            key,
            font_size=16,
            color=TEXT_SECONDARY,
            max_width=width - 1.5,
            max_height=0.25,
            policy=ContentPolicy.FIT,
            max_lines=1,
        )
        self.instruction_label = _make_fitted_text(
            instruction,
            font_size=font_size,
            color=TEXT_PRIMARY,
            max_width=width - 2 * SPACING.sm,
            max_height=0.55,
            policy=ContentPolicy(content_policy),
            max_lines=2,
        )
        self.output_label = _make_fitted_text(
            output_space,
            font_size=max(14, font_size - 6),
            color=TEXT_SECONDARY,
            max_width=width - 2 * SPACING.sm,
            max_height=0.25,
            policy=ContentPolicy.FIT,
            max_lines=1,
        )

        top = self.card.get_top()[1]
        left = self.card.get_left()[0]
        self.kind_badge.move_to(
            np.array([left + SPACING.sm + self.kind_badge.width / 2, top - 0.25, 0])
        )
        self.kind_label.move_to(self.kind_badge)
        self.key_label.next_to(self.kind_badge, RIGHT, buff=SPACING.xs)
        self.instruction_label.move_to(self.card)
        self.output_label.move_to(
            np.array([self.card.get_center()[0], self.card.get_bottom()[1] + 0.23, 0])
        )
        self.add(
            self.card,
            self.kind_badge,
            self.kind_label,
            self.key_label,
            self.instruction_label,
            self.output_label,
        )
        self.set_active(active)

    @classmethod
    def choice(
        cls, key: str, instruction: str, options, **kwargs
    ) -> "QuestionCard":
        values = tuple(options)
        if not values:
            raise ValueError("choice questions require at least one option")
        return cls(
            key,
            instruction,
            QuestionKind.CHOICE,
            "choices: " + " | ".join(map(str, values)),
            **kwargs,
        )

    @classmethod
    def score(
        cls,
        key: str,
        instruction: str,
        score_range: tuple[float, float] = (0.0, 1.0),
        **kwargs,
    ) -> "QuestionCard":
        if (
            len(score_range) != 2
            or not all(math.isfinite(v) for v in score_range)
            or score_range[0] >= score_range[1]
        ):
            raise ValueError("score_range must contain two increasing finite values")
        return cls(
            key,
            instruction,
            QuestionKind.SCORE,
            f"score: [{score_range[0]:g}, {score_range[1]:g}]",
            **kwargs,
        )

    @classmethod
    def noul(
        cls,
        key: str,
        instruction: str,
        output_space: str = "truth likelihood: [0, 1]",
        **kwargs,
    ) -> "QuestionCard":
        return cls(key, instruction, QuestionKind.NOUL, output_space, **kwargs)

    @property
    def input_anchor(self) -> np.ndarray:
        return self.card.get_left()

    @property
    def output_anchor(self) -> np.ndarray:
        return self.card.get_right()

    def set_active(self, active: bool = True) -> "QuestionCard":
        if not isinstance(active, bool):
            raise TypeError("active must be a bool")
        self.active = active
        self.card.set_stroke(
            ACCENT.base if active else NEUTRAL.dim,
            width=STROKES.heavy.width if active else STROKES.normal.width,
        )
        self.card.set_fill(
            ACCENT.base if active else SURFACE,
            opacity=0.13 if active else 0.96,
        )
        self.instruction_label.set_color(TEXT_PRIMARY if active else TEXT_SECONDARY)
        return self


class DecisionResult(VGroup):
    """A typed answer linked to a source question and optional evidence."""

    def __init__(
        self,
        source_question_key: str,
        answer: Any = None,
        *,
        answer_type: type | tuple[type, ...] | None = None,
        distribution: ProbabilityDistribution | None = None,
        confidence: float | None = None,
        state: DecisionState = DecisionState.PENDING,
        width: float = 4.8,
        height: float = 1.15,
        font_size: float = 22,
    ) -> None:
        if not isinstance(source_question_key, str) or not source_question_key:
            raise ValueError("source_question_key must be a non-empty string")
        if not isinstance(state, DecisionState):
            raise TypeError("state must be a DecisionState")
        if not all(math.isfinite(v) and v > 0 for v in (width, height, font_size)):
            raise ValueError("result dimensions and font size must be positive and finite")
        self._validate_confidence(confidence)
        self._validate_answer(answer, answer_type)
        if distribution is not None and not isinstance(
            distribution, ProbabilityDistribution
        ):
            raise TypeError("distribution must be a ProbabilityDistribution")
        super().__init__()
        self.source_question_key = source_question_key
        self.answer = answer
        self.answer_type = answer_type
        self.distribution = distribution
        self.confidence = confidence
        self.state = state
        self._width = width
        self._height = height
        self._font_size = font_size

        self.card = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.14,
            fill_color=SURFACE,
            fill_opacity=0.96,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.normal.width,
        )
        self.source_label = _make_fitted_text(
            f"from {source_question_key}",
            font_size=15,
            color=TEXT_MUTED,
            max_width=width - 2 * SPACING.sm,
            max_height=0.22,
            policy=ContentPolicy.FIT,
            max_lines=1,
        )
        self.answer_label = _make_fitted_text(
            self._answer_display(answer),
            font_size=font_size,
            color=TEXT_PRIMARY,
            max_width=width * 0.65,
            max_height=0.36,
            policy=ContentPolicy.FIT,
            max_lines=1,
        )
        self.type_label = _make_fitted_text(
            self._type_display(answer),
            font_size=14,
            color=PRIMARY.light,
            max_width=width * 0.22,
            max_height=0.22,
            policy=ContentPolicy.FIT,
            max_lines=1,
        )
        self.confidence_label = Text("", font_size=14, color=TEXT_SECONDARY)
        self._position_labels()
        self.add(
            self.card,
            self.source_label,
            self.answer_label,
            self.type_label,
            self.confidence_label,
        )
        if distribution is not None:
            distribution.next_to(self.card, DOWN, buff=SPACING.sm)
            self.add(distribution)
        self.set_confidence(confidence)
        self.set_state(state)

    @staticmethod
    def _validate_confidence(confidence: float | None) -> None:
        if confidence is not None and (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            raise ValueError("confidence must be finite and between 0 and 1")

    @staticmethod
    def _validate_answer(
        answer: Any, answer_type: type | tuple[type, ...] | None
    ) -> None:
        if answer_type is not None and not isinstance(answer_type, (type, tuple)):
            raise TypeError("answer_type must be a type or tuple of types")
        if isinstance(answer_type, tuple) and (
            not answer_type or not all(isinstance(kind, type) for kind in answer_type)
        ):
            raise TypeError("answer_type tuples must contain at least one type")
        if (
            answer is not None
            and answer_type is not None
            and not isinstance(answer, answer_type)
        ):
            raise TypeError("answer does not match answer_type")

    def _answer_display(self, answer: Any) -> str:
        return "pending" if answer is None else _display(answer)

    def _type_display(self, answer: Any) -> str:
        if self.answer_type is not None:
            if isinstance(self.answer_type, tuple):
                return " | ".join(kind.__name__ for kind in self.answer_type)
            return self.answer_type.__name__
        return "—" if answer is None else type(answer).__name__

    def _position_labels(self) -> None:
        self.source_label.move_to(
            self.card.get_top() + DOWN * 0.2
        )
        self.answer_label.move_to(self.card.get_center() + LEFT * 0.35)
        self.type_label.move_to(
            self.card.get_right() + LEFT * (SPACING.sm + self.type_label.width / 2)
        )
        self.confidence_label.move_to(
            self.card.get_bottom() + np.array([0, 0.16, 0])
        )

    @property
    def input_anchor(self) -> np.ndarray:
        return self.card.get_left()

    @property
    def output_anchor(self) -> np.ndarray:
        return self.card.get_right()

    def set_answer(self, answer: Any) -> "DecisionResult":
        """Set a type-checked answer without replacing semantic mobjects."""
        self._validate_answer(answer, self.answer_type)
        scale = self.card.height / self._height
        answer_text = _make_fitted_text(
            self._answer_display(answer),
            font_size=self._font_size,
            color=self.answer_label[0].get_color(),
            max_width=self._width * 0.65,
            max_height=0.36,
            policy=ContentPolicy.FIT,
            max_lines=1,
        ).scale(scale)
        type_text = _make_fitted_text(
            self._type_display(answer),
            font_size=14,
            color=self.type_label[0].get_color(),
            max_width=self._width * 0.22,
            max_height=0.22,
            policy=ContentPolicy.FIT,
            max_lines=1,
        ).scale(scale)
        _replace_text(self.answer_label, answer_text, self.answer_label.get_center())
        _replace_text(self.type_label, type_text, self.type_label.get_center())
        self.answer = answer
        return self

    def set_confidence(self, confidence: float | None) -> "DecisionResult":
        """Show or clear optional confidence without creating a new label."""
        self._validate_confidence(confidence)
        text = "" if confidence is None else f"confidence {confidence:.0%}"
        scale = self.card.height / self._height
        replacement = _make_fitted_text(
            text,
            font_size=14,
            color=TEXT_SECONDARY,
            max_width=self._width - 2 * SPACING.sm,
            max_height=0.2,
            policy=ContentPolicy.FIT,
            max_lines=1,
        ).scale(scale)
        replacement.set_opacity(0 if confidence is None else 1)
        _replace_text(
            self.confidence_label, replacement, self.confidence_label.get_center()
        )
        self.confidence = confidence
        return self

    def set_state(self, state: DecisionState) -> "DecisionResult":
        if not isinstance(state, DecisionState):
            raise TypeError("state must be a DecisionState")
        color = _DECISION_COLORS[state]
        self.state = state
        self.card.set_stroke(
            color,
            width=STROKES.heavy.width
            if state is DecisionState.ACTIVE
            else STROKES.normal.width,
        )
        self.card.set_fill(
            color if state is not DecisionState.PENDING else SURFACE,
            opacity=0.14 if state is not DecisionState.PENDING else 0.96,
        )
        self.answer_label.set_color(
            DANGER.light if state is DecisionState.ABSTAINED else TEXT_PRIMARY
        )
        return self


__all__ = [
    "DecisionResult",
    "DecisionState",
    "QuestionCard",
    "QuestionKind",
]
