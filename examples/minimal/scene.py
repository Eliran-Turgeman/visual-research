"""Minimal narrated example: speculative tokens become accepted tokens."""

from pathlib import Path

from manim import (
    AnimationGroup,
    Create,
    FadeIn,
    FadeOut,
    Text,
    Transform,
    UP,
    VGroup,
    Write,
)

from manim_lib import (
    CandidateToken,
    NarratedScene,
    TokenBox,
    TokenSequence,
    TokenState,
    # Design system
    PRIMARY,
    SUCCESS,
    TYPOGRAPHY,
    SPACING,
    place_at_safe_edge,
    focus_on,
    restore_focus,
)

class MinimalExplainer(NarratedScene):
    """Explain proposal and verification with a three-token toy example."""

    review_timeline_path = Path("media/review/minimal/timeline.json")
    external_voiceover_subdir = "minimal_external"

    def construct(self):
        # ── Themed heading ────────────────────────────────────────────
        title = Text(
            "Speculate, then verify",
            font_size=TYPOGRAPHY.heading.font_size,
            color=TYPOGRAPHY.heading.color,
        )
        place_at_safe_edge(title, UP, buff=SPACING.sm)

        context = TokenSequence("The", "model")
        context.next_to(title, direction=(0, -1, 0), buff=SPACING.md)

        with self.narrate(
            "Start with a fixed context. A small draft model proposes several "
            "tokens without waiting for the large model after each one.",
            beat_id="context",
        ) as tracker:
            self.play(Write(title), run_time=min(1.0, tracker.duration * 0.25))
            self.play(
                AnimationGroup(
                    *(FadeIn(token, shift=UP * 0.15) for token in context),
                    lag_ratio=0.2,
                ),
                run_time=min(1.4, tracker.duration * 0.35),
            )
            self.record_visual_event("Fixed context is visible")

        # ── Draft proposals with semantic color ───────────────────────
        candidates = VGroup(
            CandidateToken("can", 0.72),
            CandidateToken("run", 0.64),
            CandidateToken("fast", 0.51),
        ).arrange(buff=SPACING.sm)
        candidates.next_to(context, direction=(0, -1, 0), buff=SPACING.lg)

        draft_label = Text(
            "draft proposals",
            font_size=TYPOGRAPHY.caption.font_size,
            color=PRIMARY.base,
        ).next_to(candidates, direction=(0, -1, 0), buff=SPACING.xs)

        with self.narrate(
            "Here the draft proposes can, run, and fast. The numbers are toy "
            "draft probabilities, not benchmark measurements.",
            beat_id="draft-proposals",
        ) as tracker:
            self.play(
                AnimationGroup(
                    *(Create(candidate) for candidate in candidates), lag_ratio=0.25
                ),
                FadeIn(draft_label),
                run_time=min(2.2, tracker.duration * 0.65),
            )
            self.record_visual_event("Three draft proposals and toy probabilities are visible")

        # ── Focus on candidates, dim context ──────────────────────────
        all_context = [title, context, draft_label]
        dim_anims, focus_ctx = focus_on(
            candidates, context=[*all_context, candidates],
        )
        if dim_anims:
            self.play(*dim_anims, run_time=0.4)

        # ── Verification with semantic success color ──────────────────
        accepted = TokenSequence()
        accepted.move_to(candidates)
        accepted_boxes = [
            TokenBox("can", state=TokenState.ACCEPTED),
            TokenBox("run", state=TokenState.ACCEPTED),
            TokenBox("fast", state=TokenState.ACCEPTED),
        ]
        accepted.add(*accepted_boxes)
        for index, box in enumerate(accepted_boxes):
            box.move_to(candidates[index].token_box)

        verified_label = Text(
            "verified in one target-model pass",
            font_size=TYPOGRAPHY.caption.font_size,
            color=SUCCESS.base,
        ).move_to(draft_label)

        with self.narrate(
            "The large model verifies all three positions together. In this "
            "example every proposal is accepted, so the sequence advances by "
            "three tokens after one target-model pass.",
            beat_id="verification",
        ) as tracker:
            self.play(
                AnimationGroup(
                    *(
                        Transform(candidates[index].token_box, accepted_boxes[index])
                        for index in range(3)
                    ),
                    lag_ratio=0.2,
                ),
                Transform(draft_label, verified_label),
                *(
                    FadeOut(candidate.probability_label)
                    for candidate in candidates
                ),
                run_time=min(2.4, tracker.duration * 0.55),
            )
            self.record_visual_event("All three proposals are shown as verified")

            # Restore context visibility
            restore_anims = restore_focus(all_context, focus_ctx)
            if restore_anims:
                self.play(*restore_anims, run_time=0.4)

            self.wait(max(0.4, tracker.duration * 0.25))
