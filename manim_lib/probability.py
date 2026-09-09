"""Semantic probability distribution with stable entry identity and anchors.

A :class:`ProbabilityDistribution` arranges entries vertically, each with a
token label, a proportional bar, and a numeric value.  Entries are keyed for
stable identity and expose anchors for composing continuity animations.

:func:`animate_mass_transfer` returns a ``TransformFromCopy`` that visibly
moves probability mass from a distribution entry into another semantic object
(a tree node, an edge label, etc.) so the operand becomes part of the result.
"""

from __future__ import annotations

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
        if not 0 <= value <= 1:
            raise ValueError("distribution values must be between 0 and 1")
        self.key = key
        self.token_text = token
        self.value = value

        self.token_label = Text(token, font_size=font_size, color=TEXT_PRIMARY)
        bar_width = max(max_bar_width * value, 0.05)
        self.track = RoundedRectangle(
            width=max_bar_width,
            height=bar_height,
            corner_radius=min(0.08, bar_height * 0.35),
            fill_color=SURFACE,
            fill_opacity=0.95,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.hairline.width,
        )
        self.bar = RoundedRectangle(
            width=bar_width,
            height=bar_height,
            corner_radius=min(0.08, bar_height * 0.35),
            fill_color=bar_color,
            fill_opacity=0.78,
            stroke_color=PRIMARY.light if bar_color == PRIMARY.base else bar_color,
            stroke_width=STROKES.hairline.width,
        )
        self.value_label = Text(
            f"{value:.2f}",
            font_size=max(font_size - 2, 12),
            color=TEXT_SECONDARY,
        )

        self.track.next_to(self.token_label, RIGHT, buff=SPACING.sm)
        self.bar.move_to(self.track).align_to(self.track, LEFT)
        self.value_label.next_to(self.track, RIGHT, buff=SPACING.xs)

        self.add(self.token_label, self.track, self.bar, self.value_label)

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
        Mapping of ``{key: (token_display, probability)}``.
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
