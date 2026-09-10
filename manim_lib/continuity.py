"""Continuity-first animation primitives.

Helpers that produce animations preserving object identity and making
structural relationships visible, so visual explanations evolve as one
picture rather than disconnected animated slides.

All functions return lists of :class:`~manim.animation.animation.Animation`
(or tuples containing them) rather than opaque custom ``Animation`` subclasses,
keeping composition in the caller's hands.
"""

from __future__ import annotations

from numbers import Integral
from typing import Sequence

import numpy as np
from manim import (
    DOWN,
    Animation,
    FadeIn,
    FadeOut,
    GrowFromPoint,
    Line,
    Mobject,
    Rectangle,
    Text,
    TransformFromCopy,
    VGroup,
)

from .composition import dim_overlay
from .focus import FocusContext, focus_on, restore_focus
from .matrices import LabeledMatrix
from .theme import ACCENT, DIM_OPACITY, SPACING, TEXT_SECONDARY
from .tokens import TokenSequence
from .trees import StableTree, TreeNode


# ---------------------------------------------------------------------------
# Branch growth
# ---------------------------------------------------------------------------


def grow_branch(
    tree: StableTree,
    parent_key: str,
    child_key: str,
    child_node: TreeNode,
    position: tuple | np.ndarray,
    *,
    label: str | None = None,
    label_font_size: float = 18,
    label_color: str = TEXT_SECONDARY,
) -> tuple[list[Animation], Line]:
    """Grow a new branch from *parent_key* to *position* in a StableTree.

    The node and edge are registered in the tree immediately (so later calls
    can reference them); the returned animations handle their visual
    introduction:

    1. ``GrowFromPoint`` for the edge originating at the parent.
    2. ``FadeIn`` for the child node, shifting from the parent direction.
    3. Optionally ``FadeIn`` for an edge label.

    Returns ``(animations, edge)``.
    """
    if parent_key not in tree.nodes:
        raise KeyError(f"Parent node not found: {parent_key!r}")

    tree.add_node(child_key, child_node, position)
    edge = tree.connect(parent_key, child_key)

    parent_center = tree.nodes[parent_key].get_center()
    child_center = np.array(position, dtype=float)
    direction = child_center - parent_center
    norm = np.linalg.norm(direction)
    shift = direction * 0.3 if norm > 0 else DOWN * 0.3

    anims: list[Animation] = [
        GrowFromPoint(edge, parent_center),
        FadeIn(child_node, shift=shift),
    ]

    if label is not None:
        edge_label = Text(
            label, font_size=label_font_size, color=label_color
        ).move_to(edge.get_center())
        tree.add(edge_label)
        anims.append(FadeIn(edge_label))

    return anims, edge


# ---------------------------------------------------------------------------
# Tree → sequence mapping
# ---------------------------------------------------------------------------


def map_tree_to_sequence(
    tree: StableTree,
    key_to_index: dict[str, int],
    sequence: TokenSequence,
) -> list[Animation]:
    """Return ``TransformFromCopy`` animations from tree nodes to sequence slots.

    The caller must explicitly map source node keys to destination indices;
    duplicates, missing keys, and out-of-range indices are rejected.
    """
    # Validate duplicates
    indices = list(key_to_index.values())
    if len(set(indices)) != len(indices):
        seen: set[int] = set()
        for idx in indices:
            if idx in seen:
                raise ValueError(f"Duplicate destination index: {idx}")
            seen.add(idx)

    for key, idx in key_to_index.items():
        if key not in tree.nodes:
            raise KeyError(f"Tree node not found: {key!r}")
        if idx < 0 or idx >= len(sequence.token_boxes):
            raise IndexError(
                f"Sequence index {idx} out of range "
                f"[0, {len(sequence.token_boxes)})"
            )

    return [
        TransformFromCopy(tree.nodes[key], sequence.token_boxes[idx])
        for key, idx in key_to_index.items()
    ]


# ---------------------------------------------------------------------------
# Ancestry → mask mapping
# ---------------------------------------------------------------------------


def _compute_ancestors(
    parent_map: dict[str, str | None], *, allow_partial: bool = False
) -> dict[str, set[str]]:
    """Compute ancestry, rejecting cycles and implicit missing-parent roots."""
    ancestors: dict[str, set[str]] = {}
    for key in parent_map:
        anc: set[str] = set()
        current = parent_map.get(key)
        while current is not None:
            if current == key or current in anc:
                raise ValueError(f"Ancestry cycle encountered at {current!r}")
            anc.add(current)
            if current not in parent_map:
                if not allow_partial:
                    raise ValueError(f"Missing parent definition: {current!r}")
                break
            current = parent_map[current]
        ancestors[key] = anc
    return ancestors


def map_ancestry_to_mask(
    parent_map: dict[str, str | None],
    matrix: LabeledMatrix,
    node_to_index: dict[str, int],
    *,
    include_self: bool = True,
    allow_partial: bool = False,
    color: str = ACCENT.base,
    opacity: float = 0.35,
) -> tuple[list[Animation], VGroup]:
    """Highlight matrix cells corresponding to ancestor relationships.

    For each node *n* with ancestor *a*, cell ``(node_to_index[n],
    node_to_index[a])`` is highlighted.  If *include_self* is ``True``
    (default), each node's own diagonal cell is also highlighted.

    Cycles are always rejected. By default every parent must be defined, with
    roots explicitly mapped to ``None``. Set ``allow_partial=True`` to treat
    undefined parents as terminal ancestors (usable as columns, but with no
    inferred row or diagonal). ``node_to_index`` may select a subset of nodes;
    ancestry still traverses unindexed intermediate nodes. Indices must be
    distinct nonnegative integers; highlighted cells must fit the matrix.

    Returns ``(animations, highlight_overlays)``.
    """
    ancestors = _compute_ancestors(parent_map, allow_partial=allow_partial)
    indices: set[int] = set()
    for key, index in node_to_index.items():
        if not isinstance(index, Integral) or isinstance(index, bool):
            raise ValueError("Mask indices must be integers")
        if index < 0:
            raise IndexError(f"Mask index {index} must be nonnegative")
        if index in indices:
            raise ValueError(f"Duplicate mask index: {index}")
        indices.add(index)
        if key not in parent_map and not allow_partial:
            raise ValueError(f"Missing node definition: {key!r}")
    coords: list[tuple[int, int]] = []

    for node_key, anc_set in ancestors.items():
        if node_key not in node_to_index:
            continue
        row = node_to_index[node_key]
        for anc_key in sorted(anc_set):
            if anc_key in node_to_index:
                coords.append((row, node_to_index[anc_key]))
        if include_self:
            coords.append((row, row))

    for row, column in coords:
        if row >= len(matrix.cells) or column >= len(matrix.cells[0]):
            raise IndexError(f"Mask cell {(row, column)} out of range")

    # Deduplicate preserving order
    seen: set[tuple[int, int]] = set()
    unique: list[tuple[int, int]] = []
    for c in coords:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    overlays = matrix.highlight_cells(unique, color=color, opacity=opacity)
    anims = [FadeIn(overlay) for overlay in overlays]
    return anims, overlays


# ---------------------------------------------------------------------------
# Semantic focus transition
# ---------------------------------------------------------------------------


def semantic_focus(
    targets: Mobject | Sequence[Mobject],
    context: Sequence[Mobject],
    *,
    dim_opacity: float = DIM_OPACITY,
    use_overlay: bool = False,
    overlay_opacity: float = 0.55,
) -> tuple[list[Animation], FocusContext, Mobject | None]:
    """Compose focus helpers into a purposeful emphasis transition.

    Wraps :func:`~manim_lib.focus.focus_on` and optionally adds a
    full-frame dim overlay from :func:`~manim_lib.composition.dim_overlay`.

    Returns ``(enter_animations, focus_ctx, overlay_or_none)``.  Pass
    *focus_ctx* and *overlay_or_none* to :func:`restore_semantic_focus`
    when the emphasis phase is over.
    """
    anims, ctx = focus_on(targets, context=context, dim_opacity=dim_opacity)
    overlay = None
    if use_overlay:
        overlay = dim_overlay(opacity=overlay_opacity)
        anims.insert(0, FadeIn(overlay))
    return anims, ctx, overlay


def restore_semantic_focus(
    context: Sequence[Mobject],
    focus_ctx: FocusContext,
    overlay: Mobject | None = None,
) -> list[Animation]:
    """Restore mobjects after a :func:`semantic_focus` phase."""
    anims = restore_focus(context, focus_ctx)
    if overlay is not None:
        anims.append(FadeOut(overlay))
    return anims


# ---------------------------------------------------------------------------
# Section transition
# ---------------------------------------------------------------------------


def section_transition(
    anchor: Mobject,
    others: Sequence[Mobject],
    *,
    fade_out: bool = True,
    dim_opacity: float = DIM_OPACITY,
) -> list[Animation]:
    """Return animations preserving *anchor* while fading or dimming *others*.

    When *fade_out* is ``True`` (default), others are removed with
    ``FadeOut``.  When ``False``, others are dimmed to *dim_opacity*,
    keeping them as faint context.

    *anchor* is automatically excluded even if accidentally included in
    *others*.
    """
    anims: list[Animation] = []
    anchor_id = id(anchor)
    for mob in others:
        if id(mob) == anchor_id:
            continue
        if fade_out:
            anims.append(FadeOut(mob))
        else:
            anims.append(mob.animate.set_opacity(dim_opacity))
    return anims


# ---------------------------------------------------------------------------
# Identity-preserving rearrangement
# ---------------------------------------------------------------------------


def identity_rearrange(
    sources: Sequence[Mobject],
    destinations: Sequence[Mobject | np.ndarray | tuple],
) -> list[Animation]:
    """Return animations that move each *source* to its *destination* position.

    Unlike :func:`map_tree_to_sequence` (which creates ``TransformFromCopy``
    duplicates), this performs a genuine identity-preserving move: the same
    Python objects animate to new positions, so every later reference to them
    still reaches the on-screen mobject.

    *destinations* may be ``Mobject`` instances (moved to their center),
    ``ndarray`` / tuple coordinates, or any mix of both.
    """
    if len(sources) != len(destinations):
        raise ValueError(
            f"sources ({len(sources)}) and destinations "
            f"({len(destinations)}) must have equal length"
        )
    if not sources:
        return []
    anims: list[Animation] = []
    for src, dst in zip(sources, destinations):
        if isinstance(dst, Mobject):
            target = dst.get_center()
        else:
            target = np.array(dst, dtype=float)
        anims.append(src.animate.move_to(target))
    return anims


__all__ = [
    "grow_branch",
    "identity_rearrange",
    "map_ancestry_to_mask",
    "map_tree_to_sequence",
    "restore_semantic_focus",
    "section_transition",
    "semantic_focus",
]
