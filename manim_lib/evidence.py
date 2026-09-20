"""Evidence-aware metric, comparison, and calibration visual primitives."""

from __future__ import annotations

from collections.abc import Mapping
import math

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Axes,
    DashedLine,
    Dot,
    Line,
    Rectangle,
    RoundedRectangle,
    Text,
    VGroup,
)

from .theme import (
    ACCENT,
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


PROVENANCE_LABELS = {
    "toy": "TOY EXAMPLE",
    "measured": "MEASURED",
    "vendor_reported": "VENDOR-REPORTED",
}
_UNCHANGED = object()


def _provenance(value: str) -> str:
    if value not in PROVENANCE_LABELS:
        raise ValueError("provenance must be toy, measured, or vendor_reported")
    return value


def _finite(value: float, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _unit(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("unit must be a nonempty string")
    return value


def _fit(mobject: Text, width: float, height: float) -> Text:
    factor = min(
        1.0,
        width / mobject.width if mobject.width else 1.0,
        height / mobject.height if mobject.height else 1.0,
    )
    if factor < 1:
        mobject.scale(factor)
    return mobject


def _replace(
    current: Text,
    text: str,
    *,
    font_size: float,
    color,
    width: float,
    height: float,
) -> None:
    replacement = Text(text if text else " ", font_size=font_size, color=color)
    _fit(replacement, width, height)
    replacement.move_to(current)
    current.become(replacement)
    current.text = text


def _format_number(value: float) -> str:
    return f"{value:g}"


class MetricCard(VGroup):
    """A metric whose label, value, unit, and provenance remain visibly bound."""

    def __init__(
        self,
        label: str,
        value: float | str,
        unit: str,
        provenance: str,
        *,
        width: float = 3.0,
        height: float = 1.7,
    ) -> None:
        if not isinstance(label, str) or not label.strip():
            raise ValueError("label must be a nonempty string")
        unit = _unit(unit)
        provenance = _provenance(provenance)
        if isinstance(value, float):
            _finite(value, "value")
        if not isinstance(value, (str, int, float)):
            raise TypeError("value must be text or a finite number")
        if not math.isfinite(width) or not math.isfinite(height) or width <= 0 or height <= 0:
            raise ValueError("card dimensions must be positive and finite")
        super().__init__()
        self.value = value
        self.unit = unit
        self.metric_label = label
        self.provenance = provenance
        self.panel = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.16,
            fill_color=SURFACE_ELEVATED,
            fill_opacity=0.98,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.normal.width,
        )
        self.value_label = Text(str(value), font_size=38, color=TEXT_PRIMARY)
        self.unit_label = Text(unit, font_size=20, color=TEXT_SECONDARY)
        value_group = VGroup(self.value_label, self.unit_label).arrange(
            RIGHT, buff=SPACING.xs, aligned_edge=DOWN
        )
        _fit(value_group, width - 2 * SPACING.sm, height * 0.38)
        self.label = Text(label, font_size=21, color=TEXT_SECONDARY)
        _fit(self.label, width - 2 * SPACING.sm, height * 0.2)
        self.provenance_label = Text(
            PROVENANCE_LABELS[provenance], font_size=13, color=ACCENT.light
        )
        _fit(self.provenance_label, width - 2 * SPACING.sm, height * 0.13)
        value_group.move_to(self.panel).shift(UP * height * 0.16)
        self.label.next_to(value_group, DOWN, buff=SPACING.xs)
        self.provenance_label.next_to(
            self.panel.get_bottom(), UP, buff=SPACING.xs
        )
        self.add(
            self.panel,
            self.value_label,
            self.unit_label,
            self.label,
            self.provenance_label,
        )

    def update(
        self,
        dt: float = 0,
        recursive: bool = True,
        *,
        value: float | str | object = _UNCHANGED,
        unit: str | object = _UNCHANGED,
        label: str | object = _UNCHANGED,
        provenance: str | object = _UNCHANGED,
    ) -> "MetricCard":
        """Update metric fields, while remaining compatible with Manim updaters."""
        if all(
            field is _UNCHANGED for field in (value, unit, label, provenance)
        ):
            return super().update(dt=dt, recursive=recursive)
        next_value = self.value if value is _UNCHANGED else value
        next_unit = self.unit if unit is _UNCHANGED else _unit(unit)
        next_label = self.metric_label if label is _UNCHANGED else label
        next_provenance = (
            self.provenance if provenance is _UNCHANGED else _provenance(provenance)
        )
        if not isinstance(next_label, str) or not next_label.strip():
            raise ValueError("label must be a nonempty string")
        if isinstance(next_value, float):
            _finite(next_value, "value")
        if not isinstance(next_value, (str, int, float)):
            raise TypeError("value must be text or a finite number")

        scale = self.panel.height / 1.7
        _replace(
            self.value_label,
            str(next_value),
            font_size=38,
            color=self.value_label[0].get_color(),
            width=self.panel.width * 0.62,
            height=self.panel.height * 0.32,
        )
        _replace(
            self.unit_label,
            next_unit,
            font_size=20,
            color=TEXT_SECONDARY,
            width=self.panel.width * 0.28,
            height=self.panel.height * 0.18,
        )
        value_group = VGroup(self.value_label, self.unit_label).arrange(
            RIGHT, buff=SPACING.xs * scale, aligned_edge=DOWN
        ).move_to(self.panel).shift(UP * self.panel.height * 0.16)
        _replace(
            self.label,
            next_label,
            font_size=21,
            color=TEXT_SECONDARY,
            width=self.panel.width - 2 * SPACING.sm * scale,
            height=self.panel.height * 0.2,
        )
        self.label.next_to(value_group, DOWN, buff=SPACING.xs * scale)
        _replace(
            self.provenance_label,
            PROVENANCE_LABELS[next_provenance],
            font_size=13,
            color=ACCENT.light,
            width=self.panel.width - 2 * SPACING.sm * scale,
            height=self.panel.height * 0.13,
        )
        self.provenance_label.next_to(
            self.panel.get_bottom(), UP, buff=SPACING.xs * scale
        )
        self.value = next_value
        self.unit = next_unit
        self.metric_label = next_label
        self.provenance = next_provenance
        return self

    def set_value(self, value: float | str) -> "MetricCard":
        """Convenience update suitable for ``card.animate.set_value(...)``."""
        return self.update(value=value)


class ComparisonEntry(VGroup):
    """One stable value row on a shared zero-based comparison scale."""

    def __init__(
        self,
        key: str,
        label: str,
        value: float,
        provenance: str,
        *,
        unit: str,
        maximum: float,
        track_width: float,
        bar_height: float,
        font_size: float,
    ) -> None:
        super().__init__()
        self.key = key
        self.value = value
        self.provenance = provenance
        self.label = Text(label, font_size=font_size, color=TEXT_PRIMARY)
        _fit(self.label, 2.0, bar_height * 0.8)
        self.track = Rectangle(
            width=track_width,
            height=bar_height,
            fill_color=SURFACE,
            fill_opacity=0.9,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.hairline.width,
        )
        self.value_label = Text(
            f"{_format_number(value)} {unit}",
            font_size=max(13, font_size * 0.75),
            color=TEXT_SECONDARY,
        )
        self.provenance_label = Text(
            PROVENANCE_LABELS[provenance],
            font_size=max(10, font_size * 0.5),
            color=ACCENT.light,
        )
        evidence = VGroup(self.value_label, self.provenance_label).arrange(
            DOWN, buff=0.04, aligned_edge=LEFT
        )
        self.track.next_to(self.label, RIGHT, buff=SPACING.sm)
        self.bar = self.track.copy().set_fill(PRIMARY.base, opacity=0.78).set_stroke(width=0)
        self.bar.stretch(value / maximum, 0, about_point=self.track.get_left())
        evidence.next_to(self.track, RIGHT, buff=SPACING.xs)
        self.add(
            self.label,
            self.track,
            self.bar,
            self.value_label,
            self.provenance_label,
        )


class ComparisonScale(VGroup):
    """Multiple values encoded proportionally on one explicit zero-based scale.

    ``values`` maps keys to ``(label, value, provenance)``. Every bar shares
    the same track and maximum; the visible axis labels include zero, avoiding
    any truncated-axis implication.
    """

    def __init__(
        self,
        values: Mapping[str, tuple[str, float, str]],
        *,
        unit: str,
        maximum: float | None = None,
        track_width: float = 3.2,
        bar_height: float = 0.3,
        font_size: float = 19,
    ) -> None:
        if not values:
            raise ValueError("values must not be empty")
        unit = _unit(unit)
        normalized = {}
        for key, item in values.items():
            if not isinstance(key, str) or not isinstance(item, tuple) or len(item) != 3:
                raise ValueError("values must map string keys to (label, value, provenance)")
            label, value, provenance = item
            if not isinstance(label, str) or not label.strip():
                raise ValueError("comparison labels must be nonempty strings")
            value = _finite(value, "comparison value")
            if value < 0:
                raise ValueError("comparison values must be nonnegative")
            normalized[key] = (label, value, _provenance(provenance))
        maximum = max(value for _, value, _ in normalized.values()) if maximum is None else _finite(maximum, "maximum")
        if maximum <= 0:
            raise ValueError("maximum must be positive")
        if any(value > maximum for _, value, _ in normalized.values()):
            raise ValueError("comparison values cannot exceed maximum")
        if track_width <= 0 or bar_height <= 0:
            raise ValueError("bar dimensions must be positive")
        super().__init__()
        self.unit = unit
        self.maximum = maximum
        self.entries: dict[str, ComparisonEntry] = {
            key: ComparisonEntry(
                key,
                label,
                value,
                provenance,
                unit=unit,
                maximum=maximum,
                track_width=track_width,
                bar_height=bar_height,
                font_size=font_size,
            )
            for key, (label, value, provenance) in normalized.items()
        }
        rows = VGroup(*self.entries.values()).arrange(
            DOWN, buff=SPACING.sm, aligned_edge=LEFT
        )
        track_left = max(entry.track.get_left()[0] for entry in self.entries.values())
        for entry in self.entries.values():
            VGroup(
                entry.track,
                entry.bar,
                entry.value_label,
                entry.provenance_label,
            ).shift(RIGHT * (track_left - entry.track.get_left()[0]))
        first = next(iter(self.entries.values()))
        self.zero_label = Text(f"0 {unit}", font_size=13, color=TEXT_MUTED)
        self.maximum_label = Text(
            f"{_format_number(maximum)} {unit}", font_size=13, color=TEXT_MUTED
        )
        self.zero_label.next_to(first.track.get_left(), UP, buff=SPACING.xs)
        self.maximum_label.next_to(first.track.get_right(), UP, buff=SPACING.xs)
        self.axis = Line(
            first.track.get_left() + UP * (bar_height / 2 + SPACING.xs),
            first.track.get_right() + UP * (bar_height / 2 + SPACING.xs),
            color=NEUTRAL.light,
            stroke_width=STROKES.hairline.width,
        )
        self.add(self.axis, self.zero_label, self.maximum_label, *self.entries.values())
        self.center()

    def set_value(self, key: str, value: float) -> "ComparisonScale":
        """Update one bar on the unchanged shared scale, preserving identities."""
        if key not in self.entries:
            raise KeyError(f"unknown comparison key: {key!r}")
        value = _finite(value, "comparison value")
        if not 0 <= value <= self.maximum:
            raise ValueError("comparison value must be between zero and maximum")
        entry = self.entries[key]
        text = f"{_format_number(value)} {self.unit}"
        replacement = Text(
            text,
            font_size=entry.value_label.font_size,
            color=entry.value_label[0].get_color(),
        ).scale(entry.track.height / entry.bar.height if entry.bar.height else 1)
        replacement.move_to(entry.value_label, aligned_edge=LEFT)
        entry.bar.set_points(entry.track.points.copy())
        entry.bar.stretch(value / self.maximum, 0, about_point=entry.track.get_left())
        entry.bar.set_stroke(width=0)
        entry.value_label.become(replacement)
        entry.value_label.text = text
        entry.value = value
        return self


class CalibrationPoint(VGroup):
    """One keyed confidence/observed-accuracy bin."""

    def __init__(self, key: str, confidence: float, accuracy: float, position):
        super().__init__()
        self.key = key
        self.confidence = confidence
        self.accuracy = accuracy
        self.dot = Dot(position, radius=0.065, color=PRIMARY.light)
        self.add(self.dot)


class CalibrationPlot(VGroup):
    """Confidence versus observed accuracy with an explicit ideal reference.

    Points represent aggregate observations or bins. The separate axis labels
    and visible note deliberately avoid treating confidence as per-example
    correctness.
    """

    def __init__(
        self,
        points: Mapping[str, tuple[float, float]],
        *,
        width: float = 4.2,
        height: float = 3.2,
    ) -> None:
        if not points:
            raise ValueError("points must not be empty")
        normalized = {}
        for key, pair in points.items():
            if not isinstance(key, str) or not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError("points must map string keys to (confidence, accuracy)")
            confidence = self._probability(pair[0], "confidence")
            accuracy = self._probability(pair[1], "observed accuracy")
            normalized[key] = (confidence, accuracy)
        if width <= 0 or height <= 0:
            raise ValueError("plot dimensions must be positive")
        super().__init__()
        self.axes = Axes(
            x_range=[0, 1, 0.2],
            y_range=[0, 1, 0.2],
            x_length=width,
            y_length=height,
            axis_config={
                "color": NEUTRAL.light,
                "stroke_width": STROKES.normal.width,
                "include_ticks": True,
                "include_tip": False,
            },
        )
        self.ideal_reference = DashedLine(
            self.axes.c2p(0, 0),
            self.axes.c2p(1, 1),
            color=SUCCESS.base,
            stroke_width=STROKES.normal.width,
            dash_length=0.1,
        )
        self.x_label = Text("Confidence", font_size=18, color=TEXT_SECONDARY)
        self.y_label = Text("Observed accuracy", font_size=18, color=TEXT_SECONDARY)
        self.x_label.next_to(self.axes, DOWN, buff=SPACING.sm)
        self.y_label.next_to(self.axes, LEFT, buff=SPACING.sm).rotate(math.pi / 2)
        self.ideal_label = Text(
            "ideal calibration", font_size=13, color=SUCCESS.light
        ).next_to(self.ideal_reference.get_end(), LEFT, buff=SPACING.xs)
        self.note = Text(
            "Aggregate calibration; confidence is not per-example correctness",
            font_size=13,
            color=TEXT_MUTED,
        )
        _fit(self.note, width + 1.6, 0.22)
        self.note.next_to(self.x_label, DOWN, buff=SPACING.xs)
        self.bins: dict[str, CalibrationPoint] = {
            key: CalibrationPoint(
                key, confidence, accuracy, self.axes.c2p(confidence, accuracy)
            )
            for key, (confidence, accuracy) in normalized.items()
        }
        self.add(
            self.axes,
            self.ideal_reference,
            self.x_label,
            self.y_label,
            self.ideal_label,
            self.note,
            *self.bins.values(),
        )

    @staticmethod
    def _probability(value: float, name: str) -> float:
        value = _finite(value, name)
        if not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
        return value

    def update_point(
        self, key: str, confidence: float, observed_accuracy: float
    ) -> "CalibrationPlot":
        """Move one existing bin after validating both coordinates."""
        if key not in self.bins:
            raise KeyError(f"unknown calibration point: {key!r}")
        confidence = self._probability(confidence, "confidence")
        observed_accuracy = self._probability(
            observed_accuracy, "observed accuracy"
        )
        point = self.bins[key]
        point.dot.move_to(self.axes.c2p(confidence, observed_accuracy))
        point.confidence = confidence
        point.accuracy = observed_accuracy
        return self


__all__ = [
    "CalibrationPlot",
    "CalibrationPoint",
    "ComparisonEntry",
    "ComparisonScale",
    "MetricCard",
    "PROVENANCE_LABELS",
]
