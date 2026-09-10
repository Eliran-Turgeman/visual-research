"""Semantic probability distribution with stable entry identity and anchors.

A :class:`ProbabilityDistribution` arranges entries vertically, each with a
token label, a proportional bar, and a numeric value.  Entries are keyed for
stable identity and expose anchors for composing continuity animations.

:func:`animate_mass_transfer` returns a ``TransformFromCopy`` that visibly
moves probability mass from a distribution entry into another semantic object
(a tree node, an edge label, etc.) so the operand becomes part of the result.
"""

from __future__ import annotations

import math

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    Animation,
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
    TEXT_SECONDARY,
)


class DistributionEntry(VGroup):
    """One entry in a probability distribution with stable identity.

    Exposes :attr:`token_anchor`, :attr:`value_anchor`, and
    :attr:`highlight_anchor` for connecting continuity animations.

    Bar width is exactly ``track.width * value``, with no minimum width or
    outline that could imply extra mass. Zero collapses the fill to the track's
    left edge; subpixel positives remain distinguishable by their numeric label.
    Labels use two decimals except when rounding would hide a positive value
    or imply certainty. Use :meth:`set_value` to update existing objects.
    """

    def __init__(
        self,
        key: str,
        token: str,
        value: float,
        *,
        max_bar_width: float = 2.0,
        bar_height: float = 0.35,
        font_size: float = 22,
        bar_color: str = PRIMARY.base,
    ) -> None:
        super().__init__()
        self._validate_value(value)
        if any(
            not math.isfinite(dimension) or dimension <= 0
            for dimension in (max_bar_width, bar_height)
        ):
            raise ValueError("bar dimensions must be positive and finite")
        self.key = key
        self.token_text = token
        self.value = value
        self._bar_height = bar_height
        self._value_font_size = max(font_size - 2, 12)

        self.token_label = Text(token, font_size=font_size, color=TEXT_PRIMARY)
        self.track = RoundedRectangle(
            width=max_bar_width,
            height=bar_height,
            corner_radius=min(0.08, bar_height * 0.35, max_bar_width * 0.5),
            fill_color=SURFACE,
            fill_opacity=0.95,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.hairline.width,
        )
        self.bar = self.track.copy().set_fill(bar_color, opacity=0.78).set_stroke(
            width=0,
        )
        self.value_label = Text(
            self._format_value(value),
            font_size=self._value_font_size,
            color=TEXT_SECONDARY,
        )

        self.track.next_to(self.token_label, RIGHT, buff=SPACING.sm)
        self.bar.move_to(self.track).align_to(self.track, LEFT)
        self.bar.stretch(value, 0, about_point=self.track.get_left())
        self.value_label.next_to(self.track, RIGHT, buff=SPACING.xs)

        self.add(self.token_label, self.track, self.bar, self.value_label)

    @staticmethod
    def _validate_value(value: float) -> None:
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("distribution values must be finite and between 0 and 1")

    @staticmethod
    def _format_value(value: float) -> str:
        rounded = f"{value:.2f}"
        if value > 0 and rounded == "0.00":
            return f"{value:.2g}"
        if value < 1 and rounded == "1.00":
            return str(value)
        return rounded

    def set_value(self, value: float) -> "DistributionEntry":
        """Update mass and its label in place, also via ``entry.animate.set_value``.

        Entry, bar, track, and label identities are retained. The current
        horizontal track supplies the scale and baseline, so updates work after
        translating or uniformly scaling the distribution, including zero to
        positive transitions. Token and value-column positions stay fixed.
        """
        self._validate_value(value)
        text = self._format_value(value)
        # Text's container color need not match its visible glyphs.
        glyph = self.value_label[0]
        label = Text(
            text, font_size=self._value_font_size, color=glyph.get_color()
        ).set_opacity(glyph.get_fill_opacity()).scale(self.track.height / self._bar_height)
        label.move_to(self.value_label, aligned_edge=LEFT)
        self.bar.set_points(self.track.points.copy())
        self.bar.stretch(value, 0, about_point=self.track.get_left())
        self.bar.set_stroke(width=0)
        self.value_label.become(label)
        self.value_label.text = text
        self.value = value
        return self

    @property
    def token_anchor(self) -> np.ndarray:
        """Center of the token label — use for linking to token-based visuals."""
        return self.token_label.get_center()

    @property
    def value_anchor(self) -> np.ndarray:
        """Center of the value label — use for linking to numeric targets."""
        return self.value_label.get_center()

    @property
    def highlight_anchor(self) -> np.ndarray:
        """Center of the bar — use for emphasis overlays."""
        return self.bar.get_center()

    def highlight(
        self, color: str = ACCENT.base, opacity: float = 0.8
    ) -> "DistributionEntry":
        """Visually emphasize this entry's bar."""
        self.bar.set_fill(color, opacity=opacity)
        self.bar.set_stroke(ACCENT.light if color == ACCENT.base else color)
        self.value_label.set_color(ACCENT.light)
        return self


class ProbabilityDistribution(VGroup):
    """A semantic probability distribution with keyed, identity-stable entries.

    Parameters
    ----------
    entries : dict[str, tuple[str, float]]
        Mapping of ``{key: (token_display, probability)}``. Each value must be
        finite and in [0, 1]. Values are independent: subsets need not sum to
        one, and no normalization or total-mass constraint is imposed.

    Token labels are left-aligned; all tracks share a common left baseline,
    and numeric labels share a separate column regardless of label widths.
    """

    def __init__(
        self,
        entries: dict[str, tuple[str, float]],
        *,
        max_bar_width: float = 2.0,
        bar_height: float = 0.35,
        entry_buff: float | None = None,
        font_size: float = 22,
        bar_color: str = PRIMARY.base,
    ) -> None:
        if not entries:
            raise ValueError("entries must not be empty")
        super().__init__()
        if entry_buff is None:
            entry_buff = SPACING.xs

        self.entries: dict[str, DistributionEntry] = {}
        for key, (token, value) in entries.items():
            entry = DistributionEntry(
                key,
                token,
                value,
                max_bar_width=max_bar_width,
                bar_height=bar_height,
                font_size=font_size,
                bar_color=bar_color,
            )
            self.entries[key] = entry
            self.add(entry)
        self.arrange(DOWN, buff=entry_buff, aligned_edge=LEFT)
        baseline = max(entry.track.get_left()[0] for entry in self.entries.values())
        for entry in self.entries.values():
            VGroup(entry.track, entry.bar, entry.value_label).shift(
                RIGHT * (baseline - entry.track.get_left()[0])
            )
        self.center()

    def highlight_entry(
        self, key: str, color: str = ACCENT.base
    ) -> DistributionEntry:
        """Highlight a single entry by key.  Raises ``KeyError`` if absent."""
        if key not in self.entries:
            raise KeyError(f"No distribution entry with key: {key!r}")
        return self.entries[key].highlight(color)


def animate_mass_transfer(
    entry: DistributionEntry,
    target: Mobject,
    *,
    source_part: Mobject | None = None,
) -> Animation:
    """Return an animation that visibly transfers mass from *entry* to *target*.

    By default the entry's bar is the visual source; pass *source_part* to
    override (e.g. ``entry.value_label`` to show the numeric value flying
    to a score position).

    The returned ``TransformFromCopy`` leaves the source untouched and
    creates a copy that morphs into *target*.
    """
    source = source_part if source_part is not None else entry.bar
    return TransformFromCopy(source, target)


__all__ = [
    "DistributionEntry",
    "ProbabilityDistribution",
    "animate_mass_transfer",
]
