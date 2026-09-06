"""DDTree visual explainer – focused standalone episode.

Continues directly from the DFlash episode: same marginals Q1/Q2/Q3,
same semantic colors, one evolving picture.  Explains why one argmax
path wastes draft probability, how DDTree builds a best-first tree,
flattens it for the target, and verifies with ancestor-only attention.

Imports storyboard.py as the single source of truth for narration text,
toy numbers, and beat structure.  Uses manim_lib primitives and the shared
NarratedScene base class.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    AnimationGroup,
    FadeIn,
    FadeOut,
    GrowFromPoint,
    LaggedStart,
    Line,
    MathTex,
    MoveToTarget,
    RoundedRectangle,
    SurroundingRectangle,
    Text,
    Transform,
    TransformFromCopy,
    VGroup,
    Write,
)

# Algorithm source of truth
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "ddtree_dflash")
)
from algorithm import Q1, Q2, Q3, best_first_prefixes  # noqa: E402

from storyboard import (
    BEATS,
    BEAT_COUNT,
    BONUS_TOKEN,
    COMMITTED_TOKENS,
    FLATTEN_ORDER,
    FLATTEN_POSITION_IDS,
    FLATTEN_TOKENS,
    NODE_BUDGET,
    PREFIXES,
    PRIOR_BONUS,
    TARGET_CHOICES,
    TARGET_FIRST_CHOICE,
    VANILLA_PATH,
    VERIFICATION_PATH,
    VISIBILITY_MASK,
)

from manim_lib.narrated_scene import NarratedScene
from manim_lib.theme import (
    ACCENT,
    BACKGROUND,
    DANGER,
    NEUTRAL,
    PRIMARY,
    SPACING,
    STROKES,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TYPOGRAPHY,
)
from manim_lib.composition import center_group, place_at_safe_edge
from manim_lib.continuity import identity_rearrange, map_ancestry_to_mask
from manim_lib.focus import focus_on, restore_focus
from manim_lib.probability import (
    ProbabilityDistribution,
    animate_mass_transfer,
)
from manim_lib.tokens import TokenBox, TokenSequence, TokenState
from manim_lib.trees import StableTree, TreeNode
from manim_lib.matrices import LabeledMatrix
from manim_lib.computation import Computation, Operand

# ── Layout constants ──────────────────────────────────────────────────────

RIBBON_Y = 3.0
DIST_Y = 1.3
DIST_BAR_WIDTH = 0.9
DIST_FONT_SIZE = 16
DIST_BAR_HEIGHT = 0.20
DIST_BUFF = 0.9

NODE_RADIUS = 0.28
SCORE_STYLE = {"direction": DOWN, "buff": 0.05, "font_size": 12}

TREE_POSITIONS = {
    "root": (0.0, -0.2, 0),
    "the": (-2.3, -1.3, 0),
    "a": (2.3, -1.3, 0),
    "the-model": (-3.3, -2.3, 0),
    "the-system": (-1.2, -2.3, 0),
    "a-model": (2.3, -2.3, 0),
    "the-model-works": (-3.3, -3.2, 0),
    "a-model-works": (2.3, -3.2, 0),
}

FLAT_Y = 1.4
FLAT_TOKEN_WIDTH = 0.82
FLAT_TOKEN_SCALE = 0.62
MASK_CENTER = (0.0, -1.5, 0)

COMMITTED_COLOR = SUCCESS.base
SPECULATIVE_COLOR = PRIMARY.base
TARGET_COLOR = ACCENT.base
BONUS_COLOR = "#e8d44d"

REVIEW_TIMELINE_PATH = Path("media/review/ddtree_visual/timeline.json")

# Positions exposed for layout tests
RIBBON_POSITION = (0.0, RIBBON_Y, 0.0)
SLOT_COUNT = 3


def _toy(value: float, digits: int = 3) -> str:
    """Format a probability without leading zero: .550 not 0.550."""
    text = f"{value:.{digits}f}"
    return text[1:] if text.startswith("0.") else text


# ── Scene ─────────────────────────────────────────────────────────────────


class DDTreeVisualExplainer(NarratedScene):
    """Focused DDTree explainer: tree construction, flattening,
    ancestor-only attention, target verification, lossless commit."""

    review_timeline_path = REVIEW_TIMELINE_PATH
    external_voiceover_subdir = "ddtree_visual_external"

    def setup(self):
        super().setup()
        # Persistent visual state across beats
        self._dist_q1 = None
        self._dist_q2 = None
        self._dist_q3 = None
        self._dist_group = None
        self._dist_labels = None
        self._ribbon = None
        self._tree = None
        self._node_masses = {}
        self._path_tokens = None
        self._flat_seq = None
        self._mask = None
        self._committed_ribbon = None

    def construct(self):
        self._beat_0_single_path_fails()
        self._beat_1_tree_root_and_depth_one()
        self._beat_2_the_model()
        self._beat_3_a_model()
        self._beat_4_complete_budget()
        self._beat_5_flatten()
        self._beat_6_ancestry_mask()
        self._beat_7_target_verify()
        self._beat_8_commit()
        self._finalize()

    # ── Helpers ───────────────────────────────────────────────────────

    def _build_distributions(self):
        """Build the three persistent probability columns."""
        entries_q1 = {
            "the": ("the", Q1["the"]),
            "a": ("a", Q1["a"]),
            "this": ("this", Q1["this"]),
        }
        entries_q2 = {
            "model": ("model", Q2["model"]),
            "system": ("system", Q2["system"]),
            "code": ("code", Q2["code"]),
        }
        entries_q3 = {
            "works": ("works", Q3["works"]),
            "runs": ("runs", Q3["runs"]),
            "fails": ("fails", Q3["fails"]),
        }
        kw = dict(
            max_bar_width=DIST_BAR_WIDTH,
            bar_height=DIST_BAR_HEIGHT,
            font_size=DIST_FONT_SIZE,
            bar_color=SPECULATIVE_COLOR,
        )
        self._dist_q1 = ProbabilityDistribution(entries_q1, **kw)
        self._dist_q2 = ProbabilityDistribution(entries_q2, **kw)
        self._dist_q3 = ProbabilityDistribution(entries_q3, **kw)
        self._dist_group = VGroup(
            self._dist_q1, self._dist_q2, self._dist_q3
        )
        self._dist_group.arrange(RIGHT, buff=DIST_BUFF, aligned_edge=UP)
        self._dist_group.move_to((0, DIST_Y, 0))

        q1l = Text("q₁", font_size=15, color=TEXT_SECONDARY).next_to(
            self._dist_q1, UP, buff=0.12
        )
        q2l = Text("q₂", font_size=15, color=TEXT_SECONDARY).next_to(
            self._dist_q2, UP, buff=0.12
        )
        q3l = Text("q₃", font_size=15, color=TEXT_SECONDARY).next_to(
            self._dist_q3, UP, buff=0.12
        )
        self._dist_labels = VGroup(q1l, q2l, q3l)

    def _build_ribbon(self):
        """Build the committed ribbon at the top."""
        ctx = TokenBox("...", state=TokenState.NEUTRAL, width=0.65, font_size=20)
        bonus = TokenBox(
            PRIOR_BONUS, state=TokenState.ACTIVE, width=0.85, font_size=22
        )
        slots = [
            TokenBox("?", state=TokenState.NEUTRAL, width=0.85, font_size=22)
            for _ in range(SLOT_COUNT)
        ]
        self._ribbon = VGroup(ctx, bonus, *slots)
        self._ribbon.arrange(RIGHT, buff=0.1)
        self._ribbon.move_to((0, RIBBON_Y, 0))
        self._ribbon.scale(0.78)
        self._ribbon_ctx = ctx
        self._ribbon_bonus = bonus
        self._ribbon_slots = slots

    def _dist_entry(self, depth: int, token: str):
        """Return the DistributionEntry for a token at a given depth."""
        dists = [self._dist_q1, self._dist_q2, self._dist_q3]
        return dists[depth - 1].entries[token]

    def _marginal_value(self, depth: int, token: str) -> float:
        """Return the marginal value from Q at the given depth."""
        return [Q1, Q2, Q3][depth - 1][token]

    # ── Beat 0: Single path fails ────────────────────────────────────

    def _beat_0_single_path_fails(self):
        beat = BEATS[0]
        self._build_ribbon()
        self._build_distributions()

        # Small opening question
        question = Text(
            "What if the draft path is wrong?",
            font_size=TYPOGRAPHY.caption.font_size,
            color=TEXT_SECONDARY,
        )
        place_at_safe_edge(question, UP + LEFT, buff=0.2)

        with self.narrate(beat.narration) as tracker:
            self.paced(
                tracker,
                FadeIn(question),
                FadeIn(self._ribbon),
                fraction=0.18,
            )
            self.paced(
                tracker,
                FadeIn(self._dist_group),
                FadeIn(self._dist_labels),
                fraction=0.18,
            )

            # Argmax path appears as speculative tokens
            path_boxes = VGroup(
                *[
                    TokenBox(tok, state=TokenState.SPECULATIVE,
                             width=0.85, font_size=22)
                    for tok in VANILLA_PATH
                ]
            ).arrange(RIGHT, buff=0.1)
            path_boxes.scale(0.78)
            # Position at ribbon slot locations
            for i, box in enumerate(path_boxes):
                box.move_to(self._ribbon_slots[i])
            self._path_tokens = path_boxes

            self.paced(
                tracker,
                *[FadeIn(box, shift=DOWN * 0.1) for box in path_boxes],
                fraction=0.18,
            )

            # Target rejects: highlight 'a' in Q1, red-mark first slot
            reject_mark = SurroundingRectangle(
                path_boxes[0], color=DANGER.base, buff=0.04
            )
            target_label = Text(
                f"target → '{TARGET_FIRST_CHOICE}'",
                font_size=14, color=TARGET_COLOR,
            ).next_to(path_boxes[0], DOWN, buff=0.15)

            a_entry = self._dist_entry(1, "a")
            a_highlight = SurroundingRectangle(
                a_entry, color=TARGET_COLOR, buff=0.04
            )
            wasted_label = Text(
                ".35 wasted", font_size=13, color=DANGER.base,
            ).next_to(a_entry, RIGHT, buff=0.12)

            self.paced(
                tracker,
                FadeIn(reject_mark),
                FadeIn(target_label),
                fraction=0.15,
            )
            self.paced(
                tracker,
                FadeIn(a_highlight),
                FadeIn(wasted_label),
                *[box.animate.set_opacity(0.25) for box in path_boxes[1:]],
                fraction=0.18,
            )
            self.wait(min(0.8, tracker.duration * 0.08))

        # Clean up path tokens and annotations; keep distributions and ribbon
        self.play(
            FadeOut(self._path_tokens),
            FadeOut(reject_mark),
            FadeOut(target_label),
            FadeOut(wasted_label),
            FadeOut(question),
            run_time=0.5,
        )
        self._a_highlight = a_highlight  # keep for beat 1

    # ── Beat 1: Tree root + depth-1 selections ──────────────────────

    def _beat_1_tree_root_and_depth_one(self):
        beat = BEATS[1]

        # Dim distributions and ribbon to make room for tree
        self.play(
            self._dist_group.animate.set_opacity(0.35),
            self._dist_labels.animate.set_opacity(0.35),
            self._ribbon.animate.set_opacity(0.3),
            FadeOut(self._a_highlight),
            run_time=0.6,
        )

        # Build tree with root
        self._tree = StableTree()
        root_node = TreeNode(PRIOR_BONUS, radius=NODE_RADIUS)
        self._tree.add_node("root", root_node, TREE_POSITIONS["root"])
        root_node.highlight(BONUS_COLOR)
        self._node_masses["root"] = 1.0

        # First two prefixes are depth-1
        p_the = PREFIXES[0]  # 'the' at .55
        p_a = PREFIXES[1]    # 'a' at .35

        with self.narrate(beat.narration) as tracker:
            # Root appears
            self.paced(tracker, FadeIn(self._tree), fraction=0.14)

            # Selection 1: 'the'
            n_the = TreeNode(p_the.token, radius=NODE_RADIUS)
            self._tree.add_node(p_the.key, n_the, TREE_POSITIONS[p_the.key])
            n_the.set_score(_toy(p_the.mass), **SCORE_STYLE)
            e_the = self._tree.connect("root", p_the.key)
            self._node_masses[p_the.key] = p_the.mass

            mass_anim_the = animate_mass_transfer(
                self._dist_entry(1, "the"), n_the,
            )
            self.paced(
                tracker,
                GrowFromPoint(e_the, root_node.get_center()),
                FadeIn(n_the, shift=DOWN * 0.08),
                mass_anim_the,
                fraction=0.18,
            )

            # Selection 2: 'a'
            n_a = TreeNode(p_a.token, radius=NODE_RADIUS)
            self._tree.add_node(p_a.key, n_a, TREE_POSITIONS[p_a.key])
            n_a.set_score(_toy(p_a.mass), **SCORE_STYLE)
            e_a = self._tree.connect("root", p_a.key)
            self._node_masses[p_a.key] = p_a.mass

            mass_anim_a = animate_mass_transfer(
                self._dist_entry(1, "a"), n_a,
            )
            self.paced(
                tracker,
                GrowFromPoint(e_a, root_node.get_center()),
                FadeIn(n_a, shift=DOWN * 0.08),
                mass_anim_a,
                fraction=0.18,
            )
            self.wait(min(0.6, tracker.duration * 0.06))

    # ── Beat 2: the-model ────────────────────────────────────────────

    def _beat_2_the_model(self):
        beat = BEATS[2]
        prefix = PREFIXES[2]  # the-model, mass=.330
        self._animate_deep_selection(beat, prefix)

    # ── Beat 3: a-model ──────────────────────────────────────────────

    def _beat_3_a_model(self):
        beat = BEATS[3]
        prefix = PREFIXES[3]  # a-model, mass=.210
        self._animate_deep_selection(beat, prefix)

    # ── Beat 4: Last three selections ────────────────────────────────

    def _beat_4_complete_budget(self):
        beat = BEATS[4]
        remaining = PREFIXES[4:7]  # the-model-works, the-system, a-model-works

        with self.narrate(beat.narration) as tracker:
            for i, prefix in enumerate(remaining):
                parent_mass = self._node_masses[prefix.parent]
                marginal = self._marginal_value(prefix.depth, prefix.token)

                # Build product equation
                eq = MathTex(
                    _toy(parent_mass),
                    r"\times",
                    _toy(marginal, 2),
                    "=",
                    _toy(prefix.mass),
                    font_size=22,
                )
                eq[-1].set_color(BONUS_COLOR)
                eq.next_to(
                    self._tree.nodes[prefix.parent], RIGHT, buff=0.5
                )
                # Clamp equation within frame
                if eq.get_right()[0] > 6.2:
                    eq.shift(LEFT * (eq.get_right()[0] - 6.0))

                # Create node
                node = TreeNode(prefix.token, radius=NODE_RADIUS)
                self._tree.add_node(
                    prefix.key, node, TREE_POSITIONS[prefix.key]
                )
                edge = self._tree.connect(prefix.parent, prefix.key)
                self._node_masses[prefix.key] = prefix.mass

                frac = 0.22 if i < 2 else 0.25
                self.paced(
                    tracker,
                    GrowFromPoint(
                        edge,
                        self._tree.nodes[prefix.parent].get_center(),
                    ),
                    FadeIn(node, shift=DOWN * 0.06),
                    Write(eq),
                    fraction=frac,
                )

                # Attach score and remove equation
                score_label = node.set_score(
                    _toy(prefix.mass), **SCORE_STYLE
                )
                self.paced(
                    tracker, FadeOut(eq), fraction=0.06,
                )

            self.wait(min(0.5, tracker.duration * 0.05))

    def _animate_deep_selection(self, beat, prefix):
        """Animate a single depth>1 selection with visible product."""
        parent_mass = self._node_masses[prefix.parent]
        marginal = self._marginal_value(prefix.depth, prefix.token)
        parent_node = self._tree.nodes[prefix.parent]

        # Highlights
        parent_hl = SurroundingRectangle(
            parent_node.score_label, color=TARGET_COLOR, buff=0.04
        )
        entry = self._dist_entry(prefix.depth, prefix.token)
        entry_hl = SurroundingRectangle(
            entry, color=SPECULATIVE_COLOR, buff=0.04
        )

        # Product equation
        eq = MathTex(
            _toy(parent_mass),
            r"\times",
            _toy(marginal, 2),
            "=",
            _toy(prefix.mass),
            font_size=24,
        )
        eq[-1].set_color(BONUS_COLOR)
        eq.next_to(parent_node, RIGHT, buff=0.6)
        if eq.get_right()[0] > 6.2:
            eq.shift(LEFT * (eq.get_right()[0] - 6.0))

        # Create node
        node = TreeNode(prefix.token, radius=NODE_RADIUS)
        self._tree.add_node(prefix.key, node, TREE_POSITIONS[prefix.key])
        edge = self._tree.connect(prefix.parent, prefix.key)
        self._node_masses[prefix.key] = prefix.mass

        with self.narrate(beat.narration) as tracker:
            self.paced(
                tracker,
                FadeIn(parent_hl), FadeIn(entry_hl),
                fraction=0.14,
            )
            self.paced(
                tracker,
                GrowFromPoint(edge, parent_node.get_center()),
                FadeIn(node, shift=DOWN * 0.06),
                Write(eq),
                fraction=0.28,
            )
            # Score flies from equation result to node
            target_score = node.prepare_score(
                _toy(prefix.mass), **SCORE_STYLE
            )
            result_copy = eq[-1].copy()
            self.add(result_copy)
            self.paced(
                tracker,
                Transform(result_copy, target_score),
                FadeOut(parent_hl), FadeOut(entry_hl),
                fraction=0.22,
            )
            self.remove(result_copy)
            node.attach_score(result_copy)
            self.paced(tracker, FadeOut(eq), fraction=0.08)

    # ── Beat 5: Flatten tree ─────────────────────────────────────────

    def _beat_5_flatten(self):
        beat = BEATS[5]

        # Compute flat positions (horizontal, centered)
        n = len(FLATTEN_ORDER)
        total_w = n * FLAT_TOKEN_WIDTH * FLAT_TOKEN_SCALE
        start_x = -total_w / 2 + FLAT_TOKEN_WIDTH * FLAT_TOKEN_SCALE / 2
        flat_positions = [
            (start_x + i * FLAT_TOKEN_WIDTH * FLAT_TOKEN_SCALE, FLAT_Y, 0)
            for i in range(n)
        ]

        # Collect nodes in flatten order
        nodes = [self._tree.nodes[key] for key in FLATTEN_ORDER]

        # Hide score labels before moving
        score_fadeouts = []
        for key in FLATTEN_ORDER:
            nd = self._tree.nodes[key]
            if nd.score_label is not None:
                score_fadeouts.append(FadeOut(nd.score_label))

        # Fade tree edges
        edge_fadeouts = [FadeOut(e) for e in self._tree.edges.values()]

        # Build rearrangement animations
        rearrange_anims = identity_rearrange(nodes, flat_positions)

        # Scale nodes to match flat tokens
        scale_anims = [nd.animate.scale(0.85) for nd in nodes]

        with self.narrate(beat.narration) as tracker:
            if score_fadeouts:
                self.paced(tracker, *score_fadeouts, fraction=0.12)
            self.paced(
                tracker,
                *edge_fadeouts, *rearrange_anims, *scale_anims,
                fraction=0.40,
            )

            # Position ID labels below each node
            pid_labels = VGroup()
            for i, (key, pid) in enumerate(
                zip(FLATTEN_ORDER, FLATTEN_POSITION_IDS)
            ):
                lbl = Text(
                    f"pos {pid}", font_size=10, color=TEXT_MUTED,
                ).move_to(flat_positions[i]).shift(DOWN * 0.28)
                pid_labels.add(lbl)

            self.paced(
                tracker,
                FadeIn(pid_labels),
                fraction=0.16,
            )
            self.wait(min(0.5, tracker.duration * 0.06))

        self._flat_positions = flat_positions
        self._pid_labels = pid_labels
        self._flat_node_refs = {
            key: self._tree.nodes[key] for key in FLATTEN_ORDER
        }

    # ── Beat 6: Ancestry mask ────────────────────────────────────────

    def _beat_6_ancestry_mask(self):
        beat = BEATS[6]

        # Build mask matrix
        n = len(FLATTEN_ORDER)
        short_labels = [
            FLATTEN_TOKENS[i][:3] for i in range(n)
        ]
        self._mask = LabeledMatrix(
            VISIBILITY_MASK,
            row_labels=short_labels,
            column_labels=short_labels,
            cell_width=0.42,
            cell_height=0.34,
        )
        self._mask.scale(0.85)
        self._mask.move_to(MASK_CENTER)

        with self.narrate(beat.narration) as tracker:
            # Fade in mask frame (labels + grid)
            self.paced(
                tracker,
                FadeIn(
                    VGroup(
                        *self._mask.row_label_mobjects,
                        *self._mask.column_label_mobjects,
                    )
                ),
                fraction=0.12,
            )

            # Progressive row reveal: each row lights ancestry cells
            all_highlights = VGroup()
            for row_idx in range(n):
                row_cells = self._mask.row_group(row_idx)
                # Highlight the 1-cells in this row
                ones = [
                    (row_idx, col)
                    for col in range(n)
                    if VISIBILITY_MASK[row_idx][col] == 1
                ]
                highlights = self._mask.highlight_cells(
                    ones, color=COMMITTED_COLOR, opacity=0.30,
                )
                all_highlights.add(*highlights)
                self.paced(
                    tracker,
                    FadeIn(row_cells),
                    FadeIn(highlights),
                    fraction=0.07,
                )

            self.wait(min(0.5, tracker.duration * 0.06))
            self._mask_highlights = all_highlights

    # ── Beat 7: Target verification ──────────────────────────────────

    def _beat_7_target_verify(self):
        beat = BEATS[7]

        # Build a map from FLATTEN_ORDER keys to flat positions
        key_to_flat_idx = {
            key: i for i, key in enumerate(FLATTEN_ORDER)
        }

        # Verification walk: root → a → a-model; miss on 'runs'
        with self.narrate(beat.narration) as tracker:
            verified_keys = []
            for choice_token, accepted in TARGET_CHOICES:
                if not verified_keys:
                    current_key = "root"
                else:
                    current_key = verified_keys[-1]

                # Find the child key for this choice
                if accepted:
                    # Find the matching child in FLATTEN_ORDER
                    child_key = None
                    for p in PREFIXES:
                        if p.parent == current_key and p.token == choice_token:
                            child_key = p.key
                            break
                    if child_key is None:
                        # Root → first depth-1 match
                        for p in PREFIXES:
                            if p.depth == 1 and p.token == choice_token:
                                child_key = p.key
                                break

                    # Light the node green
                    flat_idx = key_to_flat_idx[child_key]
                    node = self._flat_node_refs[child_key]
                    node.circle.set_stroke(COMMITTED_COLOR, width=3.5)
                    node.circle.set_fill(COMMITTED_COLOR, opacity=0.2)

                    # Draw edge from current to child in flat space
                    if verified_keys:
                        prev_idx = key_to_flat_idx[verified_keys[-1]]
                        prev_node = self._flat_node_refs[verified_keys[-1]]
                        path_edge = Line(
                            prev_node.get_center(),
                            node.get_center(),
                            color=COMMITTED_COLOR,
                            stroke_width=3,
                        )
                        self.paced(
                            tracker,
                            FadeIn(path_edge),
                            fraction=0.10,
                        )
                    else:
                        # First step: light root too
                        root_node = self._flat_node_refs["root"]
                        root_node.circle.set_stroke(BONUS_COLOR, width=3.5)
                        path_edge = Line(
                            root_node.get_center(),
                            node.get_center(),
                            color=COMMITTED_COLOR,
                            stroke_width=3,
                        )
                        self.paced(
                            tracker,
                            FadeIn(path_edge),
                            fraction=0.10,
                        )

                    # Decision label
                    decision = Text(
                        f"target → '{choice_token}'",
                        font_size=13, color=TARGET_COLOR,
                    ).next_to(node, UP, buff=0.18)
                    self.paced(tracker, FadeIn(decision), fraction=0.10)
                    self.paced(tracker, FadeOut(decision), fraction=0.05)

                    verified_keys.append(child_key)
                else:
                    # Miss: token not in tree
                    miss_label = Text(
                        f"target → '{choice_token}' (not in tree)",
                        font_size=13, color=DANGER.base,
                    )
                    last_node = self._flat_node_refs[verified_keys[-1]]
                    miss_label.next_to(last_node, UP, buff=0.18)
                    self.paced(tracker, FadeIn(miss_label), fraction=0.14)
                    self.wait(min(0.5, tracker.duration * 0.05))
                    self._miss_label = miss_label

            self._verified_keys = verified_keys

    # ── Beat 8: Commit ───────────────────────────────────────────────

    def _beat_8_commit(self):
        beat = BEATS[8]

        with self.narrate(beat.narration) as tracker:
            # Build committed ribbon growing from existing ribbon
            self._ribbon.animate.set_opacity(1.0)
            self.paced(
                tracker,
                self._ribbon.animate.set_opacity(1.0),
                fraction=0.08,
            )

            # Move accepted nodes up to ribbon
            for i, tok in enumerate(COMMITTED_TOKENS):
                # Find the key and flat node
                for key in self._verified_keys:
                    if self._tree.nodes[key].label.text == tok:
                        node = self._flat_node_refs[key]
                        target_pos = self._ribbon_slots[i].get_center()
                        self.paced(
                            tracker,
                            node.animate.move_to(target_pos).set_opacity(1.0),
                            fraction=0.12,
                        )
                        # Turn the ribbon slot green
                        self._ribbon_slots[i].set_state(TokenState.ACCEPTED)
                        self._ribbon_slots[i].label.text = tok
                        break

            # Add bonus token 'runs'
            bonus_box = TokenBox(
                BONUS_TOKEN, state=TokenState.ACTIVE,
                width=0.85, font_size=22,
            )
            bonus_box.scale(0.78)
            bonus_box.next_to(self._ribbon, RIGHT, buff=0.1)

            self.paced(
                tracker,
                FadeIn(bonus_box, shift=UP * 0.1),
                fraction=0.14,
            )

            # Closing label
            closing = Text(
                "Speed from proposals. Correctness from the target.",
                font_size=16, color=COMMITTED_COLOR,
            )
            closing.to_edge(DOWN, buff=0.3)
            self.paced(tracker, FadeIn(closing), fraction=0.16)
            self.wait(min(0.8, tracker.duration * 0.08))
