"""Shared narration infrastructure for visual explainer episodes.

Provides :class:`NarratedScene`, a base class that handles TTS provider
selection, the ``narrate()`` context manager, animation pacing, and
review-timeline generation.  Subclasses provide episode-specific content,
layout, and a ``construct()`` that calls ``self._finalize()`` at the end.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

from manim import Scene

from .theme import BACKGROUND

try:
    from manim_voiceover import VoiceoverScene
except ImportError:
    VoiceoverScene = Scene


class NarratedScene(VoiceoverScene):
    """Base for narrated visual explainer episodes.

    Subclasses **must** override the two class attributes below so that
    each episode writes its review timeline and external audio to the
    correct location::

        class MyEpisode(NarratedScene):
            review_timeline_path = Path("media/review/my_episode/timeline.json")
            external_voiceover_subdir = "my_episode_external"
    """

    review_timeline_path: Path = Path("media/review/unnamed/timeline.json")
    external_voiceover_subdir: str = "unnamed_external"

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self) -> None:
        super().setup()
        self.camera.background_color = BACKGROUND
        self._voiceover_enabled = False
        self._external_voiceover = False
        self._external_tracks: list[dict] = []
        self._review_blocks: list[dict] = []

        default_provider = (
            "openrouter" if os.getenv("OPENROUTER_API_KEY") else "none"
        )
        provider = os.getenv("MANIM_TTS_PROVIDER", default_provider).lower()

        if provider == "openrouter":
            from .openrouter_voiceover import (
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

            self.set_speech_service(GTTSService(lang="en", tld="com"))
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
        elif provider == "external-gtts":
            self._external_voiceover = True
            self._external_dir = Path(
                f"media/voiceovers/{self.external_voiceover_subdir}"
            ).resolve()
            self._external_dir.mkdir(parents=True, exist_ok=True)
        elif provider != "none":
            raise ValueError(
                "MANIM_TTS_PROVIDER must be none, openrouter, gtts, "
                "external-gtts, openai, or azure"
            )

    # ------------------------------------------------------------------
    # Narration
    # ------------------------------------------------------------------

    @contextmanager
    def narrate(self, text: str):
        """Provider-agnostic narration with universal review timeline.

        Every exit path (live TTS, pre-rendered external audio, or silent
        word-count estimate) records the block's actual rendered start/end
        in ``_review_blocks``, so ``scripts/extract_narration_frames.py``
        always has usable timestamps regardless of which provider ran.
        """
        index = len(self._review_blocks)
        start = self.time
        try:
            if self._voiceover_enabled:
                with self.voiceover(text=text) as tracker:
                    yield tracker
            elif self._external_voiceover:
                from gtts import gTTS
                from mutagen.mp3 import MP3

                digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
                audio_path = self._external_dir / f"{digest}.mp3"
                if not audio_path.exists():
                    gTTS(text=text, lang="en", tld="com").save(str(audio_path))
                duration = MP3(audio_path).info.length
                track_start = start
                tracker = SimpleNamespace(duration=duration)
                yield tracker
                remaining = duration - (self.time - track_start)
                if remaining > 0:
                    self.wait(remaining)
                self._external_tracks.append(
                    {
                        "start": track_start,
                        "duration": duration,
                        "file": str(audio_path),
                        "text": text,
                    }
                )
            else:
                yield SimpleNamespace(
                    duration=max(1.8, len(text.split()) / 2.65)
                )
        finally:
            end = self.time
            self._review_blocks.append(
                {
                    "index": index,
                    "start": start,
                    "end": end,
                    "duration": end - start,
                    "text": text,
                }
            )

    def paced(
        self,
        tracker,
        *animations,
        fraction: float = 0.58,
        minimum: float = 0.7,
        maximum: float = 4.5,
    ) -> None:
        """Play *animations* at a run-time derived from *tracker*'s duration."""
        run_time = min(maximum, max(minimum, tracker.duration * fraction))
        self.play(*animations, run_time=run_time)

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _finalize(self) -> None:
        """Write external-voiceover manifest and review timeline.

        Call this at the very end of ``construct()`` so it only executes
        when the render completes successfully.
        """
        if self._external_voiceover:
            manifest = {
                "scene_duration": self.time,
                "tracks": self._external_tracks,
            }
            (self._external_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )
        self._write_review_timeline()

    def _write_review_timeline(self) -> None:
        """Write the provider-independent narration review timeline."""
        timeline = {
            "scene_duration": self.time,
            "blocks": self._review_blocks,
        }
        self.review_timeline_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_timeline_path.write_text(
            json.dumps(timeline, indent=2),
            encoding="utf-8",
        )


__all__ = ["NarratedScene"]
