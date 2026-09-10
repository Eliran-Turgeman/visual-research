"""Managed legacy-scene cache paths, with no live speech-service calls."""

import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

from manim import tempconfig
from manim_voiceover.services.base import SpeechService
import pytest

from test_ddtree_managed_timeline import timeline_probe


@pytest.mark.parametrize("provider", ["openrouter", "gtts", "openai", "azure"])
@pytest.mark.parametrize("managed", [False, True])
def test_services_use_explicit_path_cache_across_unique_run_media(
    timeline_probe, provider, managed, monkeypatch, tmp_path,
):
    Probe, _ = timeline_probe
    services = []

    class OfflineService(SpeechService):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            services.append(self)

        def generate_from_text(self, *args, **kwargs):
            raise AssertionError("Setup must not synthesize speech")

    names = {
        "openrouter": ("manim_lib.openrouter_voiceover", "OpenRouterSpeechService"),
        "gtts": ("manim_voiceover.services.gtts", "GTTSService"),
        "openai": ("manim_voiceover.services.openai", "OpenAIService"),
        "azure": ("manim_voiceover.services.azure", "AzureService"),
    }
    module_name, service_name = names[provider]
    stub_module = ModuleType(module_name)
    setattr(stub_module, service_name, OfflineService)
    if provider == "openrouter":
        stub_module.DEFAULT_OPENROUTER_TTS_MODEL = "offline-model"
        stub_module.DEFAULT_OPENROUTER_TTS_VOICE = "offline-voice"
    monkeypatch.setitem(sys.modules, module_name, stub_module)
    monkeypatch.setenv("MANIM_TTS_PROVIDER", provider)
    cache = tmp_path / "persistent-cache" / provider
    if managed:
        monkeypatch.setenv("MANIM_VOICEOVER_DIR", str(cache))

    for run in ("first", "second"):
        media = tmp_path / run / "media"
        with tempconfig({"media_dir": str(media)}):
            scene = Probe()
            scene.setup()
            service = services[-1]
            assert isinstance(service.cache_dir, Path)
            assert service.cache_dir == (cache if managed else media / "voiceovers")
            assert service.cache_dir.is_dir()
            assert scene._voiceover_enabled
    if managed:
        assert services[0].cache_dir == services[1].cache_dir


def test_external_gtts_reuses_cache_and_writes_manifest_in_explicit_directory(
    timeline_probe, monkeypatch, tmp_path,
):
    Probe, legacy_timeline = timeline_probe
    cache = tmp_path / "persistent-cache" / "external-gtts"
    monkeypatch.setenv("MANIM_VOICEOVER_DIR", str(cache))
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "external-gtts")
    synthesized = []

    class OfflineGTTS:
        def __init__(self, **kwargs):
            self.text = kwargs["text"]

        def save(self, filename):
            synthesized.append(self.text)
            Path(filename).write_bytes(b"offline test audio")

    gtts_module = ModuleType("gtts")
    gtts_module.gTTS = OfflineGTTS
    mp3_module = ModuleType("mutagen.mp3")

    def read_offline_mp3(filename):
        assert Path(filename).read_bytes() == b"offline test audio"
        return SimpleNamespace(info=SimpleNamespace(length=0.2))

    mp3_module.MP3 = read_offline_mp3
    monkeypatch.setitem(sys.modules, "gtts", gtts_module)
    monkeypatch.setitem(sys.modules, "mutagen.mp3", mp3_module)
    audio_paths = []
    for run in ("first", "second"):
        monkeypatch.setenv("MANIM_RUN_ID", run)
        output = tmp_path / run / "timeline.json"
        monkeypatch.setenv("MANIM_TIMELINE_PATH", str(output))
        with tempconfig({"media_dir": str(tmp_path / run / "media")}):
            scene = Probe()
            scene.setup()
            assert scene._external_dir == cache
            scene.render()
        assert scene._external_dir == cache
        manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["scene_duration"] == pytest.approx(scene.time)
        assert len(manifest["tracks"]) == 1
        track = manifest["tracks"][0]
        audio_path = Path(track["file"])
        assert audio_path.parent == cache
        assert audio_path.is_file()
        assert track["text"] == "The target emits one token."
        assert track["start"] == 0.0
        assert track["duration"] == pytest.approx(0.2)
        assert json.loads(output.read_text(encoding="utf-8"))["run_id"] == run
        audio_paths.append(audio_path)
    assert audio_paths[0] == audio_paths[1]
    assert synthesized == ["The target emits one token."]
    assert not legacy_timeline.exists()


def test_silent_setup_does_not_create_an_unused_cache(
    timeline_probe, monkeypatch, tmp_path,
):
    Probe, _ = timeline_probe
    cache = tmp_path / "unused"
    monkeypatch.setenv("MANIM_VOICEOVER_DIR", str(cache))
    scene = Probe()
    scene.setup()
    assert not scene._voiceover_enabled
    assert not scene._external_voiceover
    assert not cache.exists()
