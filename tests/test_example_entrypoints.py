"""Public example entry points render under their documented names."""

from importlib import import_module
from pathlib import Path

import pytest
from manim import tempconfig


@pytest.mark.parametrize(
    ("module_name", "scene_name", "narrated"),
    [
        ("speculative_decoding_flow", "SpeculativeDecodingFlow", True),
        ("speculative_decoding_timeline", "SpeculativeDecodingTimeline", True),
        ("visual_components", "VisualComponents", False),
    ],
)
def test_documented_scene_entrypoint(module_name, scene_name, narrated, monkeypatch, tmp_path):
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "none")
    module = import_module(f"examples.{module_name}.scene")
    scene_type = getattr(module, scene_name)
    with tempconfig({"dry_run": True, "skip_animations": True, "quality": "low_quality"}):
        scene = scene_type()
        if narrated:
            assert scene.review_timeline_path == Path(f"media/review/{module_name}/timeline.json")
            assert scene.external_voiceover_subdir == f"{module_name}_external"
            scene.review_timeline_path = tmp_path / "timeline.json"
        scene.render()
    assert scene.mobjects
    if narrated:
        assert scene.review_timeline_path.exists()
        assert scene._review_blocks
