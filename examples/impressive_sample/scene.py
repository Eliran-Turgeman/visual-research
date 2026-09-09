"""A short, polished visual sample of speculative decoding."""

from pathlib import Path

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    AnimationGroup,
    Arrow,
    Create,
    FadeIn,
    FadeOut,
    GrowArrow,
    Indicate,
    LaggedStart,
    RoundedRectangle,
    Succession,
    Text,
    Transform,
    VGroup,
    rate_functions,
)

from manim_lib import (
    ACCENT,
    DANGER,
    NEUTRAL,
    PRIMARY,
    SHADOW,
    SPACING,
    STROKES,
    SUCCESS,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TYPOGRAPHY,
    NarratedScene,
    TokenBox,
    TokenState,
)


class ImpressiveSample(NarratedScene):
    """Show how speculative decoding converts serial waits into one batch."""

    review_timeline_path = Path("media/review/impressive_sample/timeline.json")
    external_voiceover_subdir = "impressive_sample_external"

    def _model(self, name: str, detail: str, color: str) -> VGroup:
        shadow = RoundedRectangle(
            width=2.65,
            height=1.1,
            corner_radius=0.18,
            stroke_width=0,
            fill_color=SHADOW,
            fill_opacity=0.65,
        ).shift(RIGHT * 0.06 + DOWN * 0.07)
        body = RoundedRectangle(
            width=2.65,
            height=1.1,
            corner_radius=0.18,
            stroke_color=color,
            stroke_width=STROKES.normal.width,
            fill_color=SURFACE_ELEVATED,
            fill_opacity=0.98,
        )
        inner = body.copy().scale(0.94).set_fill(opacity=0).set_stroke(
            color, width=STROKES.hairline.width, opacity=0.2
        )
        label = Text(name, font_size=28, color=TEXT_PRIMARY)
        sublabel = Text(detail, font_size=16, color=TEXT_SECONDARY)
        copy = VGroup(label, sublabel).arrange(DOWN, buff=0.06).move_to(body)
        return VGroup(shadow, body, inner, copy)

    def _counter(self, number: str, label: str, color: str) -> VGroup:
        value = Text(number, font_size=38, color=color)
        caption = Text(label, font_size=17, color=TEXT_SECONDARY)
        return VGroup(value, caption).arrange(DOWN, buff=SPACING.xs)

    def construct(self):
        eyebrow = Text(
            "SPECULATIVE DECODING",
            font_size=15,
            color=PRIMARY.light,
            weight="SEMIBOLD",
        )
        title = Text(
            "Turn waiting into a batch",
            font_size=TYPOGRAPHY.heading.font_size,
            color=TEXT_PRIMARY,
        )
        heading = VGroup(eyebrow, title).arrange(DOWN, buff=SPACING.xs)
        heading.move_to((0, 3.05, 0))

        target = self._model("Target model", "accurate · expensive", ACCENT.base)
        target.move_to((0, 0.75, 0))

        prompt = TokenBox("The model", width=1.55)
        prompt.move_to((-4.8, 0.75, 0))
        input_arrow = Arrow(
            prompt.get_right(),
            target.get_left(),
            buff=SPACING.sm,
            color=NEUTRAL.base,
            stroke_width=STROKES.normal.width,
            max_tip_length_to_length_ratio=0.12,
        )

        baseline_label = Text(
            "one token per pass",
            font_size=TYPOGRAPHY.caption.font_size,
            color=TEXT_SECONDARY,
        ).move_to((0, -0.25, 0))
        baseline_counter = self._counter("0", "target calls", ACCENT.light)
        baseline_counter.move_to((4.8, 0.75, 0))

        with self.narrate(
            "A large language model normally generates one token, then waits "
            "for the next expensive pass."
        ) as tracker:
            self.paced(
                tracker,
                FadeIn(eyebrow, shift=UP * 0.1),
                FadeIn(title, shift=UP * 0.1),
                fraction=0.24,
            )
            self.paced(
                tracker,
                FadeIn(prompt, shift=RIGHT * 0.15),
                GrowArrow(input_arrow),
                FadeIn(target, scale=0.94),
                FadeIn(baseline_label),
                FadeIn(baseline_counter),
                fraction=0.43,
            )

        output_tokens = VGroup()
        token_words = ("can", "reason", "fast")
        for index, word in enumerate(token_words, start=1):
            token = TokenBox(word, state=TokenState.ACCEPTED, width=1.1)
            if output_tokens:
                token.next_to(output_tokens[-1], RIGHT, buff=SPACING.xs)
            else:
                token.move_to((2.1, -1.25, 0))
            output_tokens.add(token)

            next_counter = self._counter(
                str(index), "target calls", ACCENT.light
            ).move_to(baseline_counter)
            with self.narrate(
                f"Pass {index} produces {word}."
            ) as tracker:
                self.paced(
                    tracker,
                    Succession(
                        Indicate(
                            target,
                            color=ACCENT.light,
                            scale_factor=1.03,
                        ),
                        FadeIn(token, shift=RIGHT * 0.2),
                    ),
                    Transform(baseline_counter, next_counter),
                    fraction=0.72,
                    maximum=1.25,
                )

        with self.narrate(
            "Speculation changes the rhythm. A small draft model proposes "
            "several likely tokens at once."
        ) as tracker:
            draft = self._model(
                "Draft model", "fast · approximate", PRIMARY.base
            ).move_to((-2.1, 0.65, 0))
            target_compact = target.copy().move_to((2.15, 0.65, 0))
            bridge = Arrow(
                draft.get_right(),
                target_compact.get_left(),
                buff=SPACING.sm,
                color=PRIMARY.light,
                stroke_width=STROKES.normal.width,
                max_tip_length_to_length_ratio=0.16,
            )
            new_label = Text(
                "propose in parallel",
                font_size=TYPOGRAPHY.caption.font_size,
                color=PRIMARY.light,
            ).move_to(baseline_label)
            self.paced(
                tracker,
                FadeOut(input_arrow),
                FadeOut(prompt, shift=LEFT * 0.15),
                FadeOut(output_tokens, shift=DOWN * 0.15),
                Transform(target, target_compact),
                FadeIn(draft, shift=RIGHT * 0.2),
                GrowArrow(bridge),
                Transform(baseline_label, new_label),
                FadeOut(baseline_counter),
                fraction=0.52,
            )

        proposals = VGroup(
            *[
                TokenBox(word, state=TokenState.SPECULATIVE, width=1.22)
                for word in token_words
            ]
        ).arrange(RIGHT, buff=SPACING.sm)
        proposals.move_to((0, -1.25, 0))
        draft_arrows = VGroup(
            *[
                Arrow(
                    draft.get_bottom(),
                    proposal.get_top(),
                    buff=SPACING.sm,
                    color=PRIMARY.dim,
                    stroke_width=STROKES.hairline.width,
                    max_tip_length_to_length_ratio=0.12,
                )
                for proposal in proposals
            ]
        )

        with self.narrate(
            "Can, reason, and fast arrive together. The visual structure now "
            "matches the computation: one parallel proposal."
        ) as tracker:
            self.paced(
                tracker,
                LaggedStart(
                    *[
                        AnimationGroup(
                            GrowArrow(arrow),
                            FadeIn(token, shift=DOWN * 0.15),
                        )
                        for arrow, token in zip(draft_arrows, proposals)
                    ],
                    lag_ratio=0.12,
                ),
                fraction=0.58,
            )

        verify_frame = RoundedRectangle(
            width=proposals.width + 0.45,
            height=proposals.height + 0.32,
            corner_radius=0.18,
            stroke_color=ACCENT.light,
            stroke_width=STROKES.heavy.width,
            fill_color=ACCENT.base,
            fill_opacity=0.06,
        ).move_to(proposals)
        final_counter = self._counter(
            "1", "target call", SUCCESS.light
        ).move_to((4.8, 0.65, 0))
        result_label = Text(
            "verified together",
            font_size=TYPOGRAPHY.caption.font_size,
            color=SUCCESS.light,
        ).move_to(baseline_label)

        accepted_targets = [
            TokenBox(word, state=TokenState.ACCEPTED, width=1.22).move_to(token)
            for word, token in zip(token_words, proposals)
        ]

        with self.narrate(
            "The target verifies the whole batch in one pass. Same target "
            "model. Fewer serial waits."
        ) as tracker:
            self.paced(
                tracker,
                Create(verify_frame),
                Indicate(target, color=ACCENT.light, scale_factor=1.03),
                fraction=0.28,
            )
            self.paced(
                tracker,
                *[
                    Transform(proposal, accepted)
                    for proposal, accepted in zip(proposals, accepted_targets)
                ],
                Transform(baseline_label, result_label),
                FadeIn(final_counter, shift=LEFT * 0.15),
                FadeOut(draft_arrows),
                FadeOut(verify_frame),
                fraction=0.38,
            )

        footer = Text(
            "3 serial waits  →  1 batched verification",
            font_size=24,
            color=TEXT_PRIMARY,
        ).move_to((0, -2.55, 0))
        footer[0:14].set_color(TEXT_MUTED)
        footer[-22:].set_color(SUCCESS.light)

        with self.narrate(
            "The speedup comes from changing the shape of the work."
        ) as tracker:
            self.paced(
                tracker,
                FadeOut(draft),
                FadeOut(bridge),
                target.animate.move_to((0, 0.65, 0)),
                proposals.animate.move_to((0, -1.1, 0)),
                final_counter.animate.move_to((4.7, 0.65, 0)),
                FadeIn(footer, shift=UP * 0.12),
                fraction=0.58,
            )
            self.wait(max(0.6, tracker.duration * 0.18))

        self._finalize()
