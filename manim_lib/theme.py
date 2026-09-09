"""Cohesive visual design system for technical Manim explainers.

Provides an original, restrained palette with semantic color roles, tonal
variants, a three-level typography hierarchy, stroke hierarchy, safe margins,
and a small spacing vocabulary.  Inspired by pedagogical principles—intuition
first, one evolving picture, semantic color, strong hierarchy, restrained
composition, purposeful motion—without copying any specific creator's assets.

All public configuration is exposed as frozen dataclass instances so themes are
typed, immutable, and safe to import from multiple modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from manim import ManimColor, config


# ---------------------------------------------------------------------------
# Palette — original restrained colors with semantic discipline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _SemanticColor:
    """A semantic role color with three tonal variants."""
    base: str
    light: str
    dim: str


# Deep blue-black stage and subtly separated object surfaces.  The surface
# colors create depth without relying on ornamental panels or drop shadows.
BACKGROUND = "#0b1020"
SURFACE = "#111a2e"
SURFACE_ELEVATED = "#17233d"
SHADOW = "#050814"

# Primary text / default foreground
TEXT_PRIMARY = "#f4f7ff"
TEXT_SECONDARY = "#aeb9d1"
TEXT_MUTED = "#66738f"

# Semantic role colors — original palette, not borrowed hex values.
PRIMARY = _SemanticColor(base="#4f9cff", light="#8fc5ff", dim="#24558f")
ACCENT = _SemanticColor(base="#f6c453", light="#ffe08a", dim="#896a25")
SUCCESS = _SemanticColor(base="#59d499", light="#91edc1", dim="#276f52")
DANGER = _SemanticColor(base="#f06b78", light="#ff9ba5", dim="#87333d")
NEUTRAL = _SemanticColor(base="#8290ad", light="#b6c2d9", dim="#3d4962")

# Convenience alias mapping for programmatic access
ROLE_COLORS: dict[str, _SemanticColor] = {
    "primary": PRIMARY,
    "accent": ACCENT,
    "success": SUCCESS,
    "danger": DANGER,
    "neutral": NEUTRAL,
}


# ---------------------------------------------------------------------------
# Typography hierarchy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TypographyLevel:
    """Font-size and color for one hierarchy level."""
    font_size: float
    color: str


@dataclass(frozen=True)
class Typography:
    """Three-level type scale: heading, body, caption."""
    heading: TypographyLevel = field(default_factory=lambda: TypographyLevel(42, TEXT_PRIMARY))
    body: TypographyLevel = field(default_factory=lambda: TypographyLevel(28, TEXT_PRIMARY))
    caption: TypographyLevel = field(default_factory=lambda: TypographyLevel(20, TEXT_SECONDARY))


TYPOGRAPHY = Typography()


# ---------------------------------------------------------------------------
# Stroke hierarchy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrokeLevel:
    """Named stroke weight."""
    width: float


@dataclass(frozen=True)
class Strokes:
    """Three-level stroke scale: heavy, normal, hairline."""
    heavy: StrokeLevel = field(default_factory=lambda: StrokeLevel(3.5))
    normal: StrokeLevel = field(default_factory=lambda: StrokeLevel(2.0))
    hairline: StrokeLevel = field(default_factory=lambda: StrokeLevel(1.0))


STROKES = Strokes()


# ---------------------------------------------------------------------------
# Spacing vocabulary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Spacing:
    """Small vocabulary of reusable spacing constants (Manim units)."""
    xs: float = 0.15
    sm: float = 0.3
    md: float = 0.6
    lg: float = 1.0
    xl: float = 1.6


SPACING = Spacing()


# ---------------------------------------------------------------------------
# Safe margins
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SafeMargins:
    """Frame-safe inset distances from each edge (Manim units)."""
    horizontal: float = 0.5
    vertical: float = 0.4

    @property
    def safe_width(self) -> float:
        """Usable width inside the safe zone."""
        return config.frame_width - 2 * self.horizontal

    @property
    def safe_height(self) -> float:
        """Usable height inside the safe zone."""
        return config.frame_height - 2 * self.vertical


SAFE_MARGINS = SafeMargins()


# ---------------------------------------------------------------------------
# Dim overlay defaults
# ---------------------------------------------------------------------------

DIM_OPACITY = 0.25
FOCUS_RESTORE_OPACITY = 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "ACCENT",
    "BACKGROUND",
    "DANGER",
    "DIM_OPACITY",
    "FOCUS_RESTORE_OPACITY",
    "NEUTRAL",
    "PRIMARY",
    "ROLE_COLORS",
    "SAFE_MARGINS",
    "SHADOW",
    "SPACING",
    "STROKES",
    "SUCCESS",
    "SURFACE",
    "SURFACE_ELEVATED",
    "TEXT_MUTED",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "TYPOGRAPHY",
    "SafeMargins",
    "Spacing",
    "StrokeLevel",
    "Strokes",
    "Typography",
    "TypographyLevel",
]
