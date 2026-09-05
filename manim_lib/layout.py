"""Reusable layout validation utilities: safe-frame, overlap, and containment
checks.

These are plain functions over Manim mobjects' axis-aligned bounding boxes.
They are meant to be called from tests and from ad-hoc scripts while a scene
is being developed, not from render-time hooks or global monkeypatching, so a
scene never depends on them to run correctly.
"""

from itertools import combinations

from manim import RED, Mobject, Rectangle, config

BoundingBox = tuple[float, float, float, float]


def bounding_box(mobject: Mobject) -> BoundingBox:
    """Return the axis-aligned ``(left, right, bottom, top)`` bounds."""
    return (
        mobject.get_left()[0],
        mobject.get_right()[0],
        mobject.get_bottom()[1],
        mobject.get_top()[1],
    )


def boxes_overlap(box_a: BoundingBox, box_b: BoundingBox, *, tolerance: float = 0.0) -> bool:
    """Return whether two axis-aligned boxes overlap by more than ``tolerance``.

    A positive ``tolerance`` allows a small amount of touching/near overlap
    (useful for hairline stroke widths); a negative value demands a margin.
    """
    left_a, right_a, bottom_a, top_a = box_a
    left_b, right_b, bottom_b, top_b = box_b
    horizontal = min(right_a, right_b) - max(left_a, left_b)
    vertical = min(top_a, top_b) - max(bottom_a, bottom_b)
    return horizontal > tolerance and vertical > tolerance


def mobjects_overlap(a: Mobject, b: Mobject, *, tolerance: float = 0.0) -> bool:
    """Return whether two mobjects' bounding boxes overlap by more than ``tolerance``."""
    return boxes_overlap(bounding_box(a), bounding_box(b), tolerance=tolerance)


def find_overlaps(
    mobjects: list[Mobject], *, tolerance: float = 0.0
) -> list[tuple[int, int]]:
    """Return index pairs among ``mobjects`` whose bounding boxes overlap.

    Intended for a set of sibling objects that must stay visually distinct,
    such as tree nodes, score labels, or table cells. It is a plain
    axis-aligned bounding-box check, so intentionally overlapping objects
    (for example an edge drawn behind a node) should be excluded from the
    input list rather than special-cased here.
    """
    boxes = [bounding_box(mobject) for mobject in mobjects]
    return [
        (i, j)
        for (i, box_i), (j, box_j) in combinations(enumerate(boxes), 2)
        if boxes_overlap(box_i, box_j, tolerance=tolerance)
    ]


def contains(container: Mobject, contained: Mobject, *, padding: float = 0.0) -> bool:
    """Return whether ``contained``'s bounding box lies within ``container``'s.

    ``padding`` shrinks the container box inward, which is useful for
    checking that a label stays comfortably inside a circle or panel rather
    than merely touching its edge.
    """
    left_c, right_c, bottom_c, top_c = bounding_box(container)
    left_x, right_x, bottom_x, top_x = bounding_box(contained)
    return (
        left_x >= left_c + padding
        and right_x <= right_c - padding
        and bottom_x >= bottom_c + padding
        and top_x <= top_c - padding
    )


def within_safe_frame(mobject: Mobject, *, margin: float = 0.0) -> bool:
    """Return whether a mobject stays inside the rendered frame with ``margin``."""
    half_width = config.frame_width / 2 - margin
    half_height = config.frame_height / 2 - margin
    left, right, bottom, top = bounding_box(mobject)
    return (
        left >= -half_width
        and right <= half_width
        and bottom >= -half_height
        and top <= half_height
    )


def assert_within_safe_frame(
    mobject: Mobject, *, margin: float = 0.0, label: str = "mobject"
) -> None:
    """Raise ``AssertionError`` if ``mobject`` extends outside the safe frame."""
    if not within_safe_frame(mobject, margin=margin):
        raise AssertionError(
            f"{label} extends outside the safe frame (margin={margin})"
        )


def assert_no_overlaps(
    mobjects: list[Mobject],
    *,
    tolerance: float = 0.0,
    labels: list[str] | None = None,
) -> None:
    """Raise ``AssertionError`` naming the first unexpected overlapping pair."""
    if labels is not None and len(labels) != len(mobjects):
        raise ValueError("labels must match mobjects one-to-one")
    pairs = find_overlaps(mobjects, tolerance=tolerance)
    if pairs:
        i, j = pairs[0]
        name_i = labels[i] if labels else f"item {i}"
        name_j = labels[j] if labels else f"item {j}"
        raise AssertionError(f"Unexpected overlap between {name_i} and {name_j}")


def bounding_box_overlay(mobject: Mobject, *, color=RED, buff: float = 0.0) -> Rectangle:
    """Return a debug rectangle matching a mobject's bounding box plus ``buff``.

    Add this to a scene temporarily while iterating on a layout; it is a
    development aid and should not remain in a finished render.
    """
    left, right, bottom, top = bounding_box(mobject)
    rect = Rectangle(
        width=(right - left) + 2 * buff,
        height=(top - bottom) + 2 * buff,
        stroke_color=color,
        stroke_width=2,
        fill_opacity=0,
    )
    rect.move_to(((left + right) / 2, (bottom + top) / 2, 0))
    return rect
