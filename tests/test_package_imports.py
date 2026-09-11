"""Canonical leaf imports stay offline; lazy visual exports retain their API."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def isolated(code, *args, cwd):
    bootstrap = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "def guard(event, args):\n"
        "    if event == 'import' and args[0].split('.')[0] in "
        "('manim', 'manim_voiceover', 'av', 'numpy', 'gtts', 'openai'):\n"
        "        raise AssertionError('Offline entry imported a visual/speech dependency')\n"
        "    if event in ('socket.connect', 'socket.getaddrinfo'):\n"
        "        raise AssertionError('Offline entry attempted network access')\n"
        "sys.addaudithook(guard)\n"
    )
    return subprocess.run(
        [sys.executable, "-I", "-S", "-c", bootstrap + code, *args],
        cwd=cwd, env={**os.environ, "MANIM_TTS_PROVIDER": "none", "PATH": ""},
        capture_output=True, text=True, timeout=60,
    )


def test_canonical_leaf_modules_are_stdlib_only(tmp_path):
    result = isolated(
        "import importlib, manim_lib\n"
        "from manim_lib import doctor, production, teaching, timeline\n"
        "from manim_lib import review, metrics\n"
        "assert doctor.production is production\n"
        "assert teaching.parse_timeline is timeline.parse_timeline\n"
        "assert production.parse_timeline is timeline.parse_timeline\n"
        "assert review.parse_timeline is timeline.parse_timeline\n"
        "assert not any(name.startswith('scripts.') for name in sys.modules)\n"
        "assert 'NarratedScene' in dir(manim_lib)\n"
        "try:\n"
        "    manim_lib.not_a_public_export\n"
        "except AttributeError:\n"
        "    pass\n"
        "else:\n"
        "    raise AssertionError('Unknown export did not raise AttributeError')\n",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("script", [
    "render.py", "doctor.py", "validate_teaching.py", "summarize_production.py",
    "extract_narration_frames.py", "review_production.py",
])
def test_cli_help_without_site_packages_or_network(tmp_path, script):
    result = isolated(
        "import runpy\nsys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n",
        str(ROOT / "scripts" / script), "--help", cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert result.stderr == ""


def test_offline_teaching_cli_validates_real_contract_and_timeline(tmp_path):
    contract = json.loads(
        (ROOT / "examples" / "speculative_decoding_timeline" / "teaching.json").read_text()
    )
    blocks = [
        {"index": i, "start": i * 2, "end": (i + 1) * 2, "text": beat["narration"]["text"]}
        for i, beat in enumerate(contract["beats"])
    ]
    for beat in contract["beats"]:
        beat.pop("events", None)
    contract_path = tmp_path / "contract.json"
    timeline_path = tmp_path / "timeline.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    timeline_path.write_text(json.dumps({"scene_duration": len(blocks) * 2, "blocks": blocks}), encoding="utf-8")
    result = isolated(
        "import runpy\nsys.argv = sys.argv[1:]\nrunpy.run_path(sys.argv[0], run_name='__main__')\n",
        str(ROOT / "scripts" / "validate_teaching.py"), str(contract_path),
        "--timeline", str(timeline_path), "--json", cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"]
    assert result.stderr == ""


def test_every_public_export_is_the_original_leaf_object():
    import manim_lib

    assert set(manim_lib.__all__) == set(manim_lib._EXPORTS)
    namespace = {}
    exec("from manim_lib import *", namespace)
    for name in manim_lib.__all__:
        leaf = importlib.import_module(f"manim_lib.{manim_lib._EXPORTS[name]}")
        assert getattr(manim_lib, name) is getattr(leaf, name) is namespace[name]
    with pytest.raises(AttributeError):
        getattr(manim_lib, "not_a_public_export")


def test_offline_accounting_uses_canonical_review_adapter(tmp_path):
    result = isolated(
        "import json\n"
        "from scripts import summarize_production as cli\n"
        "from manim_lib import review, metrics\n"
        "assert cli.MetricsError is metrics.MetricsError\n"
        "validate = cli._bound_validator({}, {})\n"
        "assert callable(validate)\n"
        "report = metrics.summarize_runs([{'schema_version': 1, 'run_id': 'offline',\n"
        "    'status': 'failed', 'profile': 'draft', 'scene_file': 'fixture.py',\n"
        "    'scene_name': 'Fixture', 'settings': {'provider': 'none'}, 'metrics': {}}])\n"
        "print(json.dumps(report))\n",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["totals"]["attempts"] == 1
    assert result.stderr == ""
