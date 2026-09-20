"""Small workflow visuals that require explicit topology and mappings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import math
from typing import TypeVar

import numpy as np
from manim import (
    LEFT,
    RIGHT,
    AnimationGroup,
    Dot,
    Indicate,
    Mobject,
    RoundedRectangle,
    Text,
    TransformFromCopy,
    VGroup,
)

from .theme import (
    ACCENT,
    NEUTRAL,
    PRIMARY,
    SPACING,
    STROKES,
    SURFACE,
    TEXT_PRIMARY,
)


class SystemNode(VGroup):
    """One named software component with visible input and output anchors."""

    def __init__(
        self,
        name: str,
        *,
        width: float = 2.2,
        height: float = 1.0,
        input_direction: np.ndarray = LEFT,
        output_direction: np.ndarray = RIGHT,
        font_size: float = 22,
    ) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("name must be a non-empty string")
        if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
            raise ValueError("node dimensions must be positive and finite")
        input_vector = self._validate_direction(input_direction, "input_direction")
        output_vector = self._validate_direction(output_direction, "output_direction")
        if np.allclose(input_vector, output_vector):
            raise ValueError("input and output anchors must be distinct")

        super().__init__()
        self.name = name
        self.body = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.14,
            fill_color=SURFACE,
            fill_opacity=0.96,
            stroke_color=PRIMARY.base,
            stroke_width=STROKES.normal.width,
        )
        self.label = Text(name, font_size=font_size, color=TEXT_PRIMARY)
        if self.label.width > width - 2 * SPACING.sm:
            self.label.scale_to_fit_width(width - 2 * SPACING.sm)
        if self.label.height > height - 2 * SPACING.sm:
            self.label.scale_to_fit_height(height - 2 * SPACING.sm)
        self.label.move_to(self.body)
        self.input_anchor = Dot(
            self.body.get_boundary_point(input_vector),
            radius=0.055,
            color=NEUTRAL.light,
        )
        self.output_anchor = Dot(
            self.body.get_boundary_point(output_vector),
            radius=0.055,
            color=ACCENT.base,
        )
        self.add(self.body, self.label, self.input_anchor, self.output_anchor)

    @staticmethod
    def _validate_direction(value: np.ndarray, name: str) -> np.ndarray:
        vector = np.asarray(value, dtype=float)
        if vector.shape != (3,) or not np.all(np.isfinite(vector)):
            raise ValueError(f"{name} must be a finite three-dimensional vector")
        norm = np.linalg.norm(vector)
        if norm == 0:
            raise ValueError(f"{name} must not be zero")
        return vector / norm

    @property
    def input_point(self) -> np.ndarray:
        return self.input_anchor.get_center()

    @property
    def output_point(self) -> np.ndarray:
        return self.output_anchor.get_center()


T = TypeVar("T")


def _explicit_mapping(
    value: Mapping[str, T] | Iterable[tuple[str, T]],
    role: str,
) -> dict[str, T]:
    if isinstance(value, Mapping):
        items = list(value.items())
    else:
        items = list(value)
    if not items:
        raise ValueError(f"{role} mapping must not be empty")
    result: dict[str, T] = {}
    for item in items:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(f"{role} must contain explicit (name, object) pairs")
        key, mapped = item
        if not isinstance(key, str) or not key:
            raise ValueError(f"{role} names must be non-empty strings")
        if key in result:
            raise ValueError(f"duplicate {role} mapping for {key!r}")
        result[key] = mapped
    return result


def animate_parallel_evaluation(
    sources: Mapping[str, Mobject] | Iterable[tuple[str, Mobject]],
    questions: Mapping[str, Mobject] | Iterable[tuple[str, Mobject]],
    results: Mapping[str, Mobject] | Iterable[tuple[str, Mobject]],
    *,
    indicate_scale: float = 1.08,
) -> AnimationGroup:
    """Animate explicitly matched evaluations concurrently.

    Every mapping must have exactly the same named keys. Objects must be unique
    across all roles, preventing one visual from ambiguously representing two
    lanes or two stages. Mapping iteration order is used only after key
    matching; no spatial or lexical ordering is inferred.
    """
    source_map = _explicit_mapping(sources, "source")
    question_map = _explicit_mapping(questions, "question")
    result_map = _explicit_mapping(results, "result")
    source_keys = set(source_map)
    if set(question_map) != source_keys or set(result_map) != source_keys:
        missing_questions = source_keys - set(question_map)
        missing_results = source_keys - set(result_map)
        extras = (set(question_map) | set(result_map)) - source_keys
        details = (
            f"missing questions={sorted(missing_questions)}, "
            f"missing results={sorted(missing_results)}, extras={sorted(extras)}"
        )
        raise ValueError(f"source/question/result mappings must match exactly: {details}")

    all_objects: list[Mobject] = []
    for key in source_map:
        lane = (source_map[key], question_map[key], result_map[key])
        if any(not isinstance(item, Mobject) for item in lane):
            raise TypeError("all mapped source, question, and result values must be Mobjects")
        all_objects.extend(lane)
    identities = [id(item) for item in all_objects]
    if len(set(identities)) != len(identities):
        raise ValueError("evaluation mappings are ambiguous because a Mobject is reused")

    lanes = []
    for key in source_map:
        lanes.append(
            AnimationGroup(
                Indicate(source_map[key], scale_factor=indicate_scale),
                Indicate(question_map[key], scale_factor=indicate_scale),
                TransformFromCopy(question_map[key], result_map[key]),
                lag_ratio=0,
            )
        )
    return AnimationGroup(*lanes, lag_ratio=0)


__all__ = ["SystemNode", "animate_parallel_evaluation"]
