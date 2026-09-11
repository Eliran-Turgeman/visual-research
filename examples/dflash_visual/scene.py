"""DFlash visual explainer – focused standalone episode.

Explains block-parallel speculative drafting to engineers with rusty math,
using one evolving picture (token ribbon + mechanism) rather than
slide-style panels.

Imports storyboard.py as the single source of truth for narration text,
toy numbers, and beat structure. Uses manim_lib theme, composition, focus,
continuity, and probability primitives.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    AnimationGroup,
    Arrow,
    Create,
    CurvedArrow,
    FadeIn,
    FadeOut,
    GrowFromPoint,
    Indicate,
    LaggedStart,
    Line,
    MathTex,
    MoveToTarget,
    Rectangle,
    RoundedRectangle,
    Scene,
    SurroundingRectangle,
    Text,
    Transform,
    TransformFromCopy,
    VGroup,
    Write,
)

from storyboard import (
    BEATS,
    CANDIDATE_PATH,
    DRAFT_MARGINALS,
    TARGET_CONDITIONALS,
    VERIFICATION,
    greedy_choice,
)
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
    SAFE_MARGINS,
)
from manim_lib.composition import center_group, place_at_safe_edge
from manim_lib.focus import focus_on, restore_focus
from manim_lib.probability import ProbabilityDistribution
from manim_lib.tokens import TokenBox, TokenSequence, TokenState

from manim_lib.narrated_scene import NarratedScene


# --- Derived constants for layout ---
RIBBON_Y = 2.3
DRAFT_STACK_Y = -0.4
DIST_Y = -1.8
SLOT_WIDTH = 1.05
SLOT_HEIGHT = 0.55
SLOT_FONT = 24
MASK_COLOR = PRIMARY.base
COMMITTED_COLOR = SUCCESS.base
REJECTED_COLOR = DANGER.base
TARGET_COLOR = ACCENT.base
DRAFT_COLOR = PRIMARY.base
BONUS_COLOR = ACCENT.light

REVIEW_TIMELINE_PATH = Path("media/review/dflash_visual/timeline.json")

# Positions exposed for layout tests
RIBBON_POSITION = (0.0, RIBBON_Y, 0.0)
CONTEXT_TOKENS = ("We", "see")
SLOT_COUNT = len(DRAFT_MARGINALS)


class DFlashVisualExplainer(NarratedScene):
    """Focused DFlash explainer: parallel drafting, target conditioning,
    marginals, verification, and lossless commit."""

    review_timeline_path = REVIEW_TIMELINE_PATH
    external_voiceover_subdir = "dflash_external"
    verification = VERIFICATION
    target_conditionals = TARGET_CONDITIONALS

    def setup(self):
        super().setup()
        self._beat_index = 0

    # --- Helpers ---

    def _make_token_box(self, text, *, state=TokenState.NEUTRAL,
                        width=SLOT_WIDTH, height=SLOT_HEIGHT):
        return TokenBox(text, state=state, width=width, height=height,
                        font_size=SLOT_FONT)

    def _make_slot(self, label="", *, color=TEXT_MUTED):
        box = RoundedRectangle(
            width=SLOT_WIDTH, height=SLOT_HEIGHT, corner_radius=0.06,
            stroke_color=color, stroke_width=STROKES.normal.width,
            fill_color=color, fill_opacity=0.06,
        )
        if label:
            txt = Text(label, font_size=SLOT_FONT, color=color).move_to(box)
            return VGroup(box, txt)
        return VGroup(box)

    def _make_mask(self):
        box = RoundedRectangle(
            width=SLOT_WIDTH, height=SLOT_HEIGHT, corner_radius=0.06,
            stroke_color=MASK_COLOR, stroke_width=STROKES.normal.width,
            fill_color=MASK_COLOR, fill_opacity=0.18,
        )
        txt = Text("[M]", font_size=SLOT_FONT, color=MASK_COLOR).move_to(box)
        return VGroup(box, txt)

    def _make_committed_token(self, text):
        return self._make_token_box(text, state=TokenState.ACCEPTED)

    def _make_candidate_token(self, text):
        return self._make_token_box(text, state=TokenState.SPECULATIVE)

    def _arrange_ribbon(self, items, y=RIBBON_Y):
        group = VGroup(*items)
        group.arrange(RIGHT, buff=0.1)
        group.move_to((0, y, 0))
        return group

    def _make_distributions(self):
        dists = [
            ProbabilityDistribution(
                {token: (token, probability) for token, probability in q.items()},
                max_bar_width=1.0, bar_height=0.20,
                font_size=16, bar_color=PRIMARY.base,
            )
            for q in DRAFT_MARGINALS
        ]
        group = VGroup(*dists).arrange(RIGHT, buff=1.2, aligned_edge=UP)
        group.move_to((0, DIST_Y, 0))
        return dists, group

    def _make_target_row(self):
        """Align causal next-token choices with their proposal positions."""
        targets = []
        for i, token in enumerate(self.verification.target_choices):
            target = self._make_token_box(token, state=TokenState.ACTIVE)
            if i < len(self._candidates):
                x = self._candidates[i].get_x()
            else:
                x = self._candidates[-1].get_x() + SLOT_WIDTH + 0.1
            target.move_to((x, 0.65, 0))
            targets.append(target)
        return targets

    def _make_bonus(self):
        bonus = self._make_token_box(
            self.verification.bonus_token, state=TokenState.ACTIVE,
        )
        boundary = self.verification.accepted_count
        if boundary < len(self._candidates):
            bonus.move_to(self._candidates[boundary])
        else:
            bonus.next_to(self._candidates[-1], RIGHT, buff=0.1)
        bonus.box.set_stroke(BONUS_COLOR, width=STROKES.heavy.width)
        bonus.label.set_color(BONUS_COLOR)
        return bonus

    # --- Construct ---

    def construct(self):
        # Persistent state across beats
        self.ribbon_items = []  # list of VGroup token boxes on screen
        self.slot_items = []    # empty/mask slots

        self._beat_0_sequential_problem()
        self._beat_1_standard_drafter()
        self._beat_2_dflash_parallel()
        self._beat_3_target_conditioning()
        self._beat_4_draft_output()
        self._beat_5_marginals()
        self._beat_6_candidate_path()
        self._beat_7_target_verification()
        self._beat_8_discard_suffix()
        self._beat_9_commit()
        self._beat_10_greedy_equivalence()
        self._beat_11_bridge()

        self._finalize()

    # ================================================================
    # Beat 0: Why is autoregressive decoding slow?
    # ================================================================
    def _beat_0_sequential_problem(self):
        beat = BEATS[0]

        # Opening question – small, top-left
        question = Text(
            "How does a large model generate text?",
            font_size=TYPOGRAPHY.caption.font_size,
            color=TEXT_SECONDARY,
        )
        place_at_safe_edge(question, UP + LEFT)

        # Committed context ribbon
        context_tokens = []
        for tok in CONTEXT_TOKENS:
            context_tokens.append(self._make_committed_token(tok))
        self.ribbon_items = list(context_tokens)

        # Empty slots
        empty_slots = [self._make_slot() for _ in range(SLOT_COUNT)]
        self.slot_items = list(empty_slots)

        all_ribbon = self._arrange_ribbon(self.ribbon_items + self.slot_items)

        with self.narrate(beat.narration) as tracker:
            self.paced(tracker, FadeIn(question), fraction=0.2)
            # Show committed context first
            self.paced(
                tracker,
                *[FadeIn(t, shift=RIGHT * 0.2) for t in context_tokens],
                fraction=0.35,
            )
            # Then empty slots appear one by one
            self.paced(
                tracker,
                LaggedStart(
                    *[FadeIn(s, shift=RIGHT * 0.15) for s in empty_slots],
                    lag_ratio=0.5,
                ),
                fraction=0.35,
            )

        # Fade out question after a beat
        self.play(FadeOut(question), run_time=0.4)
        self._question_mob = None

    # ================================================================
    # Beat 1: Standard drafter fills slots sequentially
    # ================================================================
    def _beat_1_standard_drafter(self):
        beat = BEATS[1]

        # Small drafter label
        drafter_label = Text(
            "standard drafter", font_size=20, color=TEXT_SECONDARY,
        ).next_to(
            VGroup(*self.slot_items), DOWN, buff=0.4
        )

        # Sequential fill animation
        seq_tokens = CANDIDATE_PATH
        filled = []

        with self.narrate(beat.narration) as tracker:
            self.paced(tracker, FadeIn(drafter_label), fraction=0.2)
            for i, tok in enumerate(seq_tokens):
                new_tok = self._make_candidate_token(tok)
                new_tok.move_to(self.slot_items[i])
                self.paced(
                    tracker,
                    FadeOut(self.slot_items[i]),
                    FadeIn(new_tok, shift=DOWN * 0.15),
                    fraction=0.22,
                )
                filled.append(new_tok)

        # Clean up: reset slots back to empty for the DFlash beat
        self.play(
            FadeOut(drafter_label),
            *[FadeOut(f) for f in filled],
            run_time=0.5,
        )
        # Restore empty slots
        new_slots = [self._make_slot() for _ in range(SLOT_COUNT)]
        for i, s in enumerate(new_slots):
            s.move_to(self.slot_items[i])
        self.slot_items = new_slots
        self.play(*[FadeIn(s) for s in new_slots], run_time=0.4)

    # ================================================================
    # Beat 2: DFlash parallel prediction
    # ================================================================
    def _beat_2_dflash_parallel(self):
        beat = BEATS[2]

        # Transform empty slots into masks
        masks = [self._make_mask() for _ in range(SLOT_COUNT)]
        for i, m in enumerate(masks):
            m.move_to(self.slot_items[i])

        with self.narrate(beat.narration) as tracker:
            # Transform slots → masks
            self.paced(
                tracker,
                *[Transform(self.slot_items[i], masks[i]) for i in range(SLOT_COUNT)],
                fraction=0.35,
            )
            # Simultaneous activation flash
            flash_rects = []
            for m in self.slot_items:
                sr = SurroundingRectangle(
                    m, color=PRIMARY.light, buff=0.05,
                    stroke_width=2.5,
                )
                flash_rects.append(sr)

            self.paced(
                tracker,
                *[Create(r) for r in flash_rects],
                fraction=0.25,
            )
            self.wait(0.3)
            self.paced(
                tracker,
                *[FadeOut(r) for r in flash_rects],
                fraction=0.15,
            )

        self._masks = self.slot_items  # keep reference

    # ================================================================
    # Beat 3: Target hidden features condition the drafter
    # ================================================================
    def _beat_3_target_conditioning(self):
        beat = BEATS[3]

        # Target model box (above ribbon, right side)
        target_box = RoundedRectangle(
            width=2.8, height=0.7, corner_radius=0.08,
            stroke_color=TARGET_COLOR, stroke_width=STROKES.normal.width,
            fill_color=TARGET_COLOR, fill_opacity=0.12,
        )
        target_label = Text("target model", font_size=20, color=TARGET_COLOR)
        target_label.move_to(target_box)
        target_group = VGroup(target_box, target_label)
        target_group.next_to(
            VGroup(*self.ribbon_items), UP, buff=0.55
        ).shift(RIGHT * 2.5)

        # Draft model stack (below masks)
        draft_box = RoundedRectangle(
            width=2.4, height=0.65, corner_radius=0.08,
            stroke_color=DRAFT_COLOR, stroke_width=STROKES.normal.width,
            fill_color=DRAFT_COLOR, fill_opacity=0.12,
        )
        draft_label = Text("draft model", font_size=20, color=DRAFT_COLOR)
        draft_label.move_to(draft_box)
        draft_group = VGroup(draft_box, draft_label)
        draft_group.move_to((0, DRAFT_STACK_Y, 0))

        # Hidden state arrows: target → draft
        feature_arrow = Arrow(
            target_box.get_bottom(), draft_box.get_top(),
            color=TARGET_COLOR, stroke_width=2, buff=0.15,
            max_tip_length_to_length_ratio=0.15,
        )
        feature_label = Text(
            "hidden features (K/V)", font_size=16, color=ACCENT.dim,
        ).next_to(feature_arrow, RIGHT, buff=0.15)

        # Mask → draft arrows
        mask_center = VGroup(*self._masks).get_center()
        mask_arrow = Arrow(
            (mask_center[0], mask_center[1] - SLOT_HEIGHT / 2, 0),
            draft_box.get_top() + LEFT * 0.5,
            color=MASK_COLOR, stroke_width=2, buff=0.15,
            max_tip_length_to_length_ratio=0.15,
        )

        with self.narrate(beat.narration) as tracker:
            self.paced(tracker, FadeIn(target_group), fraction=0.25)
            self.paced(
                tracker,
                GrowFromPoint(feature_arrow, target_box.get_bottom()),
                FadeIn(feature_label),
                fraction=0.3,
            )
            self.paced(
                tracker,
                FadeIn(draft_group),
                GrowFromPoint(mask_arrow, mask_center),
                fraction=0.35,
            )

        self._target_group = target_group
        self._draft_group = draft_group
        self._mechanism_extras = VGroup(
            feature_arrow, feature_label, mask_arrow,
        )

    # ================================================================
    # Beat 4: Draft outputs – probability distributions
    # ================================================================
    def _beat_4_draft_output(self):
        beat = BEATS[4]

        # Build probability distributions from storyboard data
        dists, dist_group = self._make_distributions()

        # Position labels
        pos_labels = []
        for i, d in enumerate(dists):
            lbl = Text(f"q{i+1} (toy)", font_size=16, color=TEXT_MUTED)
            lbl.next_to(d, UP, buff=0.12)
            pos_labels.append(lbl)
        pos_label_group = VGroup(*pos_labels)

        # Stop above the labels, rather than crossing q2.
        draft_to_dist = Line(
            self._draft_group.get_bottom(),
            pos_label_group.get_top() + UP * 0.08,
            color=DRAFT_COLOR, stroke_width=2, buff=0.07,
        )

        with self.narrate(beat.narration) as tracker:
            self.paced(
                tracker,
                GrowFromPoint(draft_to_dist, self._draft_group.get_bottom()),
                fraction=0.2,
            )
            self.paced(
                tracker,
                LaggedStart(
                    *[FadeIn(d, shift=UP * 0.2) for d in dists],
                    lag_ratio=0.3,
                ),
                *[FadeIn(lbl) for lbl in pos_labels],
                fraction=0.55,
            )

        self._dists = dists
        self._dist_group = dist_group
        self._pos_labels = pos_label_group
        self._draft_to_dist = draft_to_dist

    # ================================================================
    # Beat 5: Marginals, not conditionals
    # ================================================================
    def _beat_5_marginals(self):
        beat = BEATS[5]

        # Highlight annotation between dist 1 and dist 2
        annotation = Text(
            "q₂ does not depend on y₁",
            font_size=18, color=ACCENT.base,
        )
        annotation.next_to(self._dists[1], UP, buff=0.35)
        annot_rect = SurroundingRectangle(
            annotation, color=ACCENT.base, buff=0.1,
            stroke_width=1.5, fill_opacity=0.08, fill_color=ACCENT.dim,
        )
        annot_group = VGroup(annot_rect, annotation)

        # Dim mechanism above to focus on distributions
        dim_targets = [self._target_group, self._draft_group, self._mechanism_extras,
                       self._draft_to_dist]
        dim_anims, focus_ctx = focus_on(
            self._dists, context=dim_targets, dim_opacity=0.2,
        )

        with self.narrate(beat.narration) as tracker:
            self.paced(tracker, *dim_anims, fraction=0.2)
            self.paced(tracker, FadeIn(annot_group), fraction=0.35)
            self.wait(0.8)
            self.paced(tracker, FadeOut(annot_group), fraction=0.15)

        # Restore
        restore_anims = restore_focus(dim_targets, focus_ctx)
        self.play(*restore_anims, run_time=0.5)

    # ================================================================
    # Beat 6: Candidate path emerges
    # ================================================================
    def _beat_6_candidate_path(self):
        beat = BEATS[6]

        # Highlight top entries
        highlights = []
        for i, (d, tok) in enumerate(zip(self._dists, CANDIDATE_PATH)):
            entry = d.entries[tok]
            h = entry.highlight(ACCENT.base)
            highlights.append(entry)

        # Create candidate tokens that will fly from distributions to ribbon
        candidates = []
        for i, tok in enumerate(CANDIDATE_PATH):
            c = self._make_candidate_token(tok)
            c.move_to(self._masks[i])
            candidates.append(c)

        self._regime_label = Text(
            "greedy decoding · temperature = 0",
            font_size=22, color=TEXT_SECONDARY,
        ).move_to((0, 3.2, 0))
        self.play(FadeOut(self._target_group), run_time=0.3)

        with self.narrate(beat.narration) as tracker:
            self.paced(tracker, FadeIn(self._regime_label), fraction=0.2)
            # Highlight top entries
            self.paced(
                tracker,
                *[Indicate(h, color=ACCENT.base) for h in highlights],
                fraction=0.3,
            )
            # Transform from dist entries to ribbon positions
            self.paced(
                tracker,
                *[TransformFromCopy(
                    self._dists[i].entries[tok].bar,
                    candidates[i],
                ) for i, tok in enumerate(CANDIDATE_PATH)],
                fraction=0.45,
            )

        # Replace masks with candidates
        self.play(
            *[FadeOut(m) for m in self._masks],
            run_time=0.3,
        )
        self._candidates = candidates

    # ================================================================
    # Beat 7: Target verification
    # ================================================================
    def _beat_7_target_verification(self):
        beat = BEATS[7]

        self.play(
            *[FadeOut(m) for m in [
                self._draft_group, self._mechanism_extras, self._draft_to_dist,
                self._dist_group, self._pos_labels,
            ]],
            run_time=0.5,
        )
        self._target_tokens = self._make_target_row()
        self._target_row_label = Text(
            "target argmax\non draft prefixes",
            font_size=18, color=TARGET_COLOR,
        ).next_to(self._target_tokens[0], LEFT, buff=0.45)

        check_marks = []
        for i, candidate in enumerate(self._candidates):
            if i < self.verification.accepted_count:
                symbol, color = "match", SUCCESS.base
            elif i == self.verification.accepted_count:
                symbol, color = "STOP", DANGER.base
            else:
                symbol, color = "unused", TEXT_MUTED
            mark = Text(symbol, font_size=18, color=color)
            mark.move_to((candidate.get_x(), 1.45, 0))
            check_marks.append(mark)

        with self.narrate(beat.narration) as tracker:
            self.paced(
                tracker,
                *[FadeIn(t) for t in self._target_tokens],
                FadeIn(self._target_row_label),
                fraction=0.35,
            )
            self.paced(
                tracker,
                LaggedStart(
                    *[FadeIn(m, shift=DOWN * 0.1) for m in check_marks],
                    lag_ratio=0.4,
                ),
                fraction=0.5,
            )

        self._check_marks = check_marks

    # ================================================================
    # Beat 8: A later match is not an accepted prefix
    # ================================================================
    def _beat_8_discard_suffix(self):
        beat = BEATS[8]
        boundary = self.verification.accepted_count
        self._rejected_suffix = self._candidates[boundary:]
        wrong_prefix_targets = self._target_tokens[boundary + 1:]
        self._suffix_note = Text(
            "after the wrong prefix → unused",
            font_size=20, color=DANGER.light,
        ).move_to((1.3, -0.3, 0))

        with self.narrate(beat.narration) as tracker:
            if self._rejected_suffix:
                self.paced(
                    tracker,
                    *[t.animate.set_state(TokenState.REJECTED)
                      for t in self._rejected_suffix],
                    fraction=0.3,
                )
                for token in self._rejected_suffix:
                    token.set_state(TokenState.REJECTED)
            if wrong_prefix_targets:
                self.paced(
                    tracker,
                    *[t.animate.set_opacity(0.25) for t in wrong_prefix_targets],
                    FadeIn(self._suffix_note),
                    fraction=0.3,
                )
            if self._rejected_suffix:
                self.paced(
                    tracker,
                    *[FadeOut(t) for t in self._rejected_suffix],
                    fraction=0.2,
                )

    # ================================================================
    # Beat 9: Commit the prefix, then the target choice at the boundary
    # ================================================================
    def _beat_9_commit(self):
        beat = BEATS[9]
        boundary = self.verification.accepted_count
        self._committed_new = self._candidates[:boundary]
        bonus_group = self._make_bonus()
        self._bonus_label = Text(
            "target bonus → progress",
            font_size=16, color=BONUS_COLOR,
        ).next_to(bonus_group, DOWN, buff=0.15)

        with self.narrate(beat.narration) as tracker:
            if self._committed_new:
                self.paced(
                    tracker,
                    *[t.animate.set_state(TokenState.ACCEPTED)
                      for t in self._committed_new],
                    fraction=0.3,
                )
                for token in self._committed_new:
                    token.set_state(TokenState.ACCEPTED)
            self.paced(
                tracker,
                TransformFromCopy(self._target_tokens[boundary], bonus_group),
                FadeIn(self._bonus_label),
                fraction=0.4,
            )

        self.play(
            *[FadeOut(m) for m in self._check_marks],
            *[FadeOut(m) for m in self._target_tokens],
            FadeOut(self._target_row_label),
            FadeOut(self._suffix_note),
            run_time=0.4,
        )
        self._bonus_group = bonus_group
        self.ribbon_items.extend(self._committed_new + [bonus_group])

    # ================================================================
    # Beat 10: Correct target choices, not progress, establish equivalence
    # ================================================================
    def _beat_10_greedy_equivalence(self):
        beat = BEATS[10]
        baseline = []
        prefix = ()
        for committed in self._committed_new + [self._bonus_group]:
            token = greedy_choice(self.target_conditionals[prefix])
            prefix += (token,)
            mob = self._make_committed_token(token)
            mob.move_to((committed.get_x(), 0.65, 0))
            baseline.append(mob)
        self._baseline_tokens = baseline
        label = Text(
            "target-only greedy", font_size=18, color=TEXT_SECONDARY,
        ).next_to(baseline[0], LEFT, buff=0.45)
        invariant = Text(
            "same target + causal prefix + tie-breaking",
            font_size=22, color=SUCCESS.light,
        ).move_to((0, -0.45, 0))
        scope = Text(
            "greedy equivalence ≠ a sampling proof",
            font_size=20, color=TEXT_MUTED,
        ).next_to(invariant, DOWN, buff=0.4)
        self._equivalence_labels = VGroup(label, invariant, scope)

        with self.narrate(beat.narration) as tracker:
            self.paced(tracker, FadeIn(label), fraction=0.12)
            for mob in baseline:
                self.paced(tracker, FadeIn(mob), fraction=0.16)
            self.paced(tracker, FadeIn(invariant), fraction=0.25)
            self.paced(tracker, FadeIn(scope), fraction=0.2)

    # ================================================================
    # Beat 11: Bridge to DDTree
    # ================================================================
    def _beat_11_bridge(self):
        beat = BEATS[11]

        self.play(
            *[FadeOut(m) for m in self._baseline_tokens],
            FadeOut(self._equivalence_labels),
            run_time=0.6,
        )

        # Simple tree silhouette (teaser for DDTree)
        tree_lines = VGroup()
        root_pos = (3.5, 0.0, 0)
        from manim import Circle, GREY
        root_circle = Circle(radius=0.2, color=GREY, fill_opacity=0.1)
        root_circle.move_to(root_pos)
        tree_lines.add(root_circle)

        offsets = [(-0.7, -0.8, 0), (0.0, -0.8, 0), (0.7, -0.8, 0)]
        for off in offsets:
            child_pos = (root_pos[0] + off[0], root_pos[1] + off[1], 0)
            child = Circle(radius=0.15, color=GREY, fill_opacity=0.1)
            child.move_to(child_pos)
            edge = Line(root_circle.get_bottom(), child.get_top(), color=GREY)
            tree_lines.add(edge, child)

        tree_label = Text(
            "DDTree: next episode",
            font_size=16, color=TEXT_MUTED,
        ).next_to(tree_lines, DOWN, buff=0.2)
        self._bridge = VGroup(tree_lines, tree_label)

        with self.narrate(beat.narration) as tracker:
            self.paced(tracker, FadeIn(tree_lines, shift=RIGHT * 0.3), fraction=0.35)
            self.paced(tracker, FadeIn(tree_label), fraction=0.2)
            self.wait(0.5)
            self.paced(
                tracker,
                tree_lines.animate.set_opacity(0.3),
                tree_label.animate.set_opacity(0.3),
                fraction=0.2,
            )

        self.wait(1.0)
