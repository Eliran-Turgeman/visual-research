"""Minimal narrated example: speculative tokens become accepted tokens."""

from contextlib import contextmanager
import os
from types import SimpleNamespace

from manim import (
    BLUE,
    GREEN,
    AnimationGroup,
    Create,
    FadeIn,
    FadeOut,
    Scene,
    Text,
    Transform,
    UP,
    VGroup,
    Write,
)

from manim_lib import CandidateToken, TokenBox, TokenSequence, TokenState

try:
    from manim_voiceover import VoiceoverScene
except ImportError:
    VoiceoverScene = Scene


class MinimalExplainer(VoiceoverScene):
    """Explain proposal and verification with a three-token toy example."""

    def setup(self):
        super().setup()
        self._voiceover_enabled = False
        default_provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "none"
        provider = os.getenv("MANIM_TTS_PROVIDER", default_provider).lower()
        if provider == "openrouter":
            from manim_lib.openrouter_voiceover import (
                DEFAULT_OPENROUTER_TTS_MODEL,
                DEFAULT_OPENROUTER_TTS_VOICE,
                OpenRouterSpeechService,
            )

            style_degree = os.getenv("OPENROUTER_TTS_STYLE_DEGREE")
            self.set_speech_service(
                OpenRouterSpeechService(
                    model=os.getenv(
                        "OPENROUTER_TTS_MODEL", DEFAULT_OPENROUTER_TTS_MODEL
                    ),
                    voice=os.getenv(
                        "OPENROUTER_TTS_VOICE", DEFAULT_OPENROUTER_TTS_VOICE
                    ),
                    speed=float(os.getenv("OPENROUTER_TTS_SPEED", "0.96")),
                    style=os.getenv("OPENROUTER_TTS_STYLE"),
                    style_degree=(
                        float(style_degree) if style_degree is not None else None
                    ),
                )
            )
            self._voiceover_enabled = True
        elif provider == "gtts":
            from manim_voiceover.services.gtts import GTTSService

            self.set_speech_service(GTTSService())
            self._voiceover_enabled = True
        elif provider == "openai":
            from manim_voiceover.services.openai import OpenAIService

            self.set_speech_service(
                OpenAIService(voice=os.getenv("OPENAI_TTS_VOICE", "alloy"))
            )
            self._voiceover_enabled = True
        elif provider == "azure":
            from manim_voiceover.services.azure import AzureService

            self.set_speech_service(AzureService())
            self._voiceover_enabled = True
        elif provider != "none":
            raise ValueError(
                "MANIM_TTS_PROVIDER must be none, openrouter, gtts, openai, "
                "or azure"
            )

    @contextmanager
    def narrate(self, text: str):
        """Use synchronized voiceover or deterministic silent draft timing."""
        if self._voiceover_enabled:
            with self.voiceover(text=text) as tracker:
                yield tracker
        else:
            duration = max(1.5, len(text.split()) / 2.8)
            yield SimpleNamespace(duration=duration)

    def construct(self):
        title = Text("Speculate, then verify", font_size=40).to_edge(UP)
        context = TokenSequence("The", "model")
        context.next_to(title, direction=(0, -1, 0), buff=0.65)

        with self.narrate(
            "Start with a fixed context. A small draft model proposes several "
            "tokens without waiting for the large model after each one."
        ) as tracker:
            self.play(Write(title), run_time=min(1.0, tracker.duration * 0.25))
            self.play(
                AnimationGroup(
                    *(FadeIn(token, shift=UP * 0.15) for token in context),
                    lag_ratio=0.2,
                ),
                run_time=min(1.4, tracker.duration * 0.35),
            )

        candidates = VGroup(
            CandidateToken("can", 0.72),
            CandidateToken("run", 0.64),
            CandidateToken("fast", 0.51),
        ).arrange(buff=0.3)
        candidates.next_to(context, direction=(0, -1, 0), buff=0.8)
        draft_label = Text("draft proposals", font_size=24, color=BLUE).next_to(
            candidates, direction=(0, -1, 0), buff=0.25
        )

        with self.narrate(
            "Here the draft proposes can, run, and fast. The numbers are toy "
            "draft probabilities, not benchmark measurements."
        ) as tracker:
            self.play(
                AnimationGroup(
                    *(Create(candidate) for candidate in candidates), lag_ratio=0.25
                ),
                FadeIn(draft_label),
                run_time=min(2.2, tracker.duration * 0.65),
            )

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
        verified_label = Text("verified in one target-model pass", font_size=24)
        verified_label.set_color(GREEN).move_to(draft_label)

        with self.narrate(
            "The large model verifies all three positions together. In this "
            "example every proposal is accepted, so the sequence advances by "
            "three tokens after one target-model pass."
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
            self.wait(max(0.4, tracker.duration * 0.25))
