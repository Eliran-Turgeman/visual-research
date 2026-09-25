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
    assert result["survival"] == [1.0, .7, .336]
    assert result["length_mass"] == [0.0, .3, .364, .336]
    assert result["transfer_first_matches"] == [1, 0]
    assert result["accepted_indices"] == [0, 3, 5]
    assert result["bonus"] == "B"
    assert result["processed_words"] == ["My", "cat", "stayed"]
    assert result["bonus_word"] == "inside"


def test_meaningful_words_preserve_the_checked_prefixes_and_fit_nodes():
    modules = {}
    for name in ("scene", "checks"):
        spec = importlib.util.spec_from_file_location(f"ddtree_{name}", EXAMPLE / f"{name}.py")
        modules[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modules[name])
    scene = modules["scene"]
    checked = modules["checks"].check()
    assert scene.TARGET_CHOICES == checked["word_choices"]
    for prefix, words in checked["word_prefixes"].items():
        assert scene.phrase(prefix) == words
        assert scene.token_word(prefix) == words.split()[-1]
    assert scene.phrase("b") == "My"
    for tree in (
        scene.tree_at(),
        scene.tree_at(-6, .0, 1.8, ("A", "AA", "B")),
        scene.tree_at(.45, .0, 1.85, ("A", "AA", "AAA")),
    ):
        nodes = list(tree[0].values())
        for token in nodes:
            assert token[0].width >= token[1].width + .27
            assert token[0].height > token[1].height
            assert token.get_left()[0] >= -7.02 and token.get_right()[0] <= 7.02
        for i, left in enumerate(nodes):
            for right in nodes[i+1:]:
                assert (
                    left.get_right()[0] + .1 <= right.get_left()[0]
                    or right.get_right()[0] + .1 <= left.get_left()[0]
                    or left.get_top()[1] + .1 <= right.get_bottom()[1]
                    or right.get_top()[1] + .1 <= left.get_bottom()[1]
                )


def test_storyboard_is_complete_and_has_no_empty_narration():
    beats = json.loads((EXAMPLE / "storyboard.json").read_text(encoding="utf-8"))
    ids = [b["id"] for b in beats]
    assert len(ids) == len(set(ids)) == 41
    assert ids[:8] == [
        "inference", "autoregressive_loop", "speculation", "draft_bottleneck",
        "masked_diffusion", "dflash", "ddtree_context", "problem",
    ]
    assert all(b["narration"].strip() and b["purpose"].strip()
               and b["anchor"].strip() and b["seconds"] > 0 for b in beats)
    assert ids.index("expectation") < ids.index("selection_rule")
    assert ids.index("prepared_choices") < ids.index("walk_question")
    for question, answer in (
        ("choose_question", "choose_answer"), ("contrast_question", "contrast_answer"),
        ("mask_question", "mask_answer"), ("walk_question", "walk_first"),
        ("transfer_question", "transfer_answer"),
    ):
        index = ids.index(question)
        assert beats[index]["think"] >= 4
        assert ids[index + 1] == answer


def test_subtitle_timestamps_and_question_pause(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("ddtree_scene", EXAMPLE / "scene.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.subtitle_time(59.9996) == "00:01:00,000"
    assert module.subtitle_time(3661.25) == "01:01:01,250"
    monkeypatch.setenv("DDTREE_RECORD_DIR", str(tmp_path))
    scene = module.DDTreeExplainer()
    scene.speech = {}
    scene.geometry = []
    scene.timeline = [{
        "id": "question", "start": 0, "think_start": 8, "end": 12,
        "audio_start": None, "audio_end": None, "narration": "Which prefix wins?",
    }]
    scene.write_records()
    assert "00:00:00,000 --> 00:00:08,000" in (tmp_path / "draft-script.srt").read_text()
    assert not (tmp_path / "narration.srt").exists()
    scene.speech = {"question": {}}
    scene.timeline[0].update(audio_start=.15, audio_end=6.2)
    scene.write_records()
    assert "00:00:00,150 --> 00:00:06,200" in (tmp_path / "narration.srt").read_text()


def test_thinking_time_follows_speech_and_heading_stays_put(monkeypatch):
    spec = importlib.util.spec_from_file_location("ddtree_scene", EXAMPLE / "scene.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scene = module.DDTreeExplainer()
    scene.section = "Compare"
    scene.heading = module.txt("Compare")
    scene.anchor = module.txt("Previous step")
    scene.beats = {"q": {
        "section": "Compare", "anchor": "Which wins?", "narration": "Choose a prefix.",
        "seconds": 2, "think": 4,
    }}
    scene.speech = {"q": {"wav": "unused.wav", "duration": 3}}
    scene.timeline, scene.geometry = [], []
    heading = scene.heading
    sounds = []

    def advance(*animations, run_time=0):
        scene.renderer.time += run_time

    monkeypatch.setattr(scene, "play", advance)
    monkeypatch.setattr(scene, "wait", lambda duration: advance(run_time=duration))
    monkeypatch.setattr(scene, "add_sound", lambda path, time_offset: sounds.append(time_offset))
    scene.present("q")
    beat = scene.timeline[0]
    assert scene.heading is heading
    assert sounds == [.15]
    assert beat["think_start"] > beat["audio_end"]
    assert beat["end"] - beat["think_start"] == pytest.approx(4)
    assert beat["think_start"] - beat["start"] == pytest.approx(3.5)


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
