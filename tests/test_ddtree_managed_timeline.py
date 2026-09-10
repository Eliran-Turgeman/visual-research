"""Execute the legacy scene's real finalizer under managed-render settings."""

import json
from pathlib import Path

from manim import tempconfig
import pytest

from test_ddtree_displayed_state import _load_scene


@pytest.fixture
def timeline_probe(monkeypatch, tmp_path):
    module = _load_scene("ddtree_dflash")
    legacy_path = tmp_path / "legacy.json"
    monkeypatch.setattr(module, "REVIEW_TIMELINE_PATH", legacy_path)
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "none")
    monkeypatch.delenv("MANIM_RUN_ID", raising=False)
    monkeypatch.delenv("MANIM_TIMELINE_PATH", raising=False)
    monkeypatch.delenv("MANIM_VOICEOVER_DIR", raising=False)

    class Probe(module.DDTreeDFlashExplainer):
        def opening(self):
            with self.narrate("The target emits one token."):
                self.wait(0.2)

    # Keep the real construct()/finalizer, without rendering unrelated beats.
    for name in (
        "dflash_mechanism", "marginals_not_conditionals", "why_a_tree",
        "tree_objective", "best_first_example", "tree_verification",
        "lossless_commit", "system_tradeoff",
    ):
        monkeypatch.setattr(Probe, name, lambda self: None)

    with tempconfig({
        "dry_run": True,
        "skip_animations": True,
        "media_dir": str(tmp_path / "media"),
        "verbosity": "ERROR",
        "progress_bar": "none",
    }):
        yield Probe, legacy_path


@pytest.mark.parametrize("managed", [False, True])
def test_real_finalizer_writes_the_requested_fresh_timeline(
    timeline_probe, managed, monkeypatch, tmp_path,
):
    Probe, legacy_path = timeline_probe
    if managed:
        output = tmp_path / "run-specific" / "timeline.json"
        monkeypatch.setenv("MANIM_RUN_ID", "ddtree-managed-run")
        monkeypatch.setenv("MANIM_TIMELINE_PATH", str(output))
        legacy_path.write_text("old fixed-path output", encoding="utf-8")
    else:
        output = legacy_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('{"run_id": "stale"}', encoding="utf-8")

    scene = Probe()
    scene.render()
    timeline = json.loads(output.read_text(encoding="utf-8"))
    assert timeline["schema_version"] == 1
    assert timeline["scene_duration"] == pytest.approx(scene.time)
    assert timeline["events"] == []
    assert timeline["blocks"] == [{
        "index": 0, "start": 0.0, "end": pytest.approx(scene.time),
        "duration": pytest.approx(scene.time),
        "text": "The target emits one token.",
    }]
    assert scene.time > 0
    if managed:
        assert timeline["run_id"] == "ddtree-managed-run"
        assert legacy_path.read_text(encoding="utf-8") == "old fixed-path output"
    else:
        assert timeline.get("run_id") is None
    assert not list(output.parent.glob(f".{output.name}.*.writing"))


def test_managed_timeline_preserves_optional_beat_ids(
    timeline_probe, monkeypatch, tmp_path,
):
    Probe, _ = timeline_probe
    output = tmp_path / "beat-timeline.json"
    monkeypatch.setenv("MANIM_RUN_ID", "beat-run")
    monkeypatch.setenv("MANIM_TIMELINE_PATH", str(output))

    def opening(self):
        with self.narrate("The target emits one token.", beat_id="target-emits"):
            self.wait(0.2)

    monkeypatch.setattr(Probe, "opening", opening)
    Probe().render()
    timeline = json.loads(output.read_text(encoding="utf-8"))
    assert timeline["blocks"][0]["beat_id"] == "target-emits"


def test_failed_scene_does_not_publish_a_managed_timeline(
    timeline_probe, monkeypatch, tmp_path,
):
    Probe, legacy_path = timeline_probe
    output = tmp_path / "failed-run" / "timeline.json"
    monkeypatch.setenv("MANIM_RUN_ID", "failed-run")
    monkeypatch.setenv("MANIM_TIMELINE_PATH", str(output))

    def fail(self):
        with self.narrate("An interrupted step."):
            self.wait(0.2)
            raise RuntimeError("render interrupted")

    monkeypatch.setattr(Probe, "opening", fail)
    with pytest.raises(RuntimeError, match="render interrupted"):
        Probe().render()
    assert not output.exists()
    assert not legacy_path.exists()


def test_failed_publication_preserves_previous_file_and_removes_pending_json(
    timeline_probe, monkeypatch, tmp_path,
):
    Probe, _ = timeline_probe
    output = tmp_path / "existing-timeline.json"
    output.write_text("previous complete output", encoding="utf-8")
    monkeypatch.setenv("MANIM_TIMELINE_PATH", str(output))
    replace = Path.replace

    def fail_publication(source, target):
        if target == output:
            raise OSError("publication failed")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_publication)
    with pytest.raises(OSError, match="publication failed"):
        Probe().render()
    assert output.read_text(encoding="utf-8") == "previous complete output"
    assert not list(output.parent.glob(f".{output.name}.*.writing"))
