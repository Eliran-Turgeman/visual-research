"""Visual contracts for structural output validity."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from manim import DOWN, RIGHT, RoundedRectangle, Text, VGroup

from .state import ContentPolicy, _make_fitted_text
from .theme import (
    DANGER,
    NEUTRAL,
    SPACING,
    STROKES,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def _same_value(left: Any, right: Any) -> bool:
    """Use both type and equality so ``1`` is not silently the option ``True``."""
    return type(left) is type(right) and left == right


class OptionSet(VGroup):
    """An ordered, explicit set of structurally allowed values."""

    def __init__(
        self,
        values: Iterable[Any],
        *,
        label: str = "allowed",
        option_width: float = 1.25,
        option_height: float = 0.48,
        font_size: float = 18,
    ) -> None:
        declared = tuple(values)
        if not declared:
            raise ValueError("OptionSet requires at least one declared value")
        if any(
            _same_value(value, previous)
            for index, value in enumerate(declared)
            for previous in declared[:index]
        ):
            raise ValueError("OptionSet values must be unique")
        super().__init__()
        self.values = declared
        self.declared_values = declared
        self.highlighted_value: Any = None
        self.violating_value: Any = None
        self.label = Text(label, font_size=15, color=TEXT_SECONDARY)
        self.options: list[VGroup] = []
        for value in declared:
            box = RoundedRectangle(
                width=option_width,
                height=option_height,
                corner_radius=0.09,
                fill_color=SURFACE_ELEVATED,
                fill_opacity=1,
                stroke_color=NEUTRAL.dim,
                stroke_width=STROKES.hairline.width,
            )
            text = _make_fitted_text(
                str(value),
                font_size=font_size,
                color=TEXT_PRIMARY,
                max_width=option_width - 2 * SPACING.xs,
                max_height=option_height * 0.62,
                policy=ContentPolicy.FIT,
                max_lines=1,
            ).move_to(box)
            option = VGroup(box, text)
            option.value = value
            option.box = box
            option.label = text
            self.options.append(option)
        self.option_group = VGroup(*self.options).arrange(RIGHT, buff=SPACING.xs)
        self.label.next_to(self.option_group, DOWN, buff=SPACING.xs)
        self.violation_label = Text("", font_size=15, color=DANGER.light).next_to(
            self.label, DOWN, buff=SPACING.xs
        )
        self.add(self.option_group, self.label, self.violation_label)

    def accepts(self, value: Any) -> bool:
        """Return structural membership; no quality or correctness is implied."""
        return any(_same_value(value, declared) for declared in self.values)

    def highlight_allowed(self, value: Any | None = None) -> "OptionSet":
        """Highlight allowed values, or one matching allowed value.

        Passing a non-member applies the violation treatment instead.
        """
        if value is not None and not self.accepts(value):
            return self.show_violation(value)
        self.highlighted_value = value
        self.violating_value = None
        self.violation_label.set_opacity(0)
        for option in self.options:
            selected = value is None or _same_value(option.value, value)
            option.box.set_stroke(
                SUCCESS.base if selected else NEUTRAL.dim,
                width=STROKES.heavy.width if selected else STROKES.hairline.width,
            )
            option.box.set_fill(
                SUCCESS.base if selected else SURFACE_ELEVATED,
                opacity=0.18 if selected else 1,
            )
        return self

    def show_violation(self, value: Any) -> "OptionSet":
        """Apply an explicit red treatment for a structurally invalid value."""
        text = f"{value!s} is outside the declared set"
        replacement = _make_fitted_text(
            text,
            font_size=15,
            color=DANGER.light,
            max_width=max(self.option_group.width, 1),
            max_height=0.25,
            policy=ContentPolicy.FIT,
            max_lines=1,
        ).move_to(self.violation_label)
        self.violation_label.become(replacement)
        self.violation_label.text = replacement.text
        self.violation_label.set_opacity(1)
        self.highlighted_value = None
        self.violating_value = value
        for option in self.options:
            option.box.set_stroke(DANGER.base, width=STROKES.normal.width)
            option.box.set_fill(SURFACE, opacity=0.72)
        return self


class SchemaBoundary(VGroup):
    """A visual boundary around an explicit structural value contract."""

    def __init__(
        self,
        name: str,
        declared_values: Iterable[Any] | OptionSet,
        *,
        width: float | None = None,
    ) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("schema name must be a non-empty string")
        option_set = (
            declared_values
            if isinstance(declared_values, OptionSet)
            else OptionSet(declared_values)
        )
        super().__init__()
        self.name = name
        self.option_set = option_set
        self.declared_values = option_set.declared_values
        boundary_width = width or option_set.width + 2 * SPACING.sm
        if boundary_width < option_set.width + 2 * SPACING.xs:
            raise ValueError("boundary width is too small for the option set")
        self.boundary = RoundedRectangle(
            width=boundary_width,
            height=option_set.height + 2 * SPACING.sm,
            corner_radius=0.14,
            fill_color=SURFACE,
            fill_opacity=0.5,
            stroke_color=NEUTRAL.base,
            stroke_width=STROKES.normal.width,
        )
        self.title = _make_fitted_text(
            name,
            font_size=17,
            color=TEXT_SECONDARY,
            max_width=boundary_width - 2 * SPACING.sm,
            max_height=0.25,
            policy=ContentPolicy.FIT,
            max_lines=1,
        )
        option_set.move_to(self.boundary)
        self.title.next_to(self.boundary.get_top(), DOWN, buff=SPACING.xs)
        option_set.shift(DOWN * SPACING.xs)
        self.add(self.boundary, self.title, option_set)
        self.violating = False

    def accepts(self, value: Any) -> bool:
        return self.option_set.accepts(value)

    def highlight_allowed(self, value: Any | None = None) -> "SchemaBoundary":
        self.option_set.highlight_allowed(value)
        self.violating = value is not None and not self.accepts(value)
        color = DANGER.base if self.violating else SUCCESS.base
        self.boundary.set_stroke(color, width=STROKES.heavy.width)
        self.boundary.set_fill(color, opacity=0.1)
        return self

    def show_violation(self, value: Any) -> "SchemaBoundary":
        self.option_set.show_violation(value)
        self.violating = True
        self.boundary.set_stroke(DANGER.base, width=STROKES.heavy.width)
        self.boundary.set_fill(DANGER.base, opacity=0.12)
        return self


__all__ = ["OptionSet", "SchemaBoundary"]
