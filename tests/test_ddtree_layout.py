"""Integration-level layout regression test for the ddtree_dflash example's
best-first tree.

This builds the exact 7-node (plus root) tree the scene renders for its
"best-first tree construction" section, reusing the scene's own radius,
node positions, and score placement (rather than re-typing those numbers
here, which would silently drift from the real scene and stop catching
regressions). It then runs the shared, generic layout utilities against
that concrete geometry, so a pass here reflects a real property of the
scene's chosen layout, not a tautology derived from the same numbers.
"""

import sys
from pathlib import Path

from manim import DOWN

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "ddtree_dflash"))

from algorithm import Q1, Q2, Q3, best_first_prefixes  # noqa: E402
from scene import (  # noqa: E402
    BEST_FIRST_POSITIONS,
    BEST_FIRST_RADIUS,
    BEST_FIRST_SCORE_STYLE,
)

from manim_lib import StableTree, TreeNode, assert_no_overlaps, contains, within_safe_frame


def _toy(value: float, digits: int) -> str:
    """Mirror the scene's own toy-probability formatting (no leading zero)."""
    text = f"{value:.{digits}f}"
    return text[1:] if text.startswith("0.") else text


def _build_best_first_tree() -> StableTree:
    """Reconstruct the scene's exact final tree geometry (nodes, positions,
    radius, and scores), independent of any narration/animation.
    """
    tree = StableTree()
    tree.add_node("root", TreeNode("b", radius=BEST_FIRST_RADIUS), BEST_FIRST_POSITIONS["root"])

    for prefix in best_first_prefixes([Q1, Q2, Q3], budget=7):
        score_text = _toy(prefix.mass, 3)
        if prefix.depth == 1:
            node = TreeNode(
                prefix.token,
                score=score_text,
                radius=BEST_FIRST_RADIUS,
                score_direction=BEST_FIRST_SCORE_STYLE["direction"],
                score_buff=BEST_FIRST_SCORE_STYLE["buff"],
                score_font_size=BEST_FIRST_SCORE_STYLE["font_size"],
            )
        else:
            node = TreeNode(prefix.token, radius=BEST_FIRST_RADIUS)
        tree.add_node(prefix.key, node, BEST_FIRST_POSITIONS[prefix.key])
        tree.connect(prefix.parent, prefix.key)
        if prefix.depth != 1:
            node.set_score(score_text, **BEST_FIRST_SCORE_STYLE)

    return tree


def test_best_first_tree_has_eight_nodes_at_the_scenes_positions():
    tree = _build_best_first_tree()
    # Not tautological on its own, but establishes that the rest of this
    # test actually exercises all 7 popped prefixes plus the root, matching
    # the scene's "B = 7" heading.
    assert set(tree.nodes) == set(BEST_FIRST_POSITIONS)
    # ``StableTree.add_node`` moves each node's whole bounding box (circle,
    # token label, and -- for depth-one nodes only -- an already-attached
    # score) to its named position, so the circle itself can sit a little
    # off that point once a score is baked in below/right of it. Bound that
    # drift instead of asserting exact equality, which would be wrong for
    # depth-one nodes and tautological for the rest.
    for key, node in tree.nodes.items():
        drift = tuple(node.circle.get_center() - BEST_FIRST_POSITIONS[key])
        assert max(abs(component) for component in drift) < 0.15, (
            f"{key}'s circle drifted too far from its named position: {drift}"
        )


def test_best_first_tree_token_labels_stay_inside_their_node_circles():
    tree = _build_best_first_tree()
    for key, node in tree.nodes.items():
        assert contains(node.circle, node.label), f"{key}'s token label escapes its circle"


def test_best_first_tree_nodes_and_scores_stay_within_safe_frame():
    tree = _build_best_first_tree()
    for key, node in tree.nodes.items():
        assert within_safe_frame(node.circle), f"{key}'s circle falls outside the safe frame"
        if node.score_label is not None:
            assert within_safe_frame(
                node.score_label
            ), f"{key}'s score label falls outside the safe frame"


def test_best_first_tree_has_no_unintended_circle_or_score_collisions():
    tree = _build_best_first_tree()
    objects = []
    labels = []
    for key, node in tree.nodes.items():
        objects.append(node.circle)
        labels.append(f"{key} circle")
        if node.score_label is not None:
            objects.append(node.score_label)
            labels.append(f"{key} score")

    # Root has no score by construction; every popped prefix does.
    assert tree.nodes["root"].score_label is None
    assert sum(1 for key in tree.nodes if key != "root") == len(
        [node for node in tree.nodes.values() if node.score_label is not None]
    )

    assert_no_overlaps(objects, labels=labels)


def test_best_first_tree_score_direction_matches_scenes_crowded_layout_choice():
    # A regression guard for the specific reason this scene picks DOWN
    # (rather than the TreeNode default of RIGHT): several siblings sit
    # close enough horizontally that a RIGHT-placed score would collide
    # with the next node. If this ever changes back to the default without
    # adjusting positions, the collision test above is what will fail.
    assert BEST_FIRST_SCORE_STYLE["direction"] is DOWN
