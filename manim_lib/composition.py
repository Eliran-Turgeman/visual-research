"""Composition and layout helpers for center-weighted, frame-safe scenes.

Small, testable helpers that replace ad-hoc ``.shift()`` chains with
intentional composition: centered single-focus placement, explicit side-by-side
comparisons, and frame-safe positioning using the theme's safe margins.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
from manim import DOWN, LEFT, RIGHT, UP, Mobject, Rectangle, VGroup, config

from .theme import BACKGROUND, SAFE_MARGINS, SPACING, Spacing, SafeMargins


# ---------------------------------------------------------------------------
# Frame-safe positioning
# ---------------------------------------------------------------------------

def safe_frame_rect(
    margins: SafeMargins = SAFE_MARGINS,
) -> Rectangle:
    """Return an invisible rectangle representing the safe area.

    Useful as an alignment anchor—call ``mob.move_to(safe_frame_rect())``
    or ``mob.align_to(safe_frame_rect(), UP)`` instead of hard-coding
    coordinates.
    """
    rect = Rectangle(
        width=margins.safe_width,
        height=margins.safe_height,
        stroke_opacity=0,
        fill_opacity=0,
    )
    return rect


def place_at_safe_edge(
    mob: Mobject,
    edge: np.ndarray,
    *,
    buff: float = SPACING.sm,
    margins: SafeMargins = SAFE_MARGINS,
) -> Mobject:
    """Move *mob* to a frame edge respecting safe margins.

    ``edge`` should be one of ``UP``, ``DOWN``, ``LEFT``, ``RIGHT``, or a
    combination like ``UP + LEFT``.  The mobject is placed ``buff`` units
    inward from the safe boundary—not from the frame edge—so content never
    creeps into the danger zone.

    Returns *mob* for chaining.
    """
    ref = safe_frame_rect(margins)
    mob.align_to(ref, edge)
    # Pull inward by buff along each active axis
    inward = -edge.astype(float)
    inward_norm = np.linalg.norm(inward)
    if inward_norm > 0:
        mob.shift(inward / inward_norm * buff)
    return mob


# ---------------------------------------------------------------------------
# Centered single-focus composition
# ---------------------------------------------------------------------------

def center_group(
    *mobjects: Mobject,
    direction: np.ndarray = DOWN,
    buff: float = SPACING.md,
) -> VGroup:
    """Arrange *mobjects* along *direction*, centered on the frame origin.

    Returns the new ``VGroup`` so it can be used directly in ``self.play()``.
    """
    group = VGroup(*mobjects)
    group.arrange(direction, buff=buff)
    group.move_to(np.array([0.0, 0.0, 0.0]))
    return group


# ---------------------------------------------------------------------------
# Side-by-side comparison
# ---------------------------------------------------------------------------

def side_by_side(
    left: Mobject,
    right: Mobject,
    *,
    buff: float = SPACING.lg,
    center_vertically: bool = True,
) -> VGroup:
    """Place two mobjects side by side centered on the frame.

    Useful for explicit before/after or A-vs-B comparisons.
    """
    group = VGroup(left, right)
    group.arrange(RIGHT, buff=buff)
    group.move_to(np.array([0.0, 0.0, 0.0]))
    if center_vertically:
        left.align_to(right, np.array([0.0, 0.0, 0.0]))
    return group


# ---------------------------------------------------------------------------
# Background dim overlay
# ---------------------------------------------------------------------------

def dim_overlay(
    *,
    opacity: float = 0.55,
    color: str = BACKGROUND,
) -> Rectangle:
    """Return a full-frame translucent overlay for purposeful background dimming.

    Add this to a scene *behind* the focal content to push everything else
    into the background.  Remove it when the focus phase is over.

    Only use when a scene genuinely needs context dimming—never as decoration.
    """
    return Rectangle(
        width=config.frame_width,
        height=config.frame_height,
        fill_color=color,
        fill_opacity=opacity,
        stroke_width=0,
    )


__all__ = [
    "center_group",
    "dim_overlay",
    "place_at_safe_edge",
    "safe_frame_rect",
    "side_by_side",
]
