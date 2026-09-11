"""Packaging and offline FFmpeg contracts for a base-only installation."""

from pathlib import Path
import subprocess
import sys
import tomllib

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
import pytest

from manim_lib import production


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def manifest():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_base_dependencies_include_bounded_ffmpeg_without_optional_tools(manifest):
    dependencies = {
        requirement.name: requirement
        for requirement in map(Requirement, manifest["project"]["dependencies"])
    }
    assert set(dependencies) == {"manim", "imageio-ffmpeg"}
    ffmpeg = dependencies["imageio-ffmpeg"]
    assert ffmpeg.marker is None
    assert not ffmpeg.extras
    assert ffmpeg.specifier == SpecifierSet(">=0.6,<0.7")


@pytest.mark.parametrize("version,supported", [
    ("3.10", False), ("3.11", True), ("3.12", True),
    ("3.13", True), ("3.14", False),
])
def test_supported_python_range(manifest, version, supported):
    assert (version in SpecifierSet(manifest["project"]["requires-python"])) is supported


def test_recommended_python_is_supported(manifest):
    recommended = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    assert recommended == "3.12"
    assert recommended in SpecifierSet(manifest["project"]["requires-python"])


def test_only_the_incompatible_openai_sdk_extras_conflict(manifest):
    extras = manifest["project"]["optional-dependencies"]
    assert set(extras) == {
        "dev", "voiceover-azure", "voiceover-gtts",
        "voiceover-openai", "voiceover-openrouter",
    }
    conflicts = {
        frozenset(item["extra"] for item in conflict)
        for conflict in manifest["tool"]["uv"]["conflicts"]
    }
    assert conflicts == {frozenset({"voiceover-openai", "voiceover-openrouter"})}


def test_lock_preserves_python_range_base_dependencies_and_every_extra(manifest):
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    project = manifest["project"]
    assert SpecifierSet(lock["requires-python"]) == SpecifierSet(project["requires-python"])
    locked = next(package for package in lock["package"] if package["name"] == project["name"])
    assert locked["source"] == {"editable": "."}
    assert locked["version"] == project["version"]
    assert {dependency["name"] for dependency in locked["dependencies"]} == {
        Requirement(value).name for value in project["dependencies"]
    }
    assert set(locked["optional-dependencies"]) == set(project["optional-dependencies"])
    for extra, requirements in project["optional-dependencies"].items():
        assert {dependency["name"] for dependency in locked["optional-dependencies"][extra]} == {
            Requirement(value).name for value in requirements
        }


def test_native_ffmpeg_does_not_require_imageio(monkeypatch):
    monkeypatch.setattr(production.shutil, "which", lambda _: "native-ffmpeg")
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    assert production.find_ffmpeg() == "native-ffmpeg"


def test_missing_ffmpeg_package_reports_an_actionable_error(monkeypatch):
    monkeypatch.setattr(production.shutil, "which", lambda _: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    with pytest.raises(production.RenderError, match="Install FFmpeg on PATH or install imageio-ffmpeg"):
        production.find_ffmpeg()


@pytest.mark.parametrize("error", [RuntimeError("no executable"), OSError("cannot execute")])
def test_broken_ffmpeg_fallback_reports_the_cause(monkeypatch, error):
    import imageio_ffmpeg

    def unavailable():
        raise error

    monkeypatch.setattr(production.shutil, "which", lambda _: None)
    monkeypatch.setattr(imageio_ffmpeg, "get_ffmpeg_exe", unavailable)
    with pytest.raises(production.RenderError, match="FFmpeg is required") as raised:
        production.find_ffmpeg()
    assert raised.value.__cause__ is error


def test_installed_ffmpeg_runs_without_path_or_an_override(monkeypatch):
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("IMAGEIO_FFMPEG_EXE", raising=False)
    executable = production.find_ffmpeg()
    result = subprocess.run(
        [executable, "-version"], capture_output=True, text=True, check=True, timeout=30,
    )
    assert "ffmpeg version" in result.stdout.lower()
