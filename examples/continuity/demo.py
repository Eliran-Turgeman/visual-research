"""Continuity API proof-of-concept: distribution → branch → sequence → mask.

This is a low-complexity API exercise, not a polished episode.  Run::

    .\.venv\Scripts\manim render -ql --disable_caching examples/continuity/demo.py ContinuityDemo
"""

from manim import DOWN, LEFT, RIGHT, FadeIn, FadeOut, Scene, config

from manim_lib import LabeledMatrix, StableTree, TokenSequence, TreeNode
from manim_lib.continuity import (
    grow_branch,
    map_ancestry_to_mask,
    map_tree_to_sequence,
    restore_semantic_focus,
    section_transition,
    semantic_focus,
)
from manim_lib.probability import ProbabilityDistribution, animate_mass_transfer
from manim_lib.theme import ACCENT, BACKGROUND, SPACING


class ContinuityDemo(Scene):
    """Exercise the full continuity chain at minimal complexity."""

    def construct(self):
        self.camera.background_color = BACKGROUND

        # ── 1. Probability distribution ──────────────────────────
        dist = ProbabilityDistribution(
            {"x": ("x", 0.50), "y": ("y", 0.30), "z": ("z", 0.20)}
        )
        dist.to_edge(LEFT, buff=SPACING.lg)
        self.play(FadeIn(dist))
        self.wait(0.3)

        # ── 2. Build tree by growing branches ────────────────────
        tree = StableTree()
        root = TreeNode("root", radius=0.28)
        tree.add_node("root", root, (2.0, 2.0, 0))
        self.play(FadeIn(tree))

        positions = {"x": (0.5, 0.3, 0), "y": (2.0, 0.3, 0), "z": (3.5, 0.3, 0)}
        for key in ["x", "y", "z"]:
            entry = dist.entries[key]
            child = TreeNode(key, radius=0.28)
            branch_anims, _edge = grow_branch(
                tree, "root", key, child, positions[key], label=f"{entry.value:.1f}"
            )
            mass_anim = animate_mass_transfer(entry, child)
            entry.highlight(ACCENT.base)
            self.play(mass_anim, *branch_anims)
            self.wait(0.2)

        self.wait(0.3)

        # ── 3. Section transition: keep tree, fade distribution ──
        self.play(*section_transition(tree, [dist]))
        self.wait(0.2)

        # ── 4. Tree → sequence ───────────────────────────────────
        seq = TokenSequence("root", "x", "y", "z")
        seq.next_to(tree, DOWN, buff=SPACING.lg)
        self.play(FadeIn(seq))

        seq_anims = map_tree_to_sequence(
            tree, {"root": 0, "x": 1, "y": 2, "z": 3}, seq
        )
        self.play(*seq_anims)
        self.wait(0.3)

        # ── 5. Semantic focus on tree ────────────────────────────
        focus_anims, focus_ctx, overlay = semantic_focus(
            tree, [tree, seq], use_overlay=False
        )
        if focus_anims:
            self.play(*focus_anims)
        self.wait(0.2)
        restore_anims = restore_semantic_focus([tree, seq], focus_ctx)
        if restore_anims:
            self.play(*restore_anims)

        # ── 6. Ancestry → attention mask ─────────────────────────
        parent_map = {"root": None, "x": "root", "y": "root", "z": "root"}
        labels = ["root", "x", "y", "z"]
        mask_values = [
            [1, 0, 0, 0],
            [1, 1, 0, 0],
            [1, 0, 1, 0],
            [1, 0, 0, 1],
        ]
        matrix = LabeledMatrix(
            mask_values, row_labels=labels, column_labels=labels
        )
        matrix.next_to(seq, DOWN, buff=SPACING.md)
        self.play(FadeIn(matrix))

        mask_anims, _overlays = map_ancestry_to_mask(
            parent_map, matrix, {"root": 0, "x": 1, "y": 2, "z": 3}
        )
        self.play(*mask_anims)
        self.wait(0.5)

        # ── Cleanup ──────────────────────────────────────────────
        self.play(*[FadeOut(mob) for mob in self.mobjects])
