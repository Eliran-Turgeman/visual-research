import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import av
import pytest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ddtree"


def test_exact_worked_examples():
    spec = importlib.util.spec_from_file_location("ddtree_checks", EXAMPLE / "checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.check()
    assert result["expectation"] == 2.036
    assert result["accepted_indices"] == [0, 3, 5]
    assert result["bonus"] == "B"


def test_storyboard_is_complete_and_has_no_empty_narration():
    beats = json.loads((EXAMPLE / "storyboard.json").read_text(encoding="utf-8"))
    assert [b["id"] for b in beats] == [f"b{i:02d}" for i in range(1, 25)]
    assert all(b["narration"].strip() and b["purpose"].strip() for b in beats)


@pytest.mark.parametrize(
    "mode,speech,message",
    [
        ("yes", None, "must be 0"),
        ("1", {}, "All speech clips"),
        ("1", {"a": {"request": {"input": "old text"}}}, "stale"),
    ],
)
def test_narration_errors_do_not_fall_back_to_silence(tmp_path, monkeypatch, mode, speech, message):
    spec = importlib.util.spec_from_file_location("ddtree_scene", EXAMPLE / "scene.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setenv("DDTREE_NARRATED", mode)
    (tmp_path / "storyboard.json").write_text(json.dumps([{"id": "a", "narration": "current text"}]))
    if speech is not None:
        (tmp_path / "audio").mkdir()
        (tmp_path / "audio" / "manifest.json").write_text(json.dumps({"beats": speech}))
    with pytest.raises(ValueError, match=message):
        module.DDTreeExplainer().construct()


def test_native_example_renders_without_a_library_or_credentials(tmp_path):
    env = os.environ.copy()
    env.pop("OPENROUTER_API_KEY", None)
    env["DDTREE_NARRATED"] = "0"
    env["DDTREE_RECORD_DIR"] = str(tmp_path / "records")
    result = subprocess.run(
        [sys.executable, "-I", "-m", "manim", "-ql", "--disable_caching",
         "--media_dir", str(tmp_path / "media"), "-n", "0,1",
         str(EXAMPLE / "scene.py"), "DDTreeExplainer"],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    videos = list((tmp_path / "media" / "videos").rglob("DDTreeExplainer.mp4"))
    assert len(videos) == 1
    with av.open(str(videos[0])) as container:
        stream = container.streams.video[0]
        assert (stream.width, stream.height) == (854, 480)
        assert float(stream.average_rate) == 15
        assert not container.streams.audio
        assert len(list(container.decode(video=0))) > 0
