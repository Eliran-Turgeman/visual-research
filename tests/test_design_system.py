"""Tests for the visual design system: theme, focus, and composition modules."""

import numpy as np
import pytest
from manim import DOWN, LEFT, RIGHT, UP, Circle, Rectangle, Text, VGroup, config

from manim_lib.theme import (
    ACCENT,
    BACKGROUND,
    DANGER,
    NEUTRAL,
    PRIMARY,
    ROLE_COLORS,
    SAFE_MARGINS,
    SHADOW,
    SPACING,
    STROKES,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TYPOGRAPHY,
)
from manim_lib.focus import FocusContext, focus_on, restore_focus
from manim_lib.composition import (
    center_group,
    dim_overlay,
    place_at_safe_edge,
    safe_frame_rect,
    side_by_side,
)


# ── Theme ─────────────────────────────────────────────────────────────────

class TestThemePalette:
    def test_background_is_near_black(self):
        # Near-black: R, G, B all below 0x40
        bg = BACKGROUND.lstrip("#")
        r, g, b = int(bg[:2], 16), int(bg[2:4], 16), int(bg[4:], 16)
        assert max(r, g, b) < 0x40

    def test_semantic_colors_have_three_variants(self):
        for name, color in ROLE_COLORS.items():
            assert color.base and color.light and color.dim, f"{name} missing variant"
            assert color.base != color.light != color.dim

    def test_text_colors_are_distinct(self):
        assert TEXT_PRIMARY != TEXT_SECONDARY != TEXT_MUTED

    def test_role_colors_map_contains_all_roles(self):
        assert set(ROLE_COLORS.keys()) == {"primary", "accent", "success", "danger", "neutral"}

    def test_surfaces_are_distinct_from_stage_and_text(self):
        assert BACKGROUND != SURFACE != SURFACE_ELEVATED
        assert SHADOW != BACKGROUND
        assert SURFACE_ELEVATED != TEXT_PRIMARY


class TestThemeTypography:
    def test_heading_is_largest(self):
        assert TYPOGRAPHY.heading.font_size > TYPOGRAPHY.body.font_size
        assert TYPOGRAPHY.body.font_size > TYPOGRAPHY.caption.font_size

    def test_heading_body_caption_all_have_color(self):
        for level in (TYPOGRAPHY.heading, TYPOGRAPHY.body, TYPOGRAPHY.caption):
            assert level.color


class TestThemeStrokes:
    def test_heavy_gt_normal_gt_hairline(self):
        assert STROKES.heavy.width > STROKES.normal.width > STROKES.hairline.width


class TestThemeSpacing:
    def test_monotonically_increasing(self):
        s = SPACING
        assert s.xs < s.sm < s.md < s.lg < s.xl


class TestThemeSafeMargins:
    def test_safe_dimensions_fit_inside_frame(self):
        assert SAFE_MARGINS.safe_width < config.frame_width
        assert SAFE_MARGINS.safe_height < config.frame_height
        assert SAFE_MARGINS.safe_width > 0
        assert SAFE_MARGINS.safe_height > 0


class TestThemeImmutability:
    def test_theme_objects_are_frozen(self):
        with pytest.raises(AttributeError):
            TYPOGRAPHY.heading = None  # type: ignore[misc]
        with pytest.raises(AttributeError):
            SPACING.xs = 999  # type: ignore[misc]
        with pytest.raises(AttributeError):
            STROKES.heavy = None  # type: ignore[misc]
        with pytest.raises(AttributeError):
            SAFE_MARGINS.horizontal = 999  # type: ignore[misc]


# ── Focus ─────────────────────────────────────────────────────────────────

class TestFocus:
    def test_focus_dims_context_not_targets(self):
        target = Circle(radius=0.5)
        bystander = Rectangle(width=1, height=1)
        bystander.set_opacity(1.0)

        anims, ctx = focus_on(target, context=[target, bystander], dim_opacity=0.2)
        # Only bystander should get a dim animation
        assert len(anims) == 1
        assert isinstance(ctx, FocusContext)

    def test_focus_single_mobject_target(self):
        target = Circle(radius=0.5)
        anims, ctx = focus_on(target, context=[])
        assert anims == []

    def test_restore_returns_animations_for_dimmed_only(self):
        a = Circle(radius=0.3)
        b = Rectangle(width=1, height=1)
        b.set_opacity(1.0)
        c = Circle(radius=0.4)

        anims, ctx = focus_on(a, context=[a, b, c], dim_opacity=0.2)
        restore_anims = restore_focus([a, b, c], ctx)
        # b and c were dimmed (a was target), so 2 restore animations
        assert len(restore_anims) == 2

    def test_restore_preserves_layered_child_opacities(self):
        target = Circle(radius=0.3)
        fill = Rectangle(width=1, height=1).set_fill(opacity=0.7)
        outline = Rectangle(width=1, height=1).set_fill(opacity=0).set_stroke(
            opacity=0.25
        )
        layered = VGroup(fill, outline)
        _, ctx = focus_on(target, context=[layered], dim_opacity=0.1)
        restore_anims = restore_focus([layered], ctx)

        restore_anims[0].begin()
        restore_anims[0].finish()

        assert fill.get_fill_opacity() == pytest.approx(0.7)
        assert outline.get_fill_opacity() == pytest.approx(0.0)
        assert outline.get_stroke_opacity() == pytest.approx(0.25)


# ── Composition ───────────────────────────────────────────────────────────

class TestSafeFrameRect:
    def test_dimensions_match_safe_margins(self):
        rect = safe_frame_rect()
        assert rect.width == pytest.approx(SAFE_MARGINS.safe_width)
        assert rect.height == pytest.approx(SAFE_MARGINS.safe_height)


class TestPlaceAtSafeEdge:
    def test_top_placement_within_safe_area(self):
        mob = Rectangle(width=1, height=0.5)
        place_at_safe_edge(mob, UP)
        top = mob.get_top()[1]
        limit = config.frame_height / 2 - SAFE_MARGINS.vertical
        assert top <= limit + 0.01

    def test_bottom_placement(self):
        mob = Rectangle(width=1, height=0.5)
        place_at_safe_edge(mob, DOWN)
        bottom = mob.get_bottom()[1]
        limit = -(config.frame_height / 2 - SAFE_MARGINS.vertical)
        assert bottom >= limit - 0.01

    def test_returns_same_object(self):
        mob = Circle(radius=0.3)
        result = place_at_safe_edge(mob, RIGHT)
        assert result is mob


class TestCenterGroup:
    def test_group_is_centered_at_origin(self):
        a = Rectangle(width=1, height=0.5)
        b = Rectangle(width=1, height=0.5)
        group = center_group(a, b)
        center = group.get_center()
        assert abs(center[0]) < 0.01
        assert abs(center[1]) < 0.01

    def test_group_contains_all_mobjects(self):
        a = Circle(radius=0.3)
        b = Circle(radius=0.3)
        c = Circle(radius=0.3)
        group = center_group(a, b, c)
        assert len(group) == 3


class TestSideBySide:
    def test_left_is_left_of_right(self):
        a = Rectangle(width=1, height=1)
        b = Rectangle(width=1, height=1)
        group = side_by_side(a, b)
        assert a.get_center()[0] < b.get_center()[0]

    def test_centered_on_origin(self):
        a = Rectangle(width=1, height=1)
        b = Rectangle(width=1, height=1)
        group = side_by_side(a, b)
        assert abs(group.get_center()[0]) < 0.01


class TestDimOverlay:
    def test_covers_full_frame(self):
        overlay = dim_overlay()
        assert overlay.width == pytest.approx(config.frame_width)
        assert overlay.height == pytest.approx(config.frame_height)

    def test_has_fill_opacity(self):
        overlay = dim_overlay(opacity=0.6)
        assert overlay.get_fill_opacity() == pytest.approx(0.6)

    def test_no_stroke(self):
        overlay = dim_overlay()
        assert overlay.get_stroke_width() == pytest.approx(0.0)
