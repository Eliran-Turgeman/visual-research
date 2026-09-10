"""Shared narration infrastructure for visual explainer episodes.

Provides :class:`NarratedScene`, a base class that handles TTS provider
selection, the ``narrate()`` context manager, animation pacing, and
review-timeline generation.  Subclasses provide episode-specific content,
layout, and ``construct()``. ``_finalize()`` remains supported; successful
``tear_down()`` also writes the final timeline using the actual scene clock.
The wrapper supplies MANIM_RUN_ID / MANIM_TIMELINE_PATH / MANIM_VOICEOVER_DIR
for isolated artifacts. Direct Manim calls retain the class's default paths.
No API key alone enables narration: choose MANIM_TTS_PROVIDER explicitly.

``narrate(text, beat_id="proposal")`` optionally identifies a teaching beat.
Call ``record_visual_event("candidate accepted", beat_id="proposal")`` after
its animation to record when a meaningful visual state actually becomes visible,
or before the animation to mark its onset. Events are explicit semantic markers,
not a fabricated substitute for audiovisual review.
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
from .production import _validate_beat_id, resolve_settings

try:
    from manim_voiceover import VoiceoverScene
except ImportError:
    VoiceoverScene = Scene


class NarratedScene(VoiceoverScene):
    """Base for narrated visual explainer episodes.

    Override these attributes to choose legacy direct-Manim artifact paths.
    Managed renders override them with unique run paths::

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
        self._review_events: list[dict] = []
        self._active_beat_id: str | None = None
        self._narrating = False
        self._run_id = os.getenv("MANIM_RUN_ID")
        timeline_path = os.getenv("MANIM_TIMELINE_PATH")
        if bool(self._run_id) != bool(timeline_path):
            raise ValueError("MANIM_RUN_ID and MANIM_TIMELINE_PATH must be supplied together.")
        if timeline_path:
            self.review_timeline_path = Path(timeline_path)
        self._tts_settings = resolve_settings(profile=os.getenv("MANIM_PROFILE", "draft"))
        provider = self._tts_settings["provider"]
        service_options = {"transcription_model": None}
        audio_dir = os.getenv("MANIM_VOICEOVER_DIR")
        if audio_dir:
            Path(audio_dir).mkdir(parents=True, exist_ok=True)
            service_options["cache_dir"] = Path(audio_dir)
        if provider not in ("none", "external-gtts") and VoiceoverScene is Scene:
            raise RuntimeError(
                f"{provider} was explicitly requested but manim-voiceover is not "
                "installed. Install the corresponding voiceover extra; no silent fallback."
            )

        if provider == "openrouter":
            from .openrouter_voiceover import OpenRouterSpeechService

            self.set_speech_service(
                OpenRouterSpeechService(
                    **{key: self._tts_settings[key] for key in
                       ("model", "voice", "speed", "style", "style_degree")},
                    **service_options,
                )
            )
            self._voiceover_enabled = True
        elif provider == "gtts":
            from manim_voiceover.services.gtts import GTTSService

            self.set_speech_service(GTTSService(lang="en", tld="com", **service_options))
            self._voiceover_enabled = True
        elif provider == "openai":
            from manim_voiceover.services.openai import OpenAIService

            self.set_speech_service(
                OpenAIService(
                    voice=self._tts_settings["voice"],
                    model=self._tts_settings["model"],
                    **service_options,
                )
            )
            self._voiceover_enabled = True
        elif provider == "azure":
            from manim_voiceover.services.azure import AzureService

            self.set_speech_service(
                AzureService(
                    voice=self._tts_settings["voice"],
                    style=self._tts_settings["style"],
                    prosody={"rate": f"{self._tts_settings['speed']:.6g}"},
                    **service_options,
                )
            )
            self._voiceover_enabled = True
        elif provider == "external-gtts":
            self._external_voiceover = True
            self._external_dir = Path(
                audio_dir or f"media/voiceovers/{self.external_voiceover_subdir}"
            ).resolve()
            self._external_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Narration
    # ------------------------------------------------------------------

    @contextmanager
    def narrate(self, text: str, *, beat_id: str | None = None):
        """Provider-agnostic narration with universal review timeline.

        Every exit path (live TTS, pre-rendered external audio, or silent
        word-count estimate) records the block's actual rendered start/end
        in ``_review_blocks``, so ``scripts/extract_narration_frames.py``
        always has usable timestamps regardless of which provider ran.
        Silent blocks wait only their estimated *remaining* time, so an
        animation that already consumed the estimate is never delayed again.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Narration text must be nonempty.")
        _validate_beat_id(beat_id)
        if self._narrating:
            raise ValueError("Narration blocks must not nest or overlap.")
        self._narrating = True
        self._active_beat_id = beat_id
        index = len(self._review_blocks)
        start = self.time
        try:
            if self._voiceover_enabled:
                options = (
                    {"speed": self._tts_settings["speed"]}
                    if self._tts_settings["provider"] == "openai" else {}
                )
                with self.voiceover(text=text, **options) as tracker:
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
                self.add_sound(str(audio_path))
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
                duration = max(1.8, len(text.split()) / 2.65)
                yield SimpleNamespace(duration=duration)
                remaining = duration - (self.time - start)
                if remaining > 0:
                    self.wait(remaining)
        finally:
            end = self.time
            block = {
                "index": index, "start": start, "end": end,
                "duration": end - start, "text": text,
            }
            if beat_id is not None:
                block["beat_id"] = beat_id
            self._review_blocks.append(block)
            self._active_beat_id = None
            self._narrating = False

    def record_visual_event(self, label: str, *, beat_id: str | None = None) -> None:
        """Record a meaningful visual change at the current rendered scene time.

        Inside ``narrate``, omitted beat_id inherits that block's beat. Call this
        at the onset or completion of the relevant animation, not after rendering.
        """
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Visual event label must be nonempty.")
        beat_id = self._active_beat_id if beat_id is None else beat_id
        _validate_beat_id(beat_id)
        event = {"time": self.time, "label": label}
        if beat_id is not None:
            event["beat_id"] = beat_id
        self._review_events.append(event)

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

        This only records scene timing, not successful media encoding. The
        managed wrapper validates the encoded video before finalizing its run.
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

    def tear_down(self) -> None:
        """Preserve legacy explicit finalization and capture any later scene time."""
        super().tear_down()
        self._finalize()

    def _write_review_timeline(self) -> None:
        """Write the provider-independent narration review timeline."""
        timeline = {
            "schema_version": 1,
            "scene_duration": self.time,
            "blocks": self._review_blocks,
            "events": self._review_events,
        }
        if self._run_id:
            timeline["run_id"] = self._run_id
        self.review_timeline_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_timeline_path.write_text(
            json.dumps(timeline, indent=2),
            encoding="utf-8",
        )


__all__ = ["NarratedScene"]
