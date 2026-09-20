"""Reusable policy-decision visuals with explicit, stable semantics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import math
from numbers import Real
from typing import Any

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    DecimalNumber,
    Line,
    Mobject,
    Rectangle,
    RoundedRectangle,
    Text,
    Triangle,
    VGroup,
)

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
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def _finite_number(value: Real, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


@dataclass(frozen=True)
class ConfidenceRegion:
    """One named interval on a confidence gate."""

    name: str
    lower: float
    upper: float
    color: str = NEUTRAL.base


class ConfidenceGate(VGroup):
    """An exact unit-interval scale divided into caller-defined regions.

    Regions must be ordered, contiguous, and cover ``[0, 1]``. Alternatively,
    callers may provide interior ``thresholds`` and one name per resulting
    region. ``set_value`` moves the existing marker rather than replacing it,
    so marker identity and geometry survive scaling, translation, and
    ``gate.animate.set_value(...)``.
    """

    def __init__(
        self,
        regions: (
            Mapping[str, Sequence[Any]]
            | Sequence[ConfidenceRegion | Sequence[Any]]
            | None
        ) = None,
        *,
        thresholds: Sequence[Real] | None = None,
        region_names: Sequence[str] | None = None,
        value: Real = 0.0,
        width: Real = 4.0,
        bar_height: Real = 0.28,
        marker_height: Real = 0.22,
        font_size: Real = 18,
    ) -> None:
        parsed = self._parse_regions(regions, thresholds, region_names)
        initial_value = self._validate_value(value)
        width_value = _finite_number(width, "width")
        bar_height_value = _finite_number(bar_height, "bar_height")
        marker_height_value = _finite_number(marker_height, "marker_height")
        if width_value <= 0 or bar_height_value <= 0 or marker_height_value <= 0:
            raise ValueError("gate dimensions must be positive")

        super().__init__()
        self.region_definitions = tuple(parsed)
        self.thresholds = tuple(region.upper for region in parsed[:-1])
        self.value = initial_value
        self.selected_region = self._region_for(initial_value)

        self.track = Line(
            LEFT * width_value / 2,
            RIGHT * width_value / 2,
            stroke_color=NEUTRAL.light,
            stroke_width=STROKES.normal.width,
        )
        self.region_mobjects: dict[str, Rectangle] = {}
        self.region_labels: dict[str, Text] = {}
        for region in parsed:
            segment_width = width_value * (region.upper - region.lower)
            segment = Rectangle(
                width=segment_width,
                height=bar_height_value,
                fill_color=region.color,
                fill_opacity=0.72,
                stroke_width=0,
            )
            x = -width_value / 2 + width_value * (region.lower + region.upper) / 2
            segment.move_to([x, 0, 0])
            label = Text(region.name, font_size=font_size, color=TEXT_PRIMARY)
            if label.width > segment.width - SPACING.xs:
                label.scale_to_fit_width(max(segment.width - SPACING.xs, 0.01))
            label.next_to(segment, DOWN, buff=SPACING.xs + marker_height_value)
            self.region_mobjects[region.name] = segment
            self.region_labels[region.name] = label

        self.marker = Triangle(
            color=ACCENT.light,
            fill_color=ACCENT.base,
            fill_opacity=1,
            stroke_width=STROKES.hairline.width,
        ).scale_to_fit_height(marker_height_value)
        self.marker.rotate(np.pi)
        self.marker.next_to(self.track, DOWN, buff=SPACING.xs)
        self.marker.shift(
            RIGHT * (self.position_for_value(initial_value)[0] - self.marker.get_center()[0])
        )

        self.add(
            *self.region_mobjects.values(),
            self.track,
            self.marker,
            *self.region_labels.values(),
        )

    @classmethod
    def _parse_regions(
        cls,
        regions: Mapping[str, Sequence[Any]] | Sequence[Any] | None,
        thresholds: Sequence[Real] | None,
        region_names: Sequence[str] | None,
    ) -> list[ConfidenceRegion]:
        if regions is not None and (thresholds is not None or region_names is not None):
            raise ValueError("provide either regions or thresholds/region_names, not both")
        if regions is None:
            if thresholds is None or region_names is None:
                raise ValueError("explicit regions or thresholds with region_names are required")
            cuts = [_finite_number(v, "threshold") for v in thresholds]
            if any(not 0 < cut < 1 for cut in cuts) or cuts != sorted(cuts):
                raise ValueError("thresholds must be strictly increasing inside (0, 1)")
            if len(set(cuts)) != len(cuts):
                raise ValueError("thresholds must be unique")
            if len(region_names) != len(cuts) + 1:
                raise ValueError("region_names must contain one name per interval")
            colors = [DANGER.base, ACCENT.base, SUCCESS.base, PRIMARY.base]
            bounds = [0.0, *cuts, 1.0]
            parsed = [
                ConfidenceRegion(
                    str(region_names[index]),
                    bounds[index],
                    bounds[index + 1],
                    colors[min(index, len(colors) - 1)],
                )
                for index in range(len(region_names))
            ]
        else:
            items = regions.items() if isinstance(regions, Mapping) else regions
            parsed = []
            for item in items:
                if isinstance(item, ConfidenceRegion):
                    parsed.append(item)
                    continue
                values = tuple(item)
                if isinstance(regions, Mapping):
                    name, specification = values
                    specification = tuple(specification)
                    values = (name, *specification)
                if len(values) not in (3, 4):
                    raise ValueError("each region needs name, lower, upper, and optional color")
                name, lower, upper = values[:3]
                color = values[3] if len(values) == 4 else NEUTRAL.base
                parsed.append(
                    ConfidenceRegion(
                        str(name),
                        _finite_number(lower, "region lower bound"),
                        _finite_number(upper, "region upper bound"),
                        color,
                    )
                )
        if not parsed:
            raise ValueError("at least one confidence region is required")
        if any(not region.name for region in parsed):
            raise ValueError("region names must not be empty")
        if len({region.name for region in parsed}) != len(parsed):
            raise ValueError("region names must be unique")
        if not math.isclose(parsed[0].lower, 0.0) or not math.isclose(
            parsed[-1].upper, 1.0
        ):
            raise ValueError("regions must cover exactly [0, 1]")
        for index, region in enumerate(parsed):
            if not 0 <= region.lower < region.upper <= 1:
                raise ValueError("region bounds must be ordered inside [0, 1]")
            if index and not math.isclose(parsed[index - 1].upper, region.lower):
                raise ValueError("regions must be contiguous and ordered")
        return parsed

    @staticmethod
    def _validate_value(value: Real) -> float:
        result = _finite_number(value, "confidence")
        if not 0 <= result <= 1:
            raise ValueError("confidence must be in the exact range [0, 1]")
        return result

    def _region_for(self, value: float) -> str:
        for index, region in enumerate(self.region_definitions):
            if value < region.upper or index == len(self.region_definitions) - 1:
                return region.name
        raise RuntimeError("validated confidence did not match a region")

    def position_for_value(self, value: Real) -> np.ndarray:
        """Return the exact point on the current, possibly transformed scale."""
        normalized = self._validate_value(value)
        return self.track.get_start() + normalized * (
            self.track.get_end() - self.track.get_start()
        )

    def set_value(self, value: Real) -> "ConfidenceGate":
        """Validate, then move the existing marker to ``value``."""
        normalized = self._validate_value(value)
        selected = self._region_for(normalized)
        destination = self.position_for_value(normalized)
        self.marker.shift(RIGHT * (destination[0] - self.marker.get_center()[0]))
        self.value = normalized
        self.selected_region = selected
        return self


class DecisionRouter(VGroup):
    """A single decision point connected to explicit named destinations."""

    def __init__(
        self,
        decision_point: Mobject,
        destinations: Mapping[str, Mobject],
        *,
        route_color: str = NEUTRAL.base,
        selected_color: str = ACCENT.base,
    ) -> None:
        if not isinstance(decision_point, Mobject):
            raise TypeError("decision_point must be a Mobject")
        if not destinations:
            raise ValueError("destinations must not be empty")
        if any(not isinstance(name, str) or not name for name in destinations):
            raise ValueError("destination names must be non-empty strings")
        if any(not isinstance(node, Mobject) for node in destinations.values()):
            raise TypeError("every destination must be a Mobject")
        identities = [id(node) for node in destinations.values()]
        if len(set(identities)) != len(identities) or id(decision_point) in identities:
            raise ValueError("decision point and destinations must have unique identities")

        super().__init__()
        self.decision_point = decision_point
        self.destinations = dict(destinations)
        self.selected_route: str | None = None
        self._route_color = route_color
        self._selected_color = selected_color
        self.route_edges: dict[str, Line] = {}
        self.route_highlights: dict[str, RoundedRectangle] = {}

        for name, destination in self.destinations.items():
            edge = Line(
                decision_point.get_center(),
                destination.get_center(),
                color=route_color,
                stroke_width=STROKES.normal.width,
                stroke_opacity=0.48,
            )
            highlight = RoundedRectangle(
                width=destination.width + 2 * SPACING.xs,
                height=destination.height + 2 * SPACING.xs,
                corner_radius=0.12,
                fill_opacity=0,
                stroke_color=selected_color,
                stroke_opacity=0,
                stroke_width=STROKES.heavy.width,
            ).move_to(destination)
            self.route_edges[name] = edge
            self.route_highlights[name] = highlight

        self.add(
            *self.route_edges.values(),
            *self.route_highlights.values(),
            decision_point,
            *self.destinations.values(),
        )

    def select_route(self, name: str) -> "DecisionRouter":
        """Highlight an existing route without replacing any node or edge."""
        if name not in self.destinations:
            raise KeyError(f"unknown route: {name!r}")
        for route_name, edge in self.route_edges.items():
            if route_name == name:
                edge.set_stroke(
                    self._selected_color,
                    width=STROKES.heavy.width,
                    opacity=1,
                )
                self.route_highlights[route_name].set_stroke(opacity=1)
                self.route_highlights[route_name].set_fill(opacity=0)
            else:
                edge.set_stroke(
                    self._route_color,
                    width=STROKES.normal.width,
                    opacity=0.25,
                )
                self.route_highlights[route_name].set_stroke(opacity=0)
                self.route_highlights[route_name].set_fill(opacity=0)
        self.selected_route = name
        return self


class DecisionAggregator(VGroup):
    """Visible weighted sum over explicit named scalar inputs."""

    def __init__(
        self,
        inputs: Mapping[str, Real],
        weights: Mapping[str, Real],
        *,
        decimal_places: int = 2,
        font_size: Real = 22,
    ) -> None:
        if not inputs:
            raise ValueError("inputs must not be empty")
        if set(inputs) != set(weights):
            raise ValueError("inputs and weights must have exactly matching keys")
        if any(not isinstance(name, str) or not name for name in inputs):
            raise ValueError("input names must be non-empty strings")
        input_values = {
            name: _finite_number(value, f"input {name!r}") for name, value in inputs.items()
        }
        weight_values = {
            name: _finite_number(value, f"weight {name!r}")
            for name, value in weights.items()
        }
        if isinstance(decimal_places, bool) or not isinstance(decimal_places, int):
            raise ValueError("decimal_places must be a nonnegative integer")
        if decimal_places < 0:
            raise ValueError("decimal_places must be a nonnegative integer")

        super().__init__()
        self.input_values = input_values
        self.weights = weight_values
        self.decimal_places = decimal_places
        self.terms: dict[str, VGroup] = {}
        self.input_mobjects: dict[str, DecimalNumber] = {}
        self.weight_mobjects: dict[str, DecimalNumber] = {}

        for name in inputs:
            name_label = Text(name, font_size=font_size, color=TEXT_PRIMARY)
            weight_label = DecimalNumber(
                weight_values[name],
                num_decimal_places=decimal_places,
                color=PRIMARY.light,
                font_size=font_size,
            )
            multiply = Text("×", font_size=font_size, color=TEXT_SECONDARY)
            input_label = DecimalNumber(
                input_values[name],
                num_decimal_places=decimal_places,
                color=ACCENT.light,
                font_size=font_size,
            )
            term = VGroup(name_label, weight_label, multiply, input_label).arrange(
                RIGHT, buff=SPACING.xs
            )
            self.terms[name] = term
            self.weight_mobjects[name] = weight_label
            self.input_mobjects[name] = input_label

        self.result_caption = Text("result", font_size=font_size, color=TEXT_SECONDARY)
        self.result_mobject = DecimalNumber(
            self.result,
            num_decimal_places=decimal_places,
            color=SUCCESS.light,
            font_size=font_size,
        )
        self.result_group = VGroup(self.result_caption, self.result_mobject).arrange(
            RIGHT, buff=SPACING.sm
        )
        VGroup(*self.terms.values()).arrange(DOWN, buff=SPACING.xs, aligned_edge=LEFT)
        self.add(*self.terms.values(), self.result_group)
        self.result_group.next_to(
            VGroup(*self.terms.values()), DOWN, buff=SPACING.sm, aligned_edge=RIGHT
        )

    @property
    def result(self) -> float:
        return sum(self.weights[name] * value for name, value in self.input_values.items())

    def set_input(self, name: str, value: Real) -> "DecisionAggregator":
        """Validate and update one operand and the existing result in place."""
        if name not in self.input_values:
            raise KeyError(f"unknown input: {name!r}")
        validated = _finite_number(value, f"input {name!r}")
        new_result = sum(
            self.weights[key] * (validated if key == name else current)
            for key, current in self.input_values.items()
        )
        self.input_mobjects[name].set_value(validated)
        self.result_mobject.set_value(new_result)
        self.input_values[name] = validated
        return self


class PacketStatus(str, Enum):
    NEUTRAL = "neutral"
    PENDING = "pending"
    ACTIVE = "active"
    SUCCESS = "success"
    ERROR = "error"


_STATUS_COLORS = {
    PacketStatus.NEUTRAL: NEUTRAL.base,
    PacketStatus.PENDING: ACCENT.base,
    PacketStatus.ACTIVE: PRIMARY.base,
    PacketStatus.SUCCESS: SUCCESS.base,
    PacketStatus.ERROR: DANGER.base,
}


class DataPacket(VGroup):
    """A compact, identity-stable labeled payload with semantic status."""

    def __init__(
        self,
        packet_id: str,
        label: str,
        payload: Any,
        *,
        status: PacketStatus | str = PacketStatus.NEUTRAL,
        preview_length: int = 36,
        width: Real = 2.6,
        height: Real = 1.15,
        font_size: Real = 20,
    ) -> None:
        if not isinstance(packet_id, str) or not packet_id:
            raise ValueError("packet_id must be a non-empty string")
        if not isinstance(label, str) or not label:
            raise ValueError("label must be a non-empty string")
        if isinstance(preview_length, bool) or not isinstance(preview_length, int):
            raise ValueError("preview_length must be a positive integer")
        if preview_length <= 0:
            raise ValueError("preview_length must be a positive integer")
        parsed_status = self._parse_status(status)
        width_value = _finite_number(width, "width")
        height_value = _finite_number(height, "height")
        if width_value <= 0 or height_value <= 0:
            raise ValueError("packet dimensions must be positive")

        super().__init__()
        self.packet_id = packet_id
        self.packet_label = label
        self.payload = payload
        self.status = parsed_status
        self._font_size = float(font_size)
        self._base_badge_height = 0.26

        self.body = RoundedRectangle(
            width=width_value,
            height=height_value,
            corner_radius=0.14,
            fill_color=SURFACE_ELEVATED,
            fill_opacity=0.96,
            stroke_color=_STATUS_COLORS[parsed_status],
            stroke_width=STROKES.normal.width,
        )
        self.label_mobject = Text(label, font_size=font_size, color=TEXT_PRIMARY)
        self.payload_preview = Text(
            self._preview(payload, preview_length),
            font_size=max(float(font_size) - 4, 10),
            color=TEXT_SECONDARY,
        )
        content = VGroup(self.label_mobject, self.payload_preview).arrange(
            DOWN, buff=SPACING.xs, aligned_edge=LEFT
        )
        max_content_width = width_value - 2 * SPACING.sm
        if content.width > max_content_width:
            content.scale_to_fit_width(max_content_width)
        content.move_to(self.body)

        self.status_badge = RoundedRectangle(
            width=0.9,
            height=self._base_badge_height,
            corner_radius=0.08,
            fill_color=_STATUS_COLORS[parsed_status],
            fill_opacity=0.9,
            stroke_width=0,
        )
        self.status_label = Text(
            parsed_status.value.upper(),
            font_size=max(float(font_size) - 7, 8),
            color=TEXT_PRIMARY,
        ).move_to(self.status_badge)
        self.status_badge.next_to(self.body, DOWN, buff=-self._base_badge_height / 2)
        self.status_label.move_to(self.status_badge)
        self.add(
            self.body,
            self.label_mobject,
            self.payload_preview,
            self.status_badge,
            self.status_label,
        )

    @staticmethod
    def _parse_status(status: PacketStatus | str) -> PacketStatus:
        try:
            return PacketStatus(status)
        except (TypeError, ValueError) as exc:
            allowed = ", ".join(item.value for item in PacketStatus)
            raise ValueError(f"unknown packet status; expected one of: {allowed}") from exc

    @staticmethod
    def _preview(payload: Any, limit: int) -> str:
        if isinstance(payload, Mapping):
            text = ", ".join(f"{key}={value!r}" for key, value in payload.items())
        else:
            text = str(payload)
        return text if len(text) <= limit else text[: max(limit - 1, 0)] + "…"

    def set_status(self, status: PacketStatus | str) -> "DataPacket":
        """Validate and update existing status visuals in place."""
        parsed = self._parse_status(status)
        color = _STATUS_COLORS[parsed]
        scale = self.status_badge.height / self._base_badge_height
        replacement = Text(
            parsed.value.upper(),
            font_size=max(self._font_size - 7, 8),
            color=TEXT_PRIMARY,
        ).scale(scale)
        replacement.move_to(self.status_label)
        self.body.set_stroke(color=color)
        self.status_badge.set_fill(color=color, opacity=0.9)
        self.status_label.become(replacement)
        self.status_label.text = parsed.value.upper()
        self.status = parsed
        return self


__all__ = [
    "ConfidenceGate",
    "ConfidenceRegion",
    "DataPacket",
    "DecisionAggregator",
    "DecisionRouter",
    "PacketStatus",
]
