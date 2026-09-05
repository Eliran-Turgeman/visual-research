"""OpenRouter text-to-speech integration for Manim Voiceover."""

import os
from pathlib import Path
from typing import Any

from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService

DEFAULT_OPENROUTER_TTS_MODEL = "microsoft/mai-voice-2"
DEFAULT_OPENROUTER_TTS_VOICE = "en-US-Harper:MAI-Voice-2"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterSpeechService(SpeechService):
    """Generate cached narration through OpenRouter's speech endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_OPENROUTER_TTS_MODEL,
        voice: str = DEFAULT_OPENROUTER_TTS_VOICE,
        speed: float = 0.96,
        style: str | None = None,
        style_degree: float | None = None,
        client: Any | None = None,
        **kwargs: Any,
    ) -> None:
        if not 0.5 <= speed <= 2.0:
            raise ValueError("OpenRouter TTS speed must be between 0.5 and 2.0")
        if style_degree is not None and style is None:
            raise ValueError("style_degree requires a style")

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
            client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=resolved_key)

        self.client = client
        self.model = model
        self.voice = voice
        self.speed = speed
        self.style = style
        self.style_degree = style_degree
        super().__init__(**kwargs)

    def generate_from_text(
        self,
        text: str,
        cache_dir: str | Path | None = None,
        path: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Synthesize one narration segment and return Manim cache metadata."""
        cache_path = Path(cache_dir or self.cache_dir)
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
        cached_result = self.get_cached_result(input_data, cache_path)
        if cached_result is not None:
            return cached_result

        audio_path = path or f"{self.get_audio_basename(input_data)}.mp3"
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

        output_path = cache_path / audio_path
        with self.client.audio.speech.with_streaming_response.create(
            **request
        ) as response:
            response.stream_to_file(output_path)

        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }
