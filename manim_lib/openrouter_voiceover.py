"""OpenRouter text-to-speech integration with recoverable local audio caching."""

from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path
from typing import Any
import warnings

from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import (
    DEFAULT_VOICEOVER_CACHE_JSON_FILENAME,
    SpeechService,
    adjust_speed,
    timestamps_to_word_boundaries,
)

from .audio_cache import AudioCache, InvalidAudioError, staged_file, validate_mp3

DEFAULT_OPENROUTER_TTS_MODEL = "microsoft/mai-voice-2"
DEFAULT_OPENROUTER_TTS_VOICE = "en-US-Harper:MAI-Voice-2"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterSpeechService(SpeechService):
    """Generate narration with validated, atomically published MP3/cache files.

    ``request_timeout`` is the SDK's per-network-operation timeout in seconds,
    not a whole-render deadline. ``max_retries`` counts SDK retries after the
    first attempt; this service never adds an outer retry loop. Defaults are
    60 seconds and two retries, overridable with ``OPENROUTER_TTS_TIMEOUT`` and
    ``OPENROUTER_TTS_MAX_RETRIES``. Authentication, quota and interrupted-stream
    exceptions propagate unchanged. Injected SDK clients are configured with
    ``with_options``; simpler test transports manage their own timeouts.

    Cache locking serializes cooperating OpenRouter processes. Legacy upstream
    providers do not participate in that lock; use separate cache directories
    when rendering with other providers concurrently.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_OPENROUTER_TTS_MODEL,
        voice: str = DEFAULT_OPENROUTER_TTS_VOICE,
        speed: float = 0.96,
        style: str | None = None,
        style_degree: float | None = None,
        request_timeout: float | None = None,
        max_retries: int | None = None,
        cache_lock_timeout: float = 300.0,
        client: Any | None = None,
        **kwargs: Any,
    ) -> None:
        if not 0.5 <= speed <= 2.0:
            raise ValueError("OpenRouter TTS speed must be between 0.5 and 2.0")
        if style_degree is not None and style is None:
            raise ValueError("style_degree requires a style")
        request_timeout = (
            float(os.getenv("OPENROUTER_TTS_TIMEOUT", "60"))
            if request_timeout is None
            else request_timeout
        )
        max_retries = (
            int(os.getenv("OPENROUTER_TTS_MAX_RETRIES", "2"))
            if max_retries is None
            else max_retries
        )
        if not math.isfinite(request_timeout) or request_timeout <= 0:
            raise ValueError("request_timeout must be a finite positive number")
        if (
            not isinstance(max_retries, int)
            or isinstance(max_retries, bool)
            or max_retries < 0
        ):
            raise ValueError("max_retries must be a nonnegative integer")
        if not math.isfinite(cache_lock_timeout) or cache_lock_timeout <= 0:
            raise ValueError("cache_lock_timeout must be a finite positive number")
        global_speed = kwargs.get("global_speed", 1.0)
        if not math.isfinite(global_speed) or global_speed <= 0:
            raise ValueError("global_speed must be a finite positive number")

        resolved_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if client is None:
            if not resolved_key:
                raise ValueError(
                    "OPENROUTER_API_KEY is required for OpenRouter narration"
                )
            try:
                from openai import OpenAI
            except ImportError as error:
                raise ImportError(
                    'Install the OpenRouter voiceover extra with '
                    '`pip install -e ".[voiceover-openrouter]"`'
                ) from error
            client = OpenAI(
                base_url=OPENROUTER_BASE_URL,
                api_key=resolved_key,
                timeout=request_timeout,
                max_retries=max_retries,
            )
        elif callable(getattr(client, "with_options", None)):
            client = client.with_options(
                timeout=request_timeout, max_retries=max_retries
            )

        self.client = client
        self.model = model
        self.voice = voice
        self.speed = speed
        self.style = style
        self.style_degree = style_degree
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.cache_lock_timeout = cache_lock_timeout
        super().__init__(**kwargs)

    def _cache(self, directory: str | Path | None = None) -> AudioCache:
        return AudioCache(
            directory or self.cache_dir,
            DEFAULT_VOICEOVER_CACHE_JSON_FILENAME,
            self.cache_lock_timeout,
        )

    @staticmethod
    def _audio_path(cache: AudioCache, filename: str) -> Path:
        if not isinstance(filename, str) or not filename:
            raise ValueError("audio cache filename must be a nonempty string")
        candidate = (cache.directory / filename).resolve()
        if not candidate.is_relative_to(cache.directory.resolve()):
            raise ValueError("audio path must stay inside the narration cache directory")
        return candidate

    def _cached_result(self, input_data: dict, cache: AudioCache) -> dict | None:
        records = cache.read()
        matches = [
            entry for entry in records
            if isinstance(entry, dict) and entry.get("input_data") == input_data
        ]
        for entry in reversed(matches):
            try:
                audio_path = self._audio_path(cache, entry.get("original_audio"))
                integrity = validate_mp3(audio_path, entry.get("audio_integrity"))
            except (InvalidAudioError, ValueError):
                continue
            result = deepcopy(entry)
            # Legacy wrapped records may contain already-scaled word offsets,
            # with no information about the global speed used to produce them.
            if (
                result.get("final_audio", result["original_audio"])
                != result["original_audio"]
            ):
                result.pop("word_boundaries", None)
            result["final_audio"] = result["original_audio"]
            result["audio_integrity"] = integrity
            if len(matches) != 1 or result != entry:
                cache.upsert(records, result)
            return result
        if matches:
            warnings.warn(
                "Ignoring stale narration cache metadata for this request; "
                "missing or damaged MP3 audio will be regenerated.",
                RuntimeWarning,
                stacklevel=2,
            )
        return None

    def get_cached_result(self, input_data, cache_dir):
        """Return only verified original audio, repairing stale duplicates."""
        with self._cache(cache_dir).locked() as cache:
            return self._cached_result(input_data, cache)

    def generate_from_text(
        self,
        text: str,
        cache_dir: str | Path | None = None,
        path: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return valid cached audio, or stream and atomically commit a new MP3."""
        with self._cache(cache_dir).locked() as cache:
            return self._generate_from_text(text, cache, path, **kwargs)

    def _generate_from_text(
        self, text: str, cache: AudioCache, path: str | None, **kwargs: Any
    ) -> dict[str, Any]:
        input_text = remove_bookmarks(text)
        speed = float(kwargs.get("speed", self.speed))
        if not 0.5 <= speed <= 2.0:
            raise ValueError("OpenRouter TTS speed must be between 0.5 and 2.0")

        input_data = {
            "input_text": input_text,
            "service": "openrouter",
            "config": {
                "model": self.model,
                "voice": self.voice,
                "speed": speed,
                "style": self.style,
                "style_degree": self.style_degree,
            },
        }
        had_metadata = any(
            isinstance(entry, dict) and entry.get("input_data") == input_data
            for entry in cache.read()
        )
        cached_result = self._cached_result(input_data, cache)
        if cached_result is not None:
            cached_result["input_text"] = text
            return cached_result

        audio_path = path or f"{self.get_audio_basename(input_data)}.mp3"
        output_path = self._audio_path(cache, audio_path)
        # A completed deterministic asset can survive a crash between publishing
        # audio and metadata. Never infer ownership of arbitrary custom paths.
        integrity = None
        if not had_metadata and path is None and output_path.exists():
            try:
                integrity = validate_mp3(output_path)
            except InvalidAudioError:
                pass
        if integrity is not None:
            result = {
                "input_text": text,
                "input_data": input_data,
                "original_audio": audio_path,
                "final_audio": audio_path,
                "audio_integrity": integrity,
            }
            cache.upsert(cache.read(), result)
            return result

        request: dict[str, Any] = {
            "model": self.model,
            "voice": self.voice,
            "input": input_text,
            "response_format": "mp3",
            "speed": speed,
        }
        if self.style is not None:
            azure_options: dict[str, Any] = {"style": self.style}
            if self.style_degree is not None:
                azure_options["styledegree"] = self.style_degree
            request["extra_body"] = {
                "provider": {"options": {"azure": azure_options}}
            }

        try:
            with staged_file(output_path) as staging:
                with self.client.audio.speech.with_streaming_response.create(
                    **request
                ) as response:
                    response.stream_to_file(staging)
                integrity = validate_mp3(staging)
        except Exception as error:
            error.add_note(
                f"OpenRouter narration failed for model {self.model!r}, voice "
                f"{self.voice!r}; no incomplete audio was published to {output_path}. "
                "Check provider credentials/quota or connectivity, then retry."
            )
            raise

        result = {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
            "final_audio": audio_path,
            "audio_integrity": integrity,
        }
        cache.upsert(cache.read(), result)
        return result

    def _wrap_generate_from_text(self, text: str, path: str = None, **kwargs) -> dict:
        """Preserve upstream processing without its unsafe JSON append.

        Stored boundaries always refer to original audio. Global-speed scaling
        is applied only to the returned copy, so repeated hits cannot rescale
        cached offsets.
        """
        text = " ".join(text.split())
        with self._cache().locked() as cache:
            data = self._generate_from_text(text, cache, path, **kwargs)
            original_audio = data["original_audio"]
            original_path = self._audio_path(cache, original_audio)
            if "word_boundaries" not in data and self._whisper_model is not None:
                transcription = self._whisper_model.transcribe(
                    str(original_path), **self.transcription_kwargs
                )
                data["word_boundaries"] = timestamps_to_word_boundaries(
                    transcription.segments_to_dicts()
                )
                data["transcribed_text"] = transcription.text

            self.audio_callback(original_audio, data, **kwargs)
            data["audio_integrity"] = validate_mp3(original_path)
            data["final_audio"] = original_audio
            adjusted_path = None
            if self.global_speed != 1:
                adjustment = data.get("_openrouter_adjusted", {})
                if not isinstance(adjustment, dict):
                    adjustment = {}
                signature = {
                    "speed": self.global_speed,
                    "original_sha256": data["audio_integrity"]["sha256"],
                }
                if all(
                    adjustment.get(key) == value for key, value in signature.items()
                ):
                    try:
                        adjusted_path = self._audio_path(cache, adjustment.get("path"))
                        validate_mp3(adjusted_path, adjustment.get("integrity"))
                    except (InvalidAudioError, ValueError):
                        adjusted_path = None
                if adjusted_path is None:
                    suffix = hashlib.sha256(repr(signature).encode()).hexdigest()[:12]
                    adjusted_path = original_path.with_name(
                        f"{original_path.stem}_adjusted_{suffix}.mp3"
                    )
                    with staged_file(adjusted_path) as staging:
                        adjust_speed(str(original_path), str(staging), self.global_speed)
                        integrity = validate_mp3(staging)
                    data["_openrouter_adjusted"] = {
                        **signature,
                        "path": str(adjusted_path.relative_to(cache.directory.resolve())),
                        "integrity": integrity,
                    }
            cache.upsert(cache.read(), data)
            result = deepcopy(data)
            if adjusted_path is not None:
                result["final_audio"] = str(
                    adjusted_path.relative_to(cache.directory.resolve())
                )
                for boundary in result.get("word_boundaries", []):
                    boundary["audio_offset"] = int(
                        boundary["audio_offset"] / self.global_speed
                    )
            return result
