from contextlib import contextmanager
import io
import json
import multiprocessing
from pathlib import Path
from types import SimpleNamespace

import av
import httpx
import openai
import pytest

from manim_lib.audio_cache import AudioCache, InvalidAudioError, validate_mp3
from manim_lib.openrouter_voiceover import (
    DEFAULT_OPENROUTER_TTS_MODEL,
    DEFAULT_OPENROUTER_TTS_VOICE,
    OpenRouterSpeechService,
)


@pytest.fixture(scope="module")
def mp3_bytes():
    """Encode a real, one-second local fixture; no external tools or TTS."""
    output = io.BytesIO()
    with av.open(output, "w", format="mp3") as container:
        stream = container.add_stream("libmp3lame", rate=24000)
        stream.layout = "mono"
        for _ in range(25):
            frame = av.AudioFrame(format="s16p", layout="mono", samples=960)
            frame.sample_rate = 24000
            frame.planes[0].update(bytes(frame.planes[0].buffer_size))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return output.getvalue()


class FakeStreamingResponse:
    def __init__(self, data=b"", *, failure=None, exit_failure=None) -> None:
        self.data = data
        self.failure = failure
        self.exit_failure = exit_failure
        self.requests = []
        self.paths = []
        self.options = {}
        self.speech = SimpleNamespace(
            with_streaming_response=SimpleNamespace(create=self.create)
        )
        self.audio = SimpleNamespace(speech=self.speech)

    def with_options(self, **options):
        self.options = options
        return self

    @contextmanager
    def create(self, **request):
        self.requests.append(request)
        client = self

        class Response:
            @staticmethod
            def stream_to_file(path):
                client.paths.append(Path(path))
                Path(path).write_bytes(client.data)
                if client.failure is not None:
                    raise client.failure

        yield Response()
        if self.exit_failure is not None:
            raise self.exit_failure


def cache_records(service):
    return json.loads(service._cache().metadata_path.read_text(encoding="utf-8"))


def test_openrouter_service_generates_cached_audio(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)

    result = service.generate_from_text("A <bookmark mark='step'/> test.")

    assert result["input_data"]["config"]["model"] == DEFAULT_OPENROUTER_TTS_MODEL
    assert result["input_data"]["config"]["voice"] == DEFAULT_OPENROUTER_TTS_VOICE
    audio_path = tmp_path / result["original_audio"]
    assert audio_path.read_bytes() == mp3_bytes
    assert client.requests[0]["input"] == "A  test."
    assert client.requests[0]["speed"] == 0.96
    assert client.paths[0] != audio_path
    assert not client.paths[0].exists()
    modified = audio_path.stat().st_mtime_ns
    client.requests.clear()

    assert service.generate_from_text("A <bookmark mark='step'/> test.") == result
    assert service.get_cached_result(result["input_data"], tmp_path) == result
    assert client.requests == []
    assert audio_path.stat().st_mtime_ns == modified
    assert len(cache_records(service)) == 1


def test_openrouter_service_passes_optional_azure_style(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes)
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


def test_real_mp3_decode_and_invalid_media(tmp_path, mp3_bytes):
    path = tmp_path / "audio.mp3"
    path.write_bytes(mp3_bytes)
    integrity = validate_mp3(path)
    assert integrity["size"] == len(mp3_bytes)
    assert len(integrity["sha256"]) == 64
    for invalid in (
        b"", b"fake-mp3", mp3_bytes[:len(mp3_bytes) // 2],
        mp3_bytes[:-1], mp3_bytes[:-40], mp3_bytes[:-96],
    ):
        path.write_bytes(invalid)
        with pytest.raises(InvalidAudioError, match="Invalid narration MP3"):
            validate_mp3(path)
    # Some decoders tolerate missing trailing padding. The recorded fingerprint
    # still detects every post-publication byte change.
    path.write_bytes(mp3_bytes[:-40])
    with pytest.raises(InvalidAudioError, match="fingerprint"):
        validate_mp3(path, integrity)


def test_headerless_mp3_frames_are_still_validated(tmp_path, mp3_bytes):
    with av.open(io.BytesIO(mp3_bytes)) as container:
        audio = b"".join(bytes(packet) for packet in container.demux(audio=0))
    path = tmp_path / "headerless.mp3"
    path.write_bytes(audio)
    assert validate_mp3(path)["size"] == len(audio)
    path.write_bytes(audio[:-1])
    with pytest.raises(InvalidAudioError, match="incomplete MP3 frame"):
        validate_mp3(path)


@pytest.mark.parametrize("damage", ["missing", "empty", "garbage", "truncated", "changed"])
def test_corrupt_cached_audio_regenerates_once(tmp_path, mp3_bytes, damage):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    first = service.generate_from_text("Repair this narration.")
    path = tmp_path / first["original_audio"]
    if damage == "missing":
        path.unlink()
    elif damage == "empty":
        path.write_bytes(b"")
    elif damage == "garbage":
        path.write_bytes(b"not audio")
    elif damage == "truncated":
        path.write_bytes(mp3_bytes[:len(mp3_bytes) // 2])
    else:
        path.write_bytes(mp3_bytes[:-40])
    client.requests.clear()

    with pytest.warns(RuntimeWarning, match="stale"):
        assert service.get_cached_result(first["input_data"], tmp_path) is None
    assert client.requests == []
    with pytest.warns(RuntimeWarning, match="stale"):
        result = service.generate_from_text("Repair this narration.")
    assert len(client.requests) == 1
    assert path.read_bytes() == mp3_bytes
    assert service.generate_from_text("Repair this narration.") == result
    assert len(client.requests) == 1
    assert len(cache_records(service)) == 1


@pytest.mark.parametrize("stale_last", [False, True])
def test_stale_duplicates_never_hide_valid_record(tmp_path, mp3_bytes, stale_last):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    valid = service.generate_from_text("Keep valid audio.")
    stale = {**valid, "original_audio": "missing.mp3"}
    unrelated = {"input_data": {"service": "other"}, "extra": ["preserve", 3]}
    duplicates = [valid, stale] if stale_last else [stale, valid]
    service._cache().metadata_path.write_text(
        json.dumps([unrelated, *duplicates]), encoding="utf-8"
    )
    client.requests.clear()

    assert service.generate_from_text("Keep valid audio.") == valid
    assert client.requests == []
    assert cache_records(service) == [unrelated, valid]


def test_legacy_audio_is_adopted_and_missing_final_audio_is_repaired(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    valid = service.generate_from_text("Original audio survives.")
    legacy = {key: value for key, value in valid.items() if key != "audio_integrity"}
    legacy["final_audio"] = "missing-adjusted.mp3"
    legacy["word_boundaries"] = [{"audio_offset": 10}]
    service._cache().metadata_path.write_text(json.dumps([legacy]), encoding="utf-8")
    client.requests.clear()

    result = service._wrap_generate_from_text("Original audio survives.")
    assert client.requests == []
    assert result["final_audio"] == result["original_audio"]
    assert "word_boundaries" not in result
    assert "audio_integrity" in result
    assert len(cache_records(service)) == 1


def test_incomplete_json_preserves_unrelated_records_and_recovers_audio(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    first = service.generate_from_text("Audio was already published.")
    unrelated = {"input_data": {"service": "other"}, "keep": True}
    damaged = ("[" + json.dumps(unrelated) + ', {"input_data":').encode()
    service._cache().metadata_path.write_bytes(damaged)
    client.requests.clear()

    with pytest.warns(RuntimeWarning, match="damaged metadata preserved"):
        result = service.generate_from_text("Audio was already published.")
    assert result == first
    assert client.requests == []
    assert cache_records(service) == [unrelated, first]
    backup, = tmp_path.glob("*.corrupt-*.json")
    assert backup.read_bytes() == damaged


@pytest.mark.parametrize("raw", [b"not-json", b'{"not":"a list"}', b"\xff"])
def test_unreadable_metadata_is_quarantined_not_silently_lost(tmp_path, mp3_bytes, raw):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    service._cache().metadata_path.write_bytes(raw)
    with pytest.warns(RuntimeWarning, match="damaged metadata preserved"):
        service.generate_from_text("Recover metadata.")
    backup, = tmp_path.glob("*.corrupt-*.json")
    assert backup.read_bytes() == raw
    assert len(cache_records(service)) == 1


@pytest.mark.parametrize("exit_failure", [False, True])
def test_interrupted_stream_never_publishes_audio(tmp_path, mp3_bytes, exit_failure):
    error = RuntimeError("connection interrupted")
    client = FakeStreamingResponse(
        mp3_bytes if exit_failure else mp3_bytes[:100],
        failure=None if exit_failure else error,
        exit_failure=error if exit_failure else None,
    )
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    with pytest.raises(RuntimeError) as captured:
        service.generate_from_text("Interrupted generation.")
    assert captured.value is error
    assert "no incomplete audio was published" in error.__notes__[0]
    assert len(client.requests) == 1
    assert not list(tmp_path.glob("*.mp3"))
    assert not list(tmp_path.glob("*.part*"))
    assert not service._cache().metadata_path.exists()


def test_failed_replacement_keeps_previous_completed_audio(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    first = service.generate_from_text("Existing completed audio.", path="shared.mp3")
    client.data = b"partial"
    client.failure = OSError("stream dropped")
    with pytest.raises(OSError, match="stream dropped"):
        service.generate_from_text("Different audio.", path="shared.mp3")
    assert (tmp_path / "shared.mp3").read_bytes() == mp3_bytes
    assert service.get_cached_result(first["input_data"], tmp_path) == first
    assert cache_records(service) == [first]
    assert not list(tmp_path.glob("*.part*"))


@pytest.mark.parametrize("invalid", [b"", b"fake-mp3"])
def test_invalid_provider_audio_is_not_published(tmp_path, invalid):
    client = FakeStreamingResponse(invalid)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    with pytest.raises(InvalidAudioError):
        service.generate_from_text("Validate provider media.")
    assert len(client.requests) == 1
    assert not list(tmp_path.glob("*.mp3"))
    assert not service._cache().metadata_path.exists()


def test_partial_provider_mp3_is_rejected_even_when_it_decodes(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes[:-40])
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    with pytest.raises(InvalidAudioError, match="truncated"):
        service.generate_from_text("Do not publish a partial final frame.")
    assert not list(tmp_path.glob("*.mp3"))
    assert not service._cache().metadata_path.exists()


def test_audio_survives_failed_metadata_commit_without_paid_regeneration(
    tmp_path, mp3_bytes, monkeypatch
):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    write = AudioCache.write

    def interrupted_write(self, records):
        raise OSError("metadata write interrupted")

    monkeypatch.setattr(AudioCache, "write", interrupted_write)
    with pytest.raises(OSError, match="metadata write interrupted"):
        service.generate_from_text("Committed audio, uncommitted metadata.")
    assert len(list(tmp_path.glob("*.mp3"))) == 1
    monkeypatch.setattr(AudioCache, "write", write)
    result = service.generate_from_text("Committed audio, uncommitted metadata.")
    assert len(client.requests) == 1
    assert cache_records(service) == [result]


def test_failed_json_write_is_atomic(tmp_path):
    cache = AudioCache(tmp_path, "cache.json", 1)
    original = [{"unrelated": "retain"}]
    with cache.locked():
        cache.write(original)
        with pytest.raises(TypeError):
            cache.write([{"not_serializable": object()}])
        assert cache.read() == original
    assert not list(tmp_path.glob("*.part*"))


@pytest.mark.parametrize(
    "override",
    [
        {"model": "other/model"},
        {"voice": "other-voice"},
        {"speed": 1.1},
        {"style": "calm"},
        {"style": "calm", "style_degree": 1.1},
    ],
)
def test_cache_key_preserves_provider_configuration(tmp_path, mp3_bytes, override):
    first_client = FakeStreamingResponse(mp3_bytes)
    first_service = OpenRouterSpeechService(client=first_client, cache_dir=tmp_path)
    first = first_service.generate_from_text("Configuration identity.")
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path, **override)
    result = service.generate_from_text("Configuration identity.")
    assert result["original_audio"] != first["original_audio"]
    assert len(client.requests) == 1
    assert service.generate_from_text("Configuration identity.") == result
    assert len(client.requests) == 1


def test_speed_override_and_network_options_do_not_change_identity(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(
        client=client, cache_dir=tmp_path, request_timeout=10, max_retries=0
    )
    first = service.generate_from_text("Speed override.", speed=1.1)
    assert client.requests[0]["speed"] == 1.1
    second_client = FakeStreamingResponse(mp3_bytes)
    second_service = OpenRouterSpeechService(
        client=second_client, cache_dir=tmp_path, speed=1.1,
        request_timeout=20, max_retries=1,
    )
    assert second_service.generate_from_text("Speed override.") == first
    assert second_client.requests == []
    assert second_client.options == {"timeout": 20, "max_retries": 1}


def test_timeout_and_retry_environment_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_TTS_TIMEOUT", "15")
    monkeypatch.setenv("OPENROUTER_TTS_MAX_RETRIES", "0")
    client = FakeStreamingResponse()
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    assert service.request_timeout == 15
    assert service.max_retries == 0
    assert client.options == {"timeout": 15, "max_retries": 0}


@pytest.mark.parametrize(
    "configuration",
    [
        {"request_timeout": 0}, {"request_timeout": float("inf")},
        {"request_timeout": float("nan")}, {"max_retries": -1},
        {"max_retries": 1.5}, {"max_retries": True},
        {"cache_lock_timeout": 0}, {"cache_lock_timeout": float("inf")},
        {"global_speed": 0}, {"global_speed": float("nan")},
    ],
)
def test_invalid_recovery_configuration_fails_before_requests(configuration):
    with pytest.raises(ValueError):
        OpenRouterSpeechService(client=FakeStreamingResponse(), **configuration)


@pytest.mark.parametrize("status,retries,expected_attempts", [(401, 2, 1), (429, 1, 2), (503, 1, 2)])
def test_sdk_owns_bounded_retries_and_provider_errors_propagate(
    tmp_path, monkeypatch, status, retries, expected_attempts
):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            status,
            json={"error": {"message": "provider refused", "code": "insufficient_quota"}},
        )

    monkeypatch.setattr("openai._base_client.time.sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        sdk = openai.OpenAI(api_key="not-a-real-key", http_client=transport, max_retries=9)
        service = OpenRouterSpeechService(
            client=sdk, cache_dir=tmp_path, request_timeout=7, max_retries=retries
        )
        with pytest.raises(openai.APIStatusError) as captured:
            service.generate_from_text("Never call a real provider.")
        assert captured.value.status_code == status
        assert service.client.max_retries == retries
        assert len(requests) == expected_attempts
        assert requests[0].extensions["timeout"]["read"] == 7
    assert not list(tmp_path.glob("*.mp3"))


def test_sdk_timeout_has_no_outer_retry_loop(tmp_path, monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        raise httpx.ReadTimeout("offline timeout", request=request)

    monkeypatch.setattr("openai._base_client.time.sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        service = OpenRouterSpeechService(
            client=openai.OpenAI(api_key="not-a-real-key", http_client=transport),
            cache_dir=tmp_path, max_retries=1,
        )
        with pytest.raises(openai.APITimeoutError):
            service.generate_from_text("Bound timeout attempts.")
    assert len(requests) == 2
    assert not list(tmp_path.glob("*.mp3"))


def test_real_sdk_stream_and_cache_hit_remain_offline(tmp_path, mp3_bytes):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200, headers={"content-type": "audio/mpeg"}, content=mp3_bytes
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        service = OpenRouterSpeechService(
            client=openai.OpenAI(api_key="not-a-real-key", http_client=transport),
            cache_dir=tmp_path,
        )
        first = service._wrap_generate_from_text("SDK streaming response.")
        assert service._wrap_generate_from_text("SDK streaming response.") == first
        assert len(requests) == 1
        assert (tmp_path / first["original_audio"]).read_bytes() == mp3_bytes


def test_real_sdk_interrupted_stream_is_not_retried_or_published(tmp_path, mp3_bytes):
    requests = []
    error = httpx.ReadError("offline stream interrupted")

    class InterruptedStream(httpx.SyncByteStream):
        def __iter__(self):
            yield mp3_bytes[:100]
            raise error

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200, headers={"content-type": "audio/mpeg"}, stream=InterruptedStream()
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        service = OpenRouterSpeechService(
            client=openai.OpenAI(api_key="not-a-real-key", http_client=transport),
            cache_dir=tmp_path, max_retries=2,
        )
        with pytest.raises(httpx.ReadError) as captured:
            service.generate_from_text("Keep stream failures visible.")
    assert captured.value is error
    assert len(requests) == 1
    assert not list(tmp_path.glob("*.mp3"))
    assert not service._cache().metadata_path.exists()


def test_global_speed_cache_does_not_rescale_boundaries_or_regenerate_tts(
    tmp_path, mp3_bytes, monkeypatch
):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path, global_speed=2)
    adjustments = []
    callbacks = []

    def adjust(source, destination, speed):
        adjustments.append((source, destination, speed))
        Path(destination).write_bytes(mp3_bytes)

    def callback(path, data, **kwargs):
        callbacks.append(path)
        data.setdefault("word_boundaries", [{"audio_offset": 1000}])

    monkeypatch.setattr("manim_lib.openrouter_voiceover.adjust_speed", adjust)
    monkeypatch.setattr(service, "audio_callback", callback)
    first = service._wrap_generate_from_text("Wrapped\n   narration.")
    second = service._wrap_generate_from_text("Wrapped narration.")
    assert first == second
    assert first["final_audio"] != first["original_audio"]
    assert first["word_boundaries"][0]["audio_offset"] == 500
    assert cache_records(service)[0]["word_boundaries"][0]["audio_offset"] == 1000
    assert len(client.requests) == len(adjustments) == 1
    assert len(callbacks) == 2

    (tmp_path / first["final_audio"]).write_bytes(b"corrupt adjusted audio")
    repaired = service._wrap_generate_from_text("Wrapped narration.")
    assert repaired == first
    assert len(client.requests) == 1
    assert len(adjustments) == 2
    service.global_speed = 1.25
    different_speed = service._wrap_generate_from_text("Wrapped narration.")
    assert different_speed["final_audio"] != first["final_audio"]
    assert different_speed["word_boundaries"][0]["audio_offset"] == 800
    assert len(client.requests) == 1
    assert len(cache_records(service)) == 1


def test_wrapped_generation_preserves_transcription(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path)
    transcriptions = []

    def transcribe(path, **kwargs):
        transcriptions.append(path)
        return SimpleNamespace(
            text="Local transcription.",
            segments_to_dicts=lambda: [
                {"words": [{"word": "Local", "start": 0.0, "end": 0.5}]}
            ],
        )

    service._whisper_model = SimpleNamespace(transcribe=transcribe)
    first = service._wrap_generate_from_text("Local transcription.")
    second = service._wrap_generate_from_text("Local transcription.")
    assert first == second
    assert first["transcribed_text"] == "Local transcription."
    assert first["word_boundaries"]
    assert len(transcriptions) == len(client.requests) == 1


def test_custom_cache_directory_and_nested_path(tmp_path, mp3_bytes):
    client = FakeStreamingResponse(mp3_bytes)
    service = OpenRouterSpeechService(client=client, cache_dir=tmp_path / "default")
    directory = tmp_path / "alternate"
    result = service.generate_from_text(
        "Custom location.", cache_dir=directory, path=str(Path("nested") / "audio.mp3")
    )
    assert (directory / result["original_audio"]).read_bytes() == mp3_bytes
    assert service.get_cached_result(result["input_data"], directory) == result
    with pytest.raises(ValueError, match="inside"):
        service.generate_from_text("Escape attempt.", path=str(tmp_path / "outside.mp3"))


def _generate_in_process(directory, audio, text, start, results):
    try:
        client = FakeStreamingResponse(audio)
        service = OpenRouterSpeechService(client=client, cache_dir=directory)
        if not start.wait(20):
            raise TimeoutError("test start event timed out")
        result = service._wrap_generate_from_text(text)
        results.put(("ok", len(client.requests), result["original_audio"]))
    except Exception as error:
        results.put(("error", repr(error), ""))


@pytest.mark.parametrize("same_request", [False, True])
def test_concurrent_processes_preserve_records_and_avoid_duplicate_tts(
    tmp_path, mp3_bytes, same_request
):
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_generate_in_process,
            args=(
                str(tmp_path), mp3_bytes,
                "Shared request." if same_request else f"Request {index}.",
                start, results,
            ),
        )
        for index in range(2)
    ]
    cache = AudioCache(tmp_path, "cache.json", 10)
    unrelated = {"input_data": {"service": "other"}, "preserve": True}
    with cache.locked():
        cache.write([unrelated])
    try:
        for process in processes:
            process.start()
        start.set()
        outcomes = [results.get(timeout=60) for _ in processes]
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0
        assert all(outcome[0] == "ok" for outcome in outcomes), outcomes
        assert sum(outcome[1] for outcome in outcomes) == (1 if same_request else 2)
        with cache.locked():
            records = cache.read()
        assert unrelated in records
        assert len(records) == (2 if same_request else 3)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
        results.close()


def test_cache_lock_timeout_is_bounded_and_actionable(tmp_path):
    cache = AudioCache(tmp_path, "cache.json", 0.05)
    with cache.locked():
        with pytest.raises(TimeoutError, match="cache_lock_timeout"):
            with AudioCache(tmp_path, "cache.json", 0.05).locked():
                pytest.fail("a competing lock was acquired")
