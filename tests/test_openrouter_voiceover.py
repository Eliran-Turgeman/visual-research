from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from manim_lib.openrouter_voiceover import (
    DEFAULT_OPENROUTER_TTS_MODEL,
    DEFAULT_OPENROUTER_TTS_VOICE,
    OpenRouterSpeechService,
)


class FakeStreamingResponse:
    def __init__(self) -> None:
        self.requests = []
        self.speech = SimpleNamespace(
            with_streaming_response=SimpleNamespace(create=self.create)
        )
        self.audio = SimpleNamespace(speech=self.speech)

    def create(self, **request):
        self.requests.append(request)

        class Response:
            @staticmethod
            def stream_to_file(path):
                Path(path).write_bytes(b"fake-mp3")

        return nullcontext(Response())


def test_openrouter_service_generates_cached_audio(tmp_path):
    client = FakeStreamingResponse()
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)

    result = service.generate_from_text("A <bookmark mark='step'/> test.")

    assert result["input_data"]["config"]["model"] == DEFAULT_OPENROUTER_TTS_MODEL
    assert result["input_data"]["config"]["voice"] == DEFAULT_OPENROUTER_TTS_VOICE
    assert (tmp_path / result["original_audio"]).read_bytes() == b"fake-mp3"
    assert client.requests[0]["input"] == "A  test."
    assert client.requests[0]["speed"] == 0.96


def test_openrouter_service_passes_optional_azure_style(tmp_path):
    client = FakeStreamingResponse()
    service = OpenRouterSpeechService(
        client=client,
        cache_dir=tmp_path,
        style="calm",
        style_degree=1.1,
    )

    service.generate_from_text("Explain one state transition.")

    assert client.requests[0]["extra_body"] == {
        "provider": {
            "options": {"azure": {"style": "calm", "styledegree": 1.1}}
        }
    }


def test_openrouter_service_requires_credentials_without_injected_client(
    monkeypatch,
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterSpeechService()


@pytest.mark.parametrize("speed", [0.49, 2.01])
def test_openrouter_service_rejects_unsupported_speed(speed):
    with pytest.raises(ValueError, match="between 0.5 and 2.0"):
        OpenRouterSpeechService(client=FakeStreamingResponse(), speed=speed)
