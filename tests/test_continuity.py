"""Tests for continuity-first animation primitives and probability visuals.

Validates object identity, source/destination mappings, geometry, and error
handling.  Does *not* assert internal Manim animation implementation details.
"""

import numpy as np
import pytest
from manim import Animation, Circle, Rectangle

from manim_lib.continuity import (
    grow_branch,
    map_ancestry_to_mask,
    map_tree_to_sequence,
    restore_semantic_focus,
    section_transition,
    semantic_focus,
)
from manim_lib.focus import FocusContext
from manim_lib.matrices import LabeledMatrix
from manim_lib.probability import (
    DistributionEntry,
    ProbabilityDistribution,
    animate_mass_transfer,
)
from manim_lib.tokens import TokenSequence
from manim_lib.trees import StableTree, TreeNode


# ── ProbabilityDistribution ───────────────────────────────────────────────


class TestProbabilityDistribution:
    def test_entries_preserve_identity_and_values(self):
        dist = ProbabilityDistribution(
            {"a": ("Alpha", 0.5), "b": ("Beta", 0.3), "c": ("Gamma", 0.2)}
        )
        assert set(dist.entries.keys()) == {"a", "b", "c"}
        assert dist.entries["a"].value == 0.5
        assert dist.entries["b"].token_text == "Beta"

    def test_entry_anchors_are_3d_arrays(self):
        entry = DistributionEntry("k", "tok", 0.4)
        for anchor in (entry.token_anchor, entry.value_anchor, entry.highlight_anchor):
            assert isinstance(anchor, np.ndarray)
            assert anchor.shape == (3,)

    def test_bar_width_proportional_to_value(self):
        hi = DistributionEntry("hi", "H", 0.9, max_bar_width=2.0)
        lo = DistributionEntry("lo", "L", 0.1, max_bar_width=2.0)
        assert hi.bar.width > lo.bar.width

    def test_highlight_changes_entry_and_returns_self(self):
        dist = ProbabilityDistribution({"x": ("X", 0.8)})
        entry = dist.highlight_entry("x", color="#ff0000")
        assert entry is dist.entries["x"]

    def test_missing_key_raises(self):
        dist = ProbabilityDistribution({"x": ("X", 0.5)})
        with pytest.raises(KeyError):
            dist.highlight_entry("missing")

    def test_empty_entries_rejected(self):
        with pytest.raises(ValueError):
            ProbabilityDistribution({})

    def test_mass_transfer_returns_animation(self):
        entry = DistributionEntry("k", "tok", 0.6)
        target = Circle(radius=0.3)
        anim = animate_mass_transfer(entry, target)
        assert isinstance(anim, Animation)

    def test_mass_transfer_custom_source(self):
        entry = DistributionEntry("k", "tok", 0.6)
        target = Circle(radius=0.3)
        anim = animate_mass_transfer(entry, target, source_part=entry.value_label)
        assert isinstance(anim, Animation)


# ── grow_branch ───────────────────────────────────────────────────────────


class TestGrowBranch:
    def _make_tree(self):
        tree = StableTree()
        tree.add_node("root", TreeNode("R"), (0, 2, 0))
        return tree

    def test_adds_node_and_edge_to_tree(self):
        tree = self._make_tree()
        anims, edge = grow_branch(
            tree, "root", "child", TreeNode("C"), (0, 0, 0)
        )
        assert "child" in tree.nodes
        assert ("root", "child") in tree.edges
        assert edge is tree.edges[("root", "child")]

    def test_returns_at_least_two_animations(self):
        tree = self._make_tree()
        anims, _ = grow_branch(
            tree, "root", "child", TreeNode("C"), (-1, 0, 0)
        )
        assert len(anims) >= 2
        assert all(isinstance(a, Animation) for a in anims)

    def test_label_adds_extra_animation(self):
        tree = self._make_tree()
        anims, _ = grow_branch(
            tree, "root", "child", TreeNode("C"), (1, 0, 0), label="0.5"
        )
        assert len(anims) == 3

    def test_missing_parent_raises(self):
        tree = self._make_tree()
        with pytest.raises(KeyError, match="Parent"):
            grow_branch(tree, "nonexistent", "child", TreeNode("C"), (0, 0, 0))

    def test_duplicate_child_key_raises(self):
        tree = self._make_tree()
        grow_branch(tree, "root", "c1", TreeNode("C"), (0, 0, 0))
        with pytest.raises(ValueError):
            grow_branch(tree, "root", "c1", TreeNode("D"), (1, 0, 0))

    def test_child_position_is_correct(self):
        tree = self._make_tree()
        pos = (2.0, -1.0, 0.0)
        grow_branch(tree, "root", "ch", TreeNode("X"), pos)
        center = tree.nodes["ch"].get_center()
        assert center[0] == pytest.approx(pos[0], abs=0.01)
        assert center[1] == pytest.approx(pos[1], abs=0.01)

    def test_edge_connects_parent_to_child(self):
        tree = self._make_tree()
        anims, edge = grow_branch(
            tree, "root", "ch", TreeNode("X"), (2, -1, 0)
        )
        # Edge should span from near parent to near child
        start_y = edge.get_start()[1]
        end_y = edge.get_end()[1]
        assert start_y > end_y  # parent is higher


# ── map_tree_to_sequence ─────────────────────────────────────────────────


class TestMapTreeToSequence:
    def _make_tree_and_seq(self):
        tree = StableTree()
        tree.add_node("a", TreeNode("A"), (-1, 0, 0))
        tree.add_node("b", TreeNode("B"), (0, 0, 0))
        tree.add_node("c", TreeNode("C"), (1, 0, 0))
        seq = TokenSequence("A", "B", "C")
        return tree, seq

    def test_returns_correct_number_of_animations(self):
        tree, seq = self._make_tree_and_seq()
        anims = map_tree_to_sequence(tree, {"a": 0, "b": 1, "c": 2}, seq)
        assert len(anims) == 3
        assert all(isinstance(a, Animation) for a in anims)

    def test_partial_mapping(self):
        tree, seq = self._make_tree_and_seq()
        anims = map_tree_to_sequence(tree, {"a": 1}, seq)
        assert len(anims) == 1

    def test_duplicate_indices_rejected(self):
        tree, seq = self._make_tree_and_seq()
        with pytest.raises(ValueError, match="Duplicate"):
            map_tree_to_sequence(tree, {"a": 0, "b": 0}, seq)

    def test_missing_key_rejected(self):
        tree, seq = self._make_tree_and_seq()
        with pytest.raises(KeyError, match="not found"):
            map_tree_to_sequence(tree, {"nonexistent": 0}, seq)

    def test_out_of_range_index_rejected(self):
        tree, seq = self._make_tree_and_seq()
        with pytest.raises(IndexError, match="out of range"):
            map_tree_to_sequence(tree, {"a": 99}, seq)

    def test_negative_index_rejected(self):
        tree, seq = self._make_tree_and_seq()
        with pytest.raises(IndexError, match="out of range"):
            map_tree_to_sequence(tree, {"a": -1}, seq)


# ── map_ancestry_to_mask ─────────────────────────────────────────────────


class TestMapAncestryToMask:
    def test_simple_chain_highlights_correct_cells(self):
        parent_map = {"root": None, "A": "root", "B": "A"}
        node_to_index = {"root": 0, "A": 1, "B": 2}
        matrix = LabeledMatrix(
            [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            row_labels=["root", "A", "B"],
            column_labels=["root", "A", "B"],
        )
        anims, overlays = map_ancestry_to_mask(
            parent_map, matrix, node_to_index, include_self=True
        )
        # root: self → (0,0)
        # A: ancestor=root, self → (1,0), (1,1)
        # B: ancestors={A,root}, self → (2,1), (2,0), (2,2)
        assert len(overlays) == 6
        assert len(anims) == 6
        assert all(isinstance(a, Animation) for a in anims)

    def test_no_self_attention(self):
        parent_map = {"root": None, "A": "root"}
        node_to_index = {"root": 0, "A": 1}
        matrix = LabeledMatrix([[0, 0], [0, 0]])
        anims, overlays = map_ancestry_to_mask(
            parent_map, matrix, node_to_index, include_self=False
        )
        # Only A→root: (1, 0)
        assert len(overlays) == 1

    def test_missing_nodes_in_index_skipped(self):
        parent_map = {"root": None, "A": "root", "B": "unknown"}
        node_to_index = {"root": 0, "A": 1}
        matrix = LabeledMatrix([[0, 0], [0, 0]])
        anims, overlays = map_ancestry_to_mask(
            parent_map, matrix, node_to_index, include_self=False
        )
        assert len(overlays) == 1

    def test_wide_tree_no_cross_sibling_cells(self):
        # root -> A, root -> B  (siblings should NOT attend to each other)
        parent_map = {"root": None, "A": "root", "B": "root"}
        node_to_index = {"root": 0, "A": 1, "B": 2}
        matrix = LabeledMatrix([[0, 0, 0], [0, 0, 0], [0, 0, 0]])
        _, overlays = map_ancestry_to_mask(
            parent_map, matrix, node_to_index, include_self=False
        )
        # A→root: (1,0), B→root: (2,0). No (1,2) or (2,1).
        assert len(overlays) == 2

    def test_empty_parent_map_with_self(self):
        parent_map = {"only": None}
        node_to_index = {"only": 0}
        matrix = LabeledMatrix([[0]])
        _, overlays = map_ancestry_to_mask(
            parent_map, matrix, node_to_index, include_self=True
        )
        assert len(overlays) == 1  # just the diagonal


# ── semantic_focus ────────────────────────────────────────────────────────


class TestSemanticFocus:
    def test_without_overlay(self):
        target = Circle(radius=0.3)
        ctx_mob = Rectangle(width=1, height=1)
        ctx_mob.set_opacity(1.0)
        anims, focus_ctx, overlay = semantic_focus(
            target, [target, ctx_mob], use_overlay=False
        )
        assert isinstance(focus_ctx, FocusContext)
        assert overlay is None
        assert len(anims) >= 1

    def test_with_overlay(self):
        target = Circle(radius=0.3)
        ctx_mob = Rectangle(width=1, height=1)
        ctx_mob.set_opacity(1.0)
        anims, focus_ctx, overlay = semantic_focus(
            target, [target, ctx_mob], use_overlay=True
        )
        assert overlay is not None

    def test_restore_returns_animations(self):
        target = Circle(radius=0.3)
        ctx_mob = Rectangle(width=1, height=1)
        ctx_mob.set_opacity(1.0)
        _, focus_ctx, overlay = semantic_focus(
            target, [target, ctx_mob], use_overlay=True
        )
        restore_anims = restore_semantic_focus(
            [target, ctx_mob], focus_ctx, overlay
        )
        assert len(restore_anims) >= 1

    def test_restore_without_overlay(self):
        target = Circle(radius=0.3)
        ctx_mob = Rectangle(width=1, height=1)
        ctx_mob.set_opacity(1.0)
        _, focus_ctx, _ = semantic_focus(target, [ctx_mob])
        restore_anims = restore_semantic_focus([ctx_mob], focus_ctx, None)
        assert len(restore_anims) >= 1


# ── section_transition ────────────────────────────────────────────────────


class TestSectionTransition:
    def test_fade_out_excludes_anchor(self):
        anchor = Circle(radius=0.3)
        other1 = Rectangle(width=1, height=1)
        other2 = Rectangle(width=2, height=1)
        anims = section_transition(anchor, [anchor, other1, other2])
        assert len(anims) == 2

    def test_dim_mode(self):
        anchor = Circle(radius=0.3)
        other = Rectangle(width=1, height=1)
        anims = section_transition(anchor, [other], fade_out=False)
        assert len(anims) == 1
        # .animate builders are valid play() arguments but not Animation instances

    def test_empty_others(self):
        anchor = Circle(radius=0.3)
        anims = section_transition(anchor, [])
        assert anims == []

    def test_only_anchor_in_list(self):
        anchor = Circle(radius=0.3)
        anims = section_transition(anchor, [anchor])
        assert anims == []
