"""Stable, keyed visualizations of structured software state."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum
import math
import textwrap
from typing import Any

from manim import DOWN, LEFT, RIGHT, RoundedRectangle, Text, VGroup

from .theme import (
    ACCENT,
    NEUTRAL,
    SPACING,
    STROKES,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ContentPolicy(str, Enum):
    """How text that is wider than its allotted region is handled."""

    FIT = "fit"
    WRAP = "wrap"


def _coerce_policy(policy: ContentPolicy | str) -> ContentPolicy:
    try:
        return ContentPolicy(policy)
    except ValueError as exc:
        raise ValueError("content_policy must be 'fit' or 'wrap'") from exc


def _display(value: Any) -> str:
    return "None" if value is None else str(value)


def _make_fitted_text(
    text: str,
    *,
    font_size: float,
    color: str,
    max_width: float,
    max_height: float,
    policy: ContentPolicy,
    max_lines: int,
) -> Text:
    if max_width <= 0 or max_height <= 0:
        raise ValueError("text bounds must be positive")
    rendered = text
    if policy is ContentPolicy.WRAP and text:
        if max_lines < 1:
            raise ValueError("max_lines must be at least 1")
        # Text width is font-dependent, so wrapping is a readable first pass;
        # the geometric fit below remains the authoritative containment rule.
        chars = max(1, math.ceil(len(text) / max_lines))
        lines = textwrap.wrap(
            text, width=chars, break_long_words=True, break_on_hyphens=True
        )
        if len(lines) > max_lines:
            lines = [*lines[: max_lines - 1], " ".join(lines[max_lines - 1 :])]
        rendered = "\n".join(lines)
    label = Text(rendered, font_size=font_size, color=color)
    factor = min(
        1.0,
        max_width / label.width if label.width else 1.0,
        max_height / label.height if label.height else 1.0,
    )
    if factor < 1:
        label.scale(factor)
    return label


def _replace_text(target: Text, replacement: Text, center) -> None:
    replacement.move_to(center)
    target.become(replacement)
    target.text = replacement.text


class StateField(VGroup):
    """One fixed-size, addressable row in a :class:`StructuredState`."""

    def __init__(
        self,
        key: str,
        label: str,
        value: Any,
        type_badge: str | None = None,
        *,
        width: float = 5.4,
        height: float = 0.72,
        font_size: float = 22,
        content_policy: ContentPolicy | str = ContentPolicy.FIT,
        max_lines: int = 2,
    ) -> None:
        if not isinstance(key, str) or not key:
            raise ValueError("field key must be a non-empty string")
        if not isinstance(label, str) or not label:
            raise ValueError("field label must be a non-empty string")
        if not all(math.isfinite(v) and v > 0 for v in (width, height, font_size)):
            raise ValueError("field dimensions and font size must be positive and finite")
        policy = _coerce_policy(content_policy)
        if max_lines < 1:
            raise ValueError("max_lines must be at least 1")
        super().__init__()
        self.key = key
        self.label_text = label
        self.value = value
        self.type_name = type_badge or type(value).__name__
        self.content_policy = policy
        self.max_lines = max_lines
        self._width = width
        self._height = height
        self._font_size = font_size
        self.highlighted = False

        self.background = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=min(0.12, height * 0.2),
            fill_color=SURFACE,
            fill_opacity=0.96,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.normal.width,
        )
        label_width = width * 0.25
        badge_width = min(width * 0.22, max(0.72, width * 0.16))
        value_width = width - label_width - badge_width - 4 * SPACING.xs
        if value_width <= 0:
            raise ValueError("field width is too small for its columns")
        self._value_width = value_width

        self.label = _make_fitted_text(
            label,
            font_size=font_size,
            color=TEXT_SECONDARY,
            max_width=label_width,
            max_height=height - 2 * SPACING.xs,
            policy=policy,
            max_lines=max_lines,
        )
        self.value_label = _make_fitted_text(
            _display(value),
            font_size=font_size,
            color=TEXT_PRIMARY,
            max_width=value_width,
            max_height=height - 2 * SPACING.xs,
            policy=policy,
            max_lines=max_lines,
        )
        self.badge = RoundedRectangle(
            width=badge_width,
            height=height * 0.48,
            corner_radius=min(0.09, height * 0.14),
            fill_color=SURFACE_ELEVATED,
            fill_opacity=1,
            stroke_color=NEUTRAL.base,
            stroke_width=STROKES.hairline.width,
        )
        self.type_badge = _make_fitted_text(
            self.type_name,
            font_size=max(12, font_size - 7),
            color=TEXT_SECONDARY,
            max_width=badge_width - SPACING.xs,
            max_height=self.badge.height * 0.65,
            policy=ContentPolicy.FIT,
            max_lines=1,
        ).move_to(self.badge)

        self.label.move_to(self.background.get_left() + RIGHT * (SPACING.xs + label_width / 2))
        self.value_label.move_to(
            self.background.get_left()
            + RIGHT * (2 * SPACING.xs + label_width + value_width / 2)
        )
        self.badge.move_to(
            self.background.get_right() - RIGHT * (SPACING.xs + badge_width / 2)
        )
        self.type_badge.move_to(self.badge)
        self.add(
            self.background, self.label, self.value_label, self.badge, self.type_badge
        )

    def set_value(self, value: Any) -> "StateField":
        """Update only this row's value while retaining every mobject identity."""
        text = _display(value)
        scale = self.background.height / self._height
        replacement = _make_fitted_text(
            text,
            font_size=self._font_size,
            color=self.value_label.get_color(),
            max_width=self._value_width,
            max_height=self._height - 2 * SPACING.xs,
            policy=self.content_policy,
            max_lines=self.max_lines,
        ).scale(scale)
        replacement.set_opacity(self.value_label.get_fill_opacity())
        _replace_text(self.value_label, replacement, self.value_label.get_center())
        self.value = value
        return self

    def set_highlighted(
        self, highlighted: bool = True, color: str = ACCENT.base
    ) -> "StateField":
        """Set the row's emphasis without changing its geometry."""
        if not isinstance(highlighted, bool):
            raise TypeError("highlighted must be a bool")
        self.highlighted = highlighted
        self.background.set_stroke(
            color if highlighted else NEUTRAL.dim,
            width=STROKES.heavy.width if highlighted else STROKES.normal.width,
        )
        self.background.set_fill(
            color if highlighted else SURFACE,
            opacity=0.16 if highlighted else 0.96,
        )
        return self

    def highlight(self, color: str = ACCENT.base) -> "StateField":
        return self.set_highlighted(True, color)


class StructuredState(VGroup):
    """An ordered mapping of stable :class:`StateField` rows."""

    def __init__(
        self,
        fields: Mapping[str, tuple[str, Any] | tuple[str, Any, str] | Any]
        | Iterable[StateField] = (),
        *,
        width: float = 5.4,
        field_height: float = 0.72,
        field_buff: float = SPACING.xs,
        font_size: float = 22,
        content_policy: ContentPolicy | str = ContentPolicy.FIT,
        max_lines: int = 2,
    ) -> None:
        super().__init__()
        if not math.isfinite(field_buff) or field_buff < 0:
            raise ValueError("field_buff must be nonnegative and finite")
        self.fields: dict[str, StateField] = {}
        self.field_buff = field_buff
        self._field_kwargs = {
            "width": width,
            "height": field_height,
            "font_size": font_size,
            "content_policy": _coerce_policy(content_policy),
            "max_lines": max_lines,
        }
        rows: list[StateField] = []
        if isinstance(fields, Mapping):
            for key, spec in fields.items():
                if isinstance(spec, tuple):
                    if len(spec) == 2:
                        label, value = spec
                        badge = None
                    elif len(spec) == 3:
                        label, value, badge = spec
                    else:
                        raise ValueError("field tuples must contain label, value[, type]")
                else:
                    label, value, badge = key, spec, None
                rows.append(
                    StateField(
                        key, label, value, badge, **self._field_kwargs
                    )
                )
        else:
            rows = list(fields)
            if not all(isinstance(row, StateField) for row in rows):
                raise TypeError("fields must be a mapping or StateField iterable")
        for row in rows:
            if row.key in self.fields:
                raise ValueError(f"duplicate state field key: {row.key!r}")
            self.fields[row.key] = row
            self.add(row)
        if rows:
            self.arrange(DOWN, buff=field_buff, aligned_edge=LEFT)

    def __getitem__(self, key: str) -> StateField:
        return self.fields[key]

    def set_value(self, key: str, value: Any) -> "StructuredState":
        """Update an existing key; unknown keys are never added implicitly."""
        if key not in self.fields:
            raise KeyError(f"No state field with key: {key!r}")
        self.fields[key].set_value(value)
        return self

    def highlight_field(
        self, key: str, color: str = ACCENT.base
    ) -> StateField:
        if key not in self.fields:
            raise KeyError(f"No state field with key: {key!r}")
        return self.fields[key].highlight(color)

    def add_field(
        self,
        field_or_key: StateField | str,
        label: str | None = None,
        value: Any = None,
        type_badge: str | None = None,
    ) -> StateField:
        """Append a row without rearranging or replacing existing rows."""
        if isinstance(field_or_key, StateField):
            if label is not None or type_badge is not None:
                raise TypeError("label/type_badge are invalid when adding a StateField")
            field = field_or_key
        else:
            key = field_or_key
            if key in self.fields:
                raise ValueError(f"duplicate state field key: {key!r}")
            if label is None:
                raise ValueError("label is required when adding by key")
            field = StateField(
                key, label, value, type_badge, **self._field_kwargs
            )
        if field.key in self.fields:
            raise ValueError(f"duplicate state field key: {field.key!r}")

        if self.fields:
            previous = next(reversed(self.fields.values()))
            scale = previous.background.height / field.background.height
            field.scale(scale)
            field.next_to(previous, DOWN, buff=self.field_buff * scale)
            field.align_to(previous, LEFT)
        self.fields[field.key] = field
        self.add(field)
        return field


__all__ = ["ContentPolicy", "StateField", "StructuredState"]
