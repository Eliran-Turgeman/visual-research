"""Layout, invariant, storyboard-consistency, and algorithm tests for the
DDTree visual episode.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# ── Load modules from the ddtree_visual directory ─────────────────────────

_DDTREE_VIS_DIR = Path(__file__).resolve().parent.parent / "examples" / "ddtree_visual"
_DDTREE_ALGO_DIR = Path(__file__).resolve().parent.parent / "examples" / "ddtree_dflash"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # register so dataclass introspection works
    saved_path = sys.path[:]
    sys.path.insert(0, str(path.parent))
    if str(_DDTREE_ALGO_DIR) not in sys.path:
        sys.path.insert(0, str(_DDTREE_ALGO_DIR))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved_path
        # Clean up plain 'storyboard' from sys.modules to avoid leaking
        # into other test files that have their own storyboard.
        sys.modules.pop("storyboard", None)
        sys.modules.pop("algorithm", None)
    return mod


_storyboard = _load_module("ddtree_storyboard", _DDTREE_VIS_DIR / "storyboard.py")
_scene_mod = _load_module("ddtree_scene", _DDTREE_VIS_DIR / "scene.py")

BEATS = _storyboard.BEATS
BEAT_COUNT = _storyboard.BEAT_COUNT
PREFIXES = _storyboard.PREFIXES
NODE_BUDGET = _storyboard.NODE_BUDGET
FLATTEN_ORDER = _storyboard.FLATTEN_ORDER
FLATTEN_TOKENS = _storyboard.FLATTEN_TOKENS
FLATTEN_POSITION_IDS = _storyboard.FLATTEN_POSITION_IDS
VISIBILITY_MASK = _storyboard.VISIBILITY_MASK
VERIFICATION_PATH = _storyboard.VERIFICATION_PATH
TARGET_CHOICES = _storyboard.TARGET_CHOICES
COMMITTED_TOKENS = _storyboard.COMMITTED_TOKENS
BONUS_TOKEN = _storyboard.BONUS_TOKEN
VANILLA_PATH = _storyboard.VANILLA_PATH
Q1 = _storyboard.Q1
Q2 = _storyboard.Q2
Q3 = _storyboard.Q3

TREE_POSITIONS = _scene_mod.TREE_POSITIONS
NODE_RADIUS = _scene_mod.NODE_RADIUS
SCORE_STYLE = _scene_mod.SCORE_STYLE
DDTreeVisualExplainer = _scene_mod.DDTreeVisualExplainer

from manim import DOWN
from manim_lib.layout import (
    within_safe_frame,
    assert_no_overlaps,
    contains,
)
from manim_lib.trees import StableTree, TreeNode
from manim_lib.tokens import TokenBox, TokenSequence
from manim_lib.probability import ProbabilityDistribution


# ── Storyboard consistency ────────────────────────────────────────────────

class TestStoryboardConsistency:

    def test_beat_count_matches_tuple_length(self):
        assert BEAT_COUNT == len(BEATS)

    def test_beat_indices_are_sequential(self):
        for i, beat in enumerate(BEATS):
            assert beat.index == i, f"Beat at position {i} has index {beat.index}"

    def test_all_beats_have_narration(self):
        for beat in BEATS:
            assert beat.narration.strip(), f"Beat {beat.index} has empty narration"

    def test_all_beats_have_valid_duration_ranges(self):
        for beat in BEATS:
            lo, hi = beat.duration_range
            assert 0 < lo <= hi, (
                f"Beat {beat.index} has invalid duration range ({lo}, {hi})"
            )

    def test_vanilla_path_is_argmax(self):
        """The vanilla path must be the argmax at each position."""
        marginals = [Q1, Q2, Q3]
        for i, tok in enumerate(VANILLA_PATH):
            best = max(marginals[i], key=marginals[i].get)
            assert tok == best, (
                f"Position {i}: vanilla '{tok}' is not argmax "
                f"(expected '{best}')"
            )


# ── Toy numerical invariants ─────────────────────────────────────────────

class TestToyNumerics:

    def test_marginals_sum_to_one(self):
        for name, dist in [("Q1", Q1), ("Q2", Q2), ("Q3", Q3)]:
            total = sum(dist.values())
            assert abs(total - 1.0) < 1e-6, f"{name} sums to {total}"

    def test_prefix_count_matches_budget(self):
        assert len(PREFIXES) == NODE_BUDGET

    def test_prefix_masses_are_non_increasing(self):
        masses = [p.mass for p in PREFIXES]
        assert masses == sorted(masses, reverse=True)

    def test_prefix_set_is_prefix_closed(self):
        keys = {p.key for p in PREFIXES}
        keys.add("root")
        for p in PREFIXES:
            assert p.parent in keys, f"Parent '{p.parent}' of '{p.key}' not in tree"


# ── Flatten data invariants ──────────────────────────────────────────────

class TestFlattenData:

    def test_flatten_order_length(self):
        assert len(FLATTEN_ORDER) == NODE_BUDGET + 1  # root + budget

    def test_flatten_tokens_match_order(self):
        assert len(FLATTEN_TOKENS) == len(FLATTEN_ORDER)

    def test_position_ids_match_depth(self):
        """Position IDs must equal tree depth for each node."""
        depth_map = {"root": 0}
        for p in PREFIXES:
            depth_map[p.key] = p.depth
        for i, key in enumerate(FLATTEN_ORDER):
            assert FLATTEN_POSITION_IDS[i] == depth_map[key], (
                f"Position ID for '{key}' should be {depth_map[key]}, "
                f"got {FLATTEN_POSITION_IDS[i]}"
            )

    def test_visibility_mask_shape(self):
        n = len(FLATTEN_ORDER)
        assert len(VISIBILITY_MASK) == n
        for row in VISIBILITY_MASK:
            assert len(row) == n

    def test_visibility_mask_diagonal_is_one(self):
        """Every node can attend to itself."""
        for i in range(len(VISIBILITY_MASK)):
            assert VISIBILITY_MASK[i][i] == 1

    def test_visibility_mask_is_ancestor_only(self):
        """Each row's 1-cells correspond exactly to self + ancestors."""
        parent_map = {"root": None}
        for p in PREFIXES:
            parent_map[p.key] = p.parent
        key_to_idx = {k: i for i, k in enumerate(FLATTEN_ORDER)}

        for row_idx, key in enumerate(FLATTEN_ORDER):
            expected_ones = {row_idx}  # self
            current = parent_map.get(key)
            while current is not None:
                expected_ones.add(key_to_idx[current])
                current = parent_map.get(current)
            actual_ones = {
                col for col in range(len(VISIBILITY_MASK[row_idx]))
                if VISIBILITY_MASK[row_idx][col] == 1
            }
            assert actual_ones == expected_ones, (
                f"Row {row_idx} ({key}): expected {expected_ones}, "
                f"got {actual_ones}"
            )


# ── Verification walk ────────────────────────────────────────────────────

class TestVerification:

    def test_verification_path_is_in_tree(self):
        tree_keys = {"root"} | {p.key for p in PREFIXES}
        for key in VERIFICATION_PATH:
            assert key in tree_keys

    def test_committed_tokens_match_accepted_choices(self):
        accepted = tuple(
            tok for tok, ok in TARGET_CHOICES if ok
        )
        assert accepted == COMMITTED_TOKENS

    def test_bonus_token_is_the_rejected_choice(self):
        rejected = [tok for tok, ok in TARGET_CHOICES if not ok]
        assert len(rejected) == 1
        assert rejected[0] == BONUS_TOKEN

    def test_target_choices_never_equal_drafter_argmax_on_same_path(self):
        """The drafter's argmax is 'the'; target picks 'a'.
        This verifies the storyboard's central narrative premise."""
        assert TARGET_CHOICES[0][0] != VANILLA_PATH[0]


# ── Layout: tree positions ───────────────────────────────────────────────

class TestTreeLayout:

    def _build_tree(self) -> StableTree:
        tree = StableTree()
        tree.add_node(
            "root", TreeNode("well", radius=NODE_RADIUS),
            TREE_POSITIONS["root"],
        )
        for prefix in PREFIXES:
            node = TreeNode(
                prefix.token,
                score=f"{prefix.mass:.3f}",
                radius=NODE_RADIUS,
                score_direction=SCORE_STYLE["direction"],
                score_buff=SCORE_STYLE["buff"],
                score_font_size=SCORE_STYLE["font_size"],
            )
            tree.add_node(prefix.key, node, TREE_POSITIONS[prefix.key])
            tree.connect(prefix.parent, prefix.key)
        return tree

    def test_all_tree_nodes_within_safe_frame(self):
        tree = self._build_tree()
        for key, node in tree.nodes.items():
            assert within_safe_frame(node.circle), (
                f"{key} circle outside safe frame"
            )

    def test_tree_labels_inside_circles(self):
        tree = self._build_tree()
        for key, node in tree.nodes.items():
            assert contains(node.circle, node.label), (
                f"{key} label escapes circle"
            )

    def test_tree_positions_cover_all_prefixes(self):
        expected = {"root"} | {p.key for p in PREFIXES}
        assert set(TREE_POSITIONS.keys()) == expected


# ── Scene beat alignment ─────────────────────────────────────────────────

class TestSceneBeatAlignment:

    def test_scene_has_correct_beat_methods(self):
        actual = [m for m in dir(DDTreeVisualExplainer) if m.startswith("_beat_")]
        assert len(actual) == BEAT_COUNT, (
            f"Scene has {len(actual)} beat methods "
            f"but storyboard has {BEAT_COUNT} beats"
        )


# ── 480p readability guards ──────────────────────────────────────────────

class TestReadabilityAtLowRes:
    """Verify that score labels and position-ID labels are readable at 480p."""

    def test_score_font_size_at_least_14(self):
        """Score labels below 14pt are unreadable at 480p."""
        assert SCORE_STYLE["font_size"] >= 14, (
            f"SCORE_STYLE font_size {SCORE_STYLE['font_size']} is too small for 480p"
        )

    def test_score_labels_do_not_escape_safe_frame(self):
        """Score labels with the increased font must still fit."""
        from manim_lib.layout import within_safe_frame
        tree = StableTree()
        tree.add_node(
            "root", TreeNode("well", radius=NODE_RADIUS),
            TREE_POSITIONS["root"],
        )
        for prefix in PREFIXES:
            node = TreeNode(
                prefix.token,
                score=f"{prefix.mass:.3f}",
                radius=NODE_RADIUS,
                score_direction=SCORE_STYLE["direction"],
                score_buff=SCORE_STYLE["buff"],
                score_font_size=SCORE_STYLE["font_size"],
            )
            tree.add_node(prefix.key, node, TREE_POSITIONS[prefix.key])
            tree.connect(prefix.parent, prefix.key)
        for key, node in tree.nodes.items():
            if node.score_label is not None:
                assert within_safe_frame(node.score_label), (
                    f"{key} score label outside safe frame"
                )
