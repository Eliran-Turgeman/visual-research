"""Tests for reusable layout validation utilities."""

import pytest
from manim import DOWN, RIGHT, UP, Circle, Rectangle, Text

from manim_lib import (
    assert_no_overlaps,
    assert_within_safe_frame,
    bounding_box,
    bounding_box_overlay,
    boxes_overlap,
    contains,
    find_overlaps,
    mobjects_overlap,
    within_safe_frame,
)


def test_bounding_box_matches_manim_extents():
    rect = Rectangle(width=2, height=1)
    left, right, bottom, top = bounding_box(rect)
    assert left == pytest.approx(-1)
    assert right == pytest.approx(1)
    assert bottom == pytest.approx(-0.5)
    assert top == pytest.approx(0.5)


def test_boxes_overlap_detects_and_respects_tolerance():
    box_a = (0.0, 1.0, 0.0, 1.0)
    box_b = (0.5, 1.5, 0.0, 1.0)
    box_c = (2.0, 3.0, 0.0, 1.0)
    assert boxes_overlap(box_a, box_b)
    assert not boxes_overlap(box_a, box_c)
    # A small positive tolerance forgives a hairline overlap.
    assert not boxes_overlap(box_a, box_b, tolerance=0.6)


def test_mobjects_overlap_and_find_overlaps():
    left_box = Rectangle(width=1, height=1).shift(RIGHT * -1)
    right_box = Rectangle(width=1, height=1).shift(RIGHT * 1)
    overlapping_box = Rectangle(width=1, height=1).shift(RIGHT * 0.9)
    assert not mobjects_overlap(left_box, right_box)
    assert mobjects_overlap(right_box, overlapping_box)

    pairs = find_overlaps([left_box, right_box, overlapping_box])
    assert pairs == [(1, 2)]


def test_assert_no_overlaps_raises_with_labels():
    a = Rectangle(width=1, height=1)
    b = Rectangle(width=1, height=1)
    with pytest.raises(AssertionError, match="node-a and node-b"):
        assert_no_overlaps([a, b], labels=["node-a", "node-b"])
    assert_no_overlaps([a, b.copy().shift(RIGHT * 5)])


def test_contains_checks_label_within_circle_with_padding():
    circle = Circle(radius=0.5)
    small_label = Text("ok", font_size=16).move_to(circle)
    assert contains(circle, small_label, padding=0.05)

    wide_label = Text("overflow", font_size=32).move_to(circle)
    assert not contains(circle, wide_label)


def test_within_safe_frame_flags_off_frame_objects():
    centered = Rectangle(width=1, height=1)
    assert within_safe_frame(centered)

    far_away = Rectangle(width=1, height=1).shift(RIGHT * 1000)
    assert not within_safe_frame(far_away)
    assert_within_safe_frame(centered, label="centered box")
    with pytest.raises(AssertionError, match="off-frame box"):
        assert_within_safe_frame(far_away, label="off-frame box")


def test_bounding_box_overlay_matches_target_extents():
    target = Rectangle(width=2, height=1).shift(UP * 0.5 + DOWN * 0.2)
    overlay = bounding_box_overlay(target, buff=0.1)
    assert overlay.width == pytest.approx(target.width + 0.2)
    assert overlay.height == pytest.approx(target.height + 0.2)
    assert overlay.get_center() == pytest.approx(target.get_center())
