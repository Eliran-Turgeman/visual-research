"""Narration timing and provider wiring using clocks/local audio, never live TTS."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
from manim import tempconfig

from manim_lib.narrated_scene import NarratedScene


@pytest.fixture
def scene(tmp_path, monkeypatch):
    for name in list(os.environ):
        if name.startswith(("MANIM_", "OPENROUTER_", "OPENAI_", "AZURE_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "none")
    with tempconfig({"dry_run": True, "media_dir": str(tmp_path), "quality": "low_quality"}):
        result = NarratedScene()
        result.review_timeline_path = tmp_path / "timeline.json"
        result.setup()
        waits = []
        def wait(duration):
            waits.append(duration)
            result.renderer.time += duration
        monkeypatch.setattr(result, "wait", wait)
        result.test_waits = waits
        yield result


@pytest.mark.parametrize("elapsed", [0, 0.6, 3])
def test_silent_pacing_waits_only_remaining_and_records_actual_time(scene, elapsed):
    with scene.narrate("Short block", beat_id="demo") as tracker:
        assert tracker.duration == 1.8
        scene.renderer.time += elapsed
    assert scene.time == pytest.approx(max(elapsed, 1.8))
    assert scene.test_waits == ([pytest.approx(1.8 - elapsed)] if elapsed < 1.8 else [])
    assert scene._review_blocks == [{
        "index": 0, "start": 0, "end": scene.time, "duration": scene.time,
        "text": "Short block", "beat_id": "demo",
    }]


def test_long_silent_narration_and_exception_record_actual_time(scene):
    with scene.narrate(" ".join(["word"] * 53)) as tracker:
        assert tracker.duration == 20
    assert scene.time == 20
    with pytest.raises(RuntimeError, match="scene failed"):
        with scene.narrate("Failure"):
            scene.renderer.time += 0.5
            raise RuntimeError("scene failed")
    assert scene.time == 20.5
    assert scene._review_blocks[-1]["duration"] == 0.5
    assert scene._narrating is False


def test_visual_events_inherit_beat_and_record_scene_clock(scene):
    scene.record_visual_event("Initial state")
    with scene.narrate("Narration", beat_id="acceptance"):
        scene.renderer.time += 0.5
        scene.record_visual_event("Token accepted")
        scene.record_visual_event("Explicit beat", beat_id="other")
    scene.record_visual_event("Final state")
    assert scene._review_events == [
        {"time": 0, "label": "Initial state"},
        {"time": 0.5, "label": "Token accepted", "beat_id": "acceptance"},
        {"time": 0.5, "label": "Explicit beat", "beat_id": "other"},
        {"time": 1.8, "label": "Final state"},
    ]
    with pytest.raises(ValueError):
        scene.record_visual_event(" ")
    with pytest.raises(RuntimeError):
        scene.record_visual_event("valid", beat_id="")


def test_nested_blocks_are_rejected(scene):
    with pytest.raises(ValueError, match="nest"):
        with scene.narrate("Outer"):
            with scene.narrate("Inner"):
                pass


def test_run_timeline_and_teardown_capture_final_clock(scene, monkeypatch, tmp_path):
    target = tmp_path / "run" / "timeline.json"
    monkeypatch.setenv("MANIM_RUN_ID", "unique-id")
    monkeypatch.setenv("MANIM_TIMELINE_PATH", str(target))
    scene.setup()
    with scene.narrate("Draft", beat_id="intro"):
        scene.record_visual_event("State shown")
    scene._finalize()
    scene.renderer.time += 0.5
    scene.tear_down()
    data = json.loads(target.read_text())
    assert data["schema_version"] == 1
    assert data["run_id"] == "unique-id"
    assert data["scene_duration"] == 2.3
    assert data["blocks"][0]["end"] == 1.8
    assert data["events"][0]["beat_id"] == "intro"


def test_run_identity_requires_both_env_values(scene, monkeypatch):
    monkeypatch.setenv("MANIM_RUN_ID", "id")
    with pytest.raises(ValueError, match="together"):
        scene.setup()


def test_direct_scene_does_not_infer_paid_provider(scene, monkeypatch):
    monkeypatch.delenv("MANIM_TTS_PROVIDER")
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-do-not-use")
    scene.setup()
    assert not scene._voiceover_enabled
    assert not scene._external_voiceover


@pytest.mark.parametrize("provider,module_name,class_name", [
    ("openrouter", "manim_lib.openrouter_voiceover", "OpenRouterSpeechService"),
    ("openai", "manim_voiceover.services.openai", "OpenAIService"),
    ("gtts", "manim_voiceover.services.gtts", "GTTSService"),
    ("azure", "manim_voiceover.services.azure", "AzureService"),
])
def test_provider_options_without_live_services(scene, monkeypatch, tmp_path, provider, module_name, class_name):
    module = ModuleType(module_name)
    options = {}
    def service(**kwargs):
        options.update(kwargs)
        return SimpleNamespace()
    setattr(module, class_name, service)
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setenv("MANIM_TTS_PROVIDER", provider)
    monkeypatch.setenv("MANIM_VOICEOVER_DIR", str(tmp_path / "audio"))
    monkeypatch.setattr(scene, "set_speech_service", lambda service: None)
    if provider != "gtts":
        monkeypatch.setenv(f"{provider.upper()}_TTS_VOICE", "test-voice")
        monkeypatch.setenv(f"{provider.upper()}_TTS_SPEED", "1.1")
    scene.setup()
    assert scene._voiceover_enabled
    assert options["cache_dir"] == tmp_path / "audio"
    assert options["transcription_model"] is None
    if provider != "gtts":
        assert options["voice"] == "test-voice"
    if provider == "azure":
        assert options["prosody"] == {"rate": "1.1"}
    elif provider == "openrouter":
        assert options["speed"] == 1.1


def test_openai_speed_is_forwarded_and_actual_provider_time_recorded(scene, monkeypatch):
    scene._voiceover_enabled = True
    scene._tts_settings = {"provider": "openai", "speed": 1.2}
    seen = {}
    @contextmanager
    def voiceover(**kwargs):
        seen.update(kwargs)
        yield SimpleNamespace(duration=2)
        scene.renderer.time += 1.5
    monkeypatch.setattr(scene, "voiceover", voiceover)
    with scene.narrate("Local fake TTS"):
        scene.renderer.time += 0.5
    assert seen == {"text": "Local fake TTS", "speed": 1.2}
    assert scene._review_blocks[0]["duration"] == 2


def test_external_gtts_adds_audio_and_preserves_actual_pacing(scene, monkeypatch, tmp_path):
    import gtts
    import mutagen.mp3
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "external-gtts")
    monkeypatch.setenv("MANIM_VOICEOVER_DIR", str(tmp_path / "external"))
    scene.setup()
    monkeypatch.setattr(
        gtts, "gTTS", lambda **kwargs: SimpleNamespace(save=lambda path: Path(path).write_bytes(b"local audio fixture"))
    )
    monkeypatch.setattr(mutagen.mp3, "MP3", lambda path: SimpleNamespace(info=SimpleNamespace(length=2.5)))
    sounds = []
    monkeypatch.setattr(scene, "add_sound", sounds.append)
    with scene.narrate("External local fixture"):
        scene.renderer.time += 1
    scene._finalize()
    assert scene.time == 2.5
    assert len(sounds) == 1
    assert Path(sounds[0]).is_file()
    assert scene._external_tracks[0]["duration"] == 2.5
    assert (tmp_path / "external" / "manifest.json").is_file()
