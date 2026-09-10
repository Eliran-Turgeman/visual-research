"""Public example entry points render under their documented names."""

from importlib import import_module
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from manim import tempconfig


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("module_name", "scene_name", "narrated"),
    [
        ("minimal", "MinimalExplainer", True),
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


def _render_environment():
    env = {name: value for name, value in os.environ.items() if not name.startswith("MANIM_")}
    env.update({"PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def test_minimal_managed_draft_produces_bound_timeline_and_real_video(tmp_path):
    env = _render_environment()
    env["OPENROUTER_API_KEY"] = "offline-draft-must-not-use-this"
    result = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "render.py"),
            str(ROOT / "examples" / "minimal" / "scene.py"), "MinimalExplainer",
            "--profile", "draft", "--output-dir", str(tmp_path / "runs"),
            "--run-id", "minimal-managed",
        ],
        cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    run = tmp_path / "runs" / "minimal-managed"
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    timeline = json.loads((run / "timeline.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "rendered"
    assert manifest["settings"]["provider"] == "none"
    assert not manifest["artifacts"]["video"]["has_audio"]
    assert manifest["metrics"]["video_seconds"] > 20
    assert timeline["run_id"] == manifest["run_id"] == "minimal-managed"
    assert [block["beat_id"] for block in timeline["blocks"]] == [
        "context", "draft-proposals", "verification",
    ]
    assert len(timeline["events"]) == 3
    assert (run / manifest["artifacts"]["video"]["path"]).stat().st_size > 0


def test_static_component_draft_has_direct_still_image_path(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "manim", "-ql", "-s",
            "--media_dir", str(tmp_path / "media"),
            "--output_file", str(tmp_path / "components.png"),
            str(ROOT / "examples" / "visual_components" / "scene.py"), "VisualComponents",
        ],
        cwd=ROOT, env=_render_environment(), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    from PIL import Image
    with Image.open(tmp_path / "components.png") as image:
        image.load()
        assert image.size == (854, 480)
    assert not list(tmp_path.rglob("timeline.json"))
