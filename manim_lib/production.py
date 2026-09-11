"""Explicit render profiles and run-bound, reproducible artifact manifests.

``python scripts/render.py SCENE.py SceneName --profile draft`` defaults to
``-ql`` and provider ``none``, even when API keys exist. Production defaults to
``-qh`` and requires ``--provider`` or an explicit ``MANIM_TTS_PROVIDER``.
``--quality=-qm`` overrides ``MANIM_QUALITY``, which overrides the profile.
Provider options override the corresponding ``*_TTS_*`` environment settings.
Only supported configuration fields, never credentials/environment dumps, are
recorded. OpenAI transcription is disabled: block timing needs no Whisper model.
Source fingerprints cover Git-tracked code/configuration/storyboard inputs using
an extension allowlist, not just the selected scene. Declare untracked or
external imports/narration inputs with repeatable ``--source-file PATH``.
``source.files`` paths are relative to ``source.root`` unless absolute.
The inventory is deliberately broader than an import graph; it does not claim
all dynamic inputs were discovered. Fingerprints are checked again after render.
Matching source/configuration does not promise bit-for-bit stochastic TTS output.

Each invocation reserves OUTPUT_DIR/RUN_ID (never reused), sets MANIM_RUN_ID,
MANIM_TIMELINE_PATH and MANIM_VOICEOVER_DIR, then invokes Manim without caching.
That disables only Manim's animation cache, not speech reuse. Speech caches live
at CACHE_ROOT/PROVIDER, independent of run/output directories. ``--cache-dir``
selects CACHE_ROOT, then MANIM_TTS_CACHE_ROOT, then repository media/voiceovers.
Providers never share a cache JSON. MANIM_TTS_CACHE_DIR carries the resolved
provider directory to scenes; MANIM_VOICEOVER_DIR remains immutable run audio.
NarratedScene copies the exact consumed audio bytes into content-addressed run
assets. Timeline block ``audio`` references and manifest ``artifacts.audio``
identify those copies, not mutable shared cache files. The manifest's ``cache``
field records the selected provider/path, not an invented hit/request count.
The final manifest's status is ``rendered`` only after successful encoding,
full media decoding and matching timeline identity/duration. It is not a review
or acceptance record. Failed runs retain status ``failed`` for diagnostics.
``metrics.render_seconds`` measures the whole invocation through validation.
Successful runs also expose measured ``metrics.video_seconds``, equal to
``artifacts.video.duration``; failed runs do not fabricate a video denominator.

Public building blocks: ``resolve_settings``, ``preflight``, ``find_ffmpeg``,
``validate_timeline``, ``validate_media``, ``source_snapshot``,
``provider_cache_dir``, ``render`` and ``main``. No schema
framework is required. ``validate_timeline`` accepts legacy timelines unless a
run ID is explicitly required; managed renders always require it. Managed scenes
share the structural and exact numeric policy in ``manim_lib.timeline`` and
must use NarratedScene (or emit the same run-bound timeline protocol). For old
scenes without a timeline, direct ``python -m manim -ql SCENE.py SceneName``
remains available, outside this manifest workflow.
Still-only public component scenes use direct Manim's ``-s`` path, for example
``python -m manim -ql -s examples/visual_components/scene.py VisualComponents``;
no narration blocks or managed timeline are required for that still-image draft.

FFmpeg is resolved from PATH, then the existing imageio_ffmpeg distribution.
PyAV (a Manim dependency) reads stream metadata; the resolved FFmpeg decodes the
complete result. TeX tools are preflighted for direct Tex/MathTex use; pass
``--require-tex`` for scenes using TeX indirectly through helper libraries.
The standalone installation doctor reuses the prerequisite checks below without
requiring a scene, importing the visual library, or contacting a speech service.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid

from manim_lib.timeline import TimelineError, nonblank_text, parse_timeline


PROVIDERS = ("none", "openrouter", "gtts", "external-gtts", "openai", "azure")
QUALITIES = ("-ql", "-qm", "-qh", "-qp", "-qk")
ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = frozenset({
    ".py", ".md", ".json", ".toml", ".yaml", ".yml", ".txt", ".csv", ".ssml",
    ".ps1", ".sh",
})
DEFAULTS = {
    "none": {},
    "openrouter": {
        "model": "microsoft/mai-voice-2",
        "voice": "en-US-Harper:MAI-Voice-2",
        "speed": 0.96,
        "style": None,
        "style_degree": None,
    },
    "openai": {"model": "tts-1-hd", "voice": "alloy", "speed": 1.0},
    "azure": {"voice": "en-US-AriaNeural", "speed": 1.0, "style": None},
    "gtts": {},
    "external-gtts": {},
}
CREDENTIALS = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "azure": ("AZURE_SUBSCRIPTION_KEY", "AZURE_SERVICE_REGION"),
}
DEPENDENCIES = {
    "none": (),
    "openrouter": ("manim_voiceover", "openai"),
    "openai": ("manim_voiceover", "openai"),
    "azure": ("manim_voiceover", "azure.cognitiveservices.speech"),
    "gtts": ("manim_voiceover", "gtts"),
    "external-gtts": ("gtts", "mutagen"),
}


class RenderError(RuntimeError):
    """Actionable render failure, optionally retaining a subprocess exit code."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code if exit_code > 0 else 1


def resolve_settings(
    *,
    profile: str = "draft",
    provider: str | None = None,
    quality: str | None = None,
    environ: dict | None = None,
    **options,
) -> dict:
    """Resolve an allowlist of settings; key presence never selects a provider."""
    env = os.environ if environ is None else environ
    if profile not in ("draft", "production"):
        raise RenderError("Profile must be draft or production.")
    provider = (provider if provider is not None else env.get("MANIM_TTS_PROVIDER", "none"))
    provider = provider.strip().lower()
    if provider not in PROVIDERS:
        raise RenderError(f"Provider must be one of: {', '.join(PROVIDERS)}.")
    if profile == "production" and provider == "none":
        raise RenderError(
            "Production requires an explicit non-silent --provider (openrouter, "
            "openai, azure, gtts, external-gtts) or MANIM_TTS_PROVIDER. "
            "Use --profile draft for silent output."
        )
    quality = quality or env.get("MANIM_QUALITY") or (
        "-ql" if profile == "draft" else "-qh"
    )
    if quality not in QUALITIES:
        raise RenderError(f"Quality must be one of {', '.join(QUALITIES)}; use --quality=-ql.")
    supported = DEFAULTS[provider]
    for key, value in options.items():
        if key not in supported and value is not None:
            raise RenderError(f"Setting {key!r} is not supported by provider {provider!r}.")
    settings = {"quality": quality, "provider": provider}
    for key, default in supported.items():
        value = options.get(key)
        if value is None:
            value = env.get(f"{provider.upper()}_TTS_{key.upper()}", default)
        if value is not None and key in ("speed", "style_degree"):
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise RenderError(f"{key} must be a finite number.") from exc
            if not math.isfinite(value):
                raise RenderError(f"{key} must be a finite number.")
        elif value is not None:
            pattern = r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}"
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise RenderError(f"{key} must be a nonempty provider identifier, not free text.")
        settings[key] = value
    if "speed" in settings:
        low, high = (0.25, 4.0) if provider == "openai" else (0.5, 2.0)
        if not low <= settings["speed"] <= high:
            raise RenderError(f"{provider} speed must be between {low} and {high}.")
    if settings.get("style_degree") is not None:
        if not settings.get("style"):
            raise RenderError("style_degree requires a style.")
        if not 0.01 <= settings["style_degree"] <= 2:
            raise RenderError("style_degree must be between 0.01 and 2.")
    return settings


def find_ffmpeg() -> str:
    """Prefer native FFmpeg, otherwise use the installed imageio_ffmpeg binary."""
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError, OSError) as exc:
        raise RenderError(
            "FFmpeg is required. Install FFmpeg on PATH or install imageio-ffmpeg "
            "in the Python environment selected by MANIM_PYTHON."
        ) from exc


def _checked(command: list[str], *, label: str, **kwargs) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(command, check=False, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"{label} timed out; check its installation.") from exc
    except OSError as exc:
        raise RenderError(f"Cannot start {label}; check its installation and executable path.") from exc
    if result.returncode:
        raise RenderError(f"{label} exited with code {result.returncode}.", result.returncode)
    return result


def check_python() -> None:
    if not (3, 11) <= sys.version_info[:2] < (3, 14):
        raise RenderError("Use Python >=3.11,<3.14; select it with MANIM_PYTHON.")


def check_scene_file(scene_file: Path) -> None:
    if not scene_file.is_file() or scene_file.suffix != ".py":
        raise RenderError(f"Scene source must be an existing Python file: {scene_file}")


def check_credential(name: str, provider: str, environ: dict) -> None:
    if not environ.get(name, "").strip():
        raise RenderError(
            f"{name} is required for {provider}. Set it before rendering; "
            "credentials are never inferred from another provider."
        )


def required_modules(provider: str) -> tuple[str, ...]:
    return ("manim", "av", *DEPENDENCIES[provider])


def dependency_install_command(module: str, provider: str) -> str:
    extra = "voiceover-gtts" if provider == "external-gtts" else f"voiceover-{provider}"
    return "pip install -e ." if module in ("manim", "av") else f'pip install -e ".[{extra}]"'


def check_module(module: str, provider: str, *, isolated: bool = False) -> None:
    """Import a required module; isolation also detects crashes in native loaders."""
    try:
        if isolated:
            flags = ["-S"] if sys.flags.no_site else []
            result = subprocess.run(
                [sys.executable, *flags, "-c",
                 "import importlib, sys; importlib.import_module(sys.argv[1])", module],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, check=False, timeout=30,
            )
            if result.returncode:
                raise ImportError("Dependency import process failed.")
        else:
            importlib.import_module(module)
    except (ImportError, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        raise RenderError(
            f"Cannot import {module}. In the selected Python environment run "
            f"`{dependency_install_command(module, provider)}` and verify its native dependencies."
        ) from exc


def check_ffmpeg() -> dict:
    ffmpeg = find_ffmpeg()
    result = _checked(
        [ffmpeg, "-version"], label="FFmpeg preflight", capture_output=True, text=True,
        timeout=30,
    )
    lines = result.stdout.splitlines()
    if not lines or not lines[0].startswith("ffmpeg version "):
        raise RenderError("FFmpeg returned no recognizable version; verify its installation.")
    return {"ffmpeg": ffmpeg, "ffmpeg_version": lines[0]}


def scene_requires_tex(scene_file: Path) -> bool:
    """Detect direct TeX calls, ignoring comments/literals and allowing Manim aliases."""
    try:
        tree = ast.parse(scene_file.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise RenderError("Scene source must be readable UTF-8 Python.") from exc
    constructors = {"MathTex", "Tex", "SingleStringMathTex", "BulletedList", "Title"}
    aliases = {
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "manim"
        for alias in node.names
        if alias.name in constructors and alias.asname
    }
    return any(
        isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name) and node.func.id in constructors | aliases
            or isinstance(node.func, ast.Attribute) and node.func.attr in constructors
        )
        for node in ast.walk(tree)
    )


def check_tex_tool(name: str) -> None:
    executable = shutil.which(name)
    if not executable:
        raise RenderError(f"{name} is required by this scene. Install a TeX distribution and add it to PATH.")
    _checked(
        [executable, "--version"], label=f"{name} preflight", capture_output=True,
        text=True, timeout=30,
    )


def preflight(
    scene_file: Path,
    settings: dict,
    *,
    environ: dict | None = None,
    require_tex: bool = False,
) -> dict:
    """Check interpreter, provider credentials/imports and native tools, offline."""
    check_python()
    check_scene_file(scene_file)
    env = os.environ if environ is None else environ
    provider = settings["provider"]
    for name in CREDENTIALS.get(provider, ()):
        check_credential(name, provider, env)
    for module in required_modules(provider):
        check_module(module, provider)
    tools = check_ffmpeg()
    if require_tex or scene_requires_tex(scene_file):
        for name in ("latex", "dvisvgm"):
            check_tex_tool(name)
    return tools


def _positive_number(value, label: str, *, zero: bool = False) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (value < 0 if zero else value <= 0)
    ):
        raise RenderError(f"{label} must be a finite {'nonnegative' if zero else 'positive'} number.")
    return float(value)


def validate_timeline(data: object, *, run_id: str | None = None) -> dict:
    """Shared structural policy; preserve the caller's original dict/extensions."""
    try:
        parse_timeline(data, run_id=run_id)
    except TimelineError as exc:
        raise RenderError(str(exc)) from exc
    return data


def _validate_beat_id(beat_id: str | None) -> None:
    # Narration's Python API uses None to omit the JSON field, not to emit null.
    if beat_id is not None:
        try:
            nonblank_text(beat_id, "beat_id")
        except TimelineError as exc:
            raise RenderError(str(exc)) from exc


def validate_media(
    path: Path, *, ffmpeg: str, expect_audio: bool, scene_duration: float
) -> dict:
    """Reject missing, empty, corrupt, wrong-stream or duration-mismatched media."""
    if not path.is_file() or path.stat().st_size == 0:
        raise RenderError(f"Encoded video is missing or empty: {path}")
    import av

    try:
        with av.open(str(path)) as container:
            videos, audios = list(container.streams.video), list(container.streams.audio)
            if len(videos) != 1 or bool(audios) != expect_audio:
                raise RenderError(
                    "Encoded media must contain one video stream and "
                    + ("audible-provider audio." if expect_audio else "no audio for provider none.")
                )
            video = videos[0]
            frame_rate = float(video.average_rate or 0)
            if video.width <= 0 or video.height <= 0 or frame_rate <= 0:
                raise RenderError("Encoded video has invalid dimensions or frame rate.")
            durations = []
            for stream in (video, *audios):
                if stream.duration is None or stream.time_base is None:
                    raise RenderError("Encoded media is missing a stream duration.")
                durations.append(_positive_number(float(stream.duration * stream.time_base), "Media duration"))
            tolerance = max(0.15, 2 / frame_rate)
            if any(abs(value - scene_duration) > tolerance for value in durations):
                raise RenderError(
                    f"Media duration does not match timeline ({scene_duration:.3f}s): "
                    + ", ".join(f"{value:.3f}s" for value in durations)
                )
        for kind in (("video", "audio") if expect_audio else ("video",)):
            with av.open(str(path)) as container:
                if next(container.decode(**{kind: 0}), None) is None:
                    raise RenderError(f"Encoded {kind} stream contains no decodable frames.")
    except RenderError:
        raise
    except (av.FFmpegError, ValueError, OSError) as exc:
        raise RenderError(f"Encoded media is corrupt or unreadable: {path}") from exc
    _checked(
        [ffmpeg, "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode",
         "-i", str(path), "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"],
        label="Media decode validation",
        capture_output=True,
        text=True,
    )
    return {
        "duration": durations[0],
        "audio_duration": durations[1] if audios else None,
        "has_audio": bool(audios),
        "width": video.width,
        "height": video.height,
        "frame_rate": frame_rate,
    }


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _versions(tools: dict) -> dict:
    packages = {}
    for name in ("visual-research", "manim", "manim-voiceover", "av", "imageio-ffmpeg",
                 "openai", "gTTS", "azure-cognitiveservices-speech", "mutagen", "setuptools"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {
        "python": platform.python_version(),
        "manim": packages.get("manim"),
        "packages": packages,
        "ffmpeg": tools["ffmpeg_version"],
    }


def source_snapshot(scene_file: Path, extra_files: tuple[Path, ...] = ()) -> dict:
    """Fingerprint tracked allowlisted inputs plus explicitly declared dependencies.

    Does not execute source, follow tracked symlinks, read arbitrary environment
    files or infer actual imports. External/untracked inputs must be declared.
    """
    scene_file = Path(scene_file).resolve()
    declared = {scene_file, *(Path(path).resolve() for path in extra_files)}
    for path in declared:
        if path.suffix.lower() not in SOURCE_SUFFIXES or not path.is_file():
            raise RenderError(
                f"Declared source must be an existing code/storyboard/narration file "
                f"with an allowlisted extension: {path}"
            )
    paths = set(declared)
    result = {
        "git_commit": None, "dirty": None, "scene_sha256": _sha256(scene_file),
        "root": str(ROOT), "scope": "tracked-source-allowlist-and-declared",
        "suffixes": sorted(SOURCE_SUFFIXES), "tracked_files_available": False,
    }
    if shutil.which("git"):
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
        tracked = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8",
        )
        if commit.returncode == 0:
            result["git_commit"] = commit.stdout.strip()
        if status.returncode == 0:
            result["dirty"] = bool(status.stdout.strip())
        if tracked.returncode == 0:
            result["tracked_files_available"] = True
            paths.update(
                ROOT / name for name in tracked.stdout.split("\0")
                if name and Path(name).suffix.lower() in SOURCE_SUFFIXES
            )
    result["files"] = []
    for path in sorted(paths, key=str):
        name = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        entry = {"path": name}
        if path.is_symlink():
            entry["state"] = "symlink-not-followed"
        elif not path.is_file():
            entry["state"] = "missing"
        else:
            entry["sha256"] = _sha256(path)
        result["files"].append(entry)
    return result


def _verify_source_snapshot(snapshot: dict) -> None:
    for entry in snapshot.get("files", []):
        path = Path(snapshot["root"]) / entry["path"]
        if entry.get("state") == "symlink-not-followed":
            unchanged = path.is_symlink()
        elif entry.get("state") == "missing":
            unchanged = not path.exists()
        else:
            unchanged = not path.is_symlink() and path.is_file() and _sha256(path) == entry["sha256"]
        if not unchanged:
            raise RenderError(f"Source input changed during rendering; rerun with stable inputs: {path}")


def _write_json(path: Path, data: dict) -> None:
    staging = path.with_suffix(".writing")
    staging.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    staging.replace(path)


def provider_cache_dir(
    provider: str, cache_dir: Path | None = None, *, environ: dict | None = None
) -> Path | None:
    """Resolve a reusable provider-isolated cache; this function does no writes."""
    if provider not in PROVIDERS:
        raise RenderError(f"Unknown cache provider: {provider}")
    if provider == "none":
        return None
    env = os.environ if environ is None else environ
    root = cache_dir or env.get("MANIM_TTS_CACHE_ROOT") or ROOT / "media" / "voiceovers"
    return Path(root).resolve() / provider


def _prepare_cache(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write-probe-{uuid.uuid4().hex}"
        with probe.open("xb"):
            pass
        probe.unlink()
    except OSError as exc:
        raise RenderError(f"Speech cache is not writable: {path}. Choose --cache-dir with write access.") from exc


def _audio_artifacts(timeline: dict, run_dir: Path) -> list[dict]:
    assets = {}
    for block in timeline["blocks"]:
        references = block.get("audio", [])
        if not isinstance(references, list):
            raise RenderError("Timeline block audio references must be a list.")
        for reference in references:
            if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
                raise RenderError("Timeline audio reference requires path and sha256.")
            path = (run_dir / reference["path"]).resolve()
            if not path.is_relative_to(run_dir / "audio") or not path.is_file():
                raise RenderError("Timeline audio must reference an existing immutable run-local asset.")
            digest = _sha256(path)
            if digest != reference.get("sha256"):
                raise RenderError("Run-local audio hash does not match its timeline reference.")
            name = str(path.relative_to(run_dir))
            assets[name] = {"path": name, "sha256": digest}
    return [assets[name] for name in sorted(assets)]


def build_command(scene_file: Path, scene_name: str, settings: dict, run_dir: Path) -> list[str]:
    """Build a single-scene invocation; output/quality flags cannot leak between runs."""
    return [
        sys.executable, "-m", "manim", settings["quality"],
        "--renderer", "cairo", "--format", "mp4", "--write_to_movie",
        "--disable_caching", "--media_dir", str(run_dir / "media"),
        "--output_file", str(run_dir / "video.mp4"),
        str(scene_file), scene_name,
    ]


def render(
    scene_file: Path,
    scene_name: str,
    *,
    profile: str = "draft",
    output_dir: Path = Path("media/runs"),
    run_id: str | None = None,
    require_tex: bool = False,
    source_files: tuple[Path, ...] = (),
    cache_dir: Path | None = None,
    **options,
) -> Path:
    """Render once and return manifest.json; never reuse a directory or old timeline."""
    started = time.perf_counter()
    created_at = datetime.now(timezone.utc).isoformat()
    scene_file = Path(scene_file).resolve()
    if not re.fullmatch(r"[A-Za-z_]\w*", scene_name, flags=re.ASCII):
        raise RenderError("Scene name must be one Python class identifier.")
    settings = resolve_settings(profile=profile, **options)
    tools = preflight(scene_file, settings, require_tex=require_tex)
    speech_cache = provider_cache_dir(settings["provider"], cache_dir)
    if speech_cache is not None:
        _prepare_cache(speech_cache)
    source = source_snapshot(scene_file, source_files)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id):
        raise RenderError("run_id must be 1-80 letters, digits, dots, underscores or hyphens, starting with a letter/digit.")
    run_dir = Path(output_dir).resolve() / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise RenderError(f"Run directory already exists; choose a new run_id: {run_dir}") from exc
    timeline_path = run_dir / "timeline.json"
    manifest_path = run_dir / "manifest.json"
    manifest = {
        "schema_version": 1, "run_id": run_id, "profile": profile, "status": "rendering",
        "created_at": created_at, "scene_file": str(scene_file), "scene_name": scene_name,
        "source": source, "settings": settings, "environment": _versions(tools),
        "metrics": {}, "artifacts": {},
    }
    if speech_cache is not None:
        manifest["cache"] = {"provider": settings["provider"], "path": str(speech_cache)}
    _write_json(manifest_path, manifest)
    env = os.environ.copy()
    env.pop("MANIM_TTS_CACHE_DIR", None)
    if speech_cache is not None:
        env["MANIM_TTS_CACHE_DIR"] = str(speech_cache)
    for provider, defaults in DEFAULTS.items():
        for key in defaults:
            env.pop(f"{provider.upper()}_TTS_{key.upper()}", None)
    for key in DEFAULTS[settings["provider"]]:
        if settings[key] is not None:
            env[f"{settings['provider'].upper()}_TTS_{key.upper()}"] = str(settings[key])
    work_dir = run_dir / "work"
    work_dir.mkdir()
    env.update({
        "MANIM_PROFILE": profile, "MANIM_TTS_PROVIDER": settings["provider"],
        "MANIM_QUALITY": settings["quality"], "MANIM_RUN_ID": run_id,
        "MANIM_TIMELINE_PATH": str(timeline_path),
        "MANIM_VOICEOVER_DIR": str(run_dir / "audio"),
        "MANIM_FFMPEG_EXE": tools["ffmpeg"], "IMAGEIO_FFMPEG_EXE": tools["ffmpeg"],
        "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMP": str(work_dir), "TEMP": str(work_dir), "TMPDIR": str(work_dir),
    })
    try:
        _checked(
            build_command(scene_file, scene_name, settings, run_dir),
            label="Manim render", cwd=ROOT, env=env,
        )
        if not timeline_path.is_file():
            raise RenderError(
                "This render did not write its run-specific timeline. Use NarratedScene "
                "or emit MANIM_TIMELINE_PATH with MANIM_RUN_ID. Legacy scenes can use "
                "direct `python -m manim` without managed manifests."
            )
        try:
            timeline = validate_timeline(json.loads(timeline_path.read_text(encoding="utf-8")), run_id=run_id)
        except (ValueError, OSError) as exc:
            raise RenderError("Run-specific timeline is unreadable or invalid JSON.") from exc
        media = validate_media(
            run_dir / "video.mp4", ffmpeg=tools["ffmpeg"],
            expect_audio=settings["provider"] != "none", scene_duration=timeline["scene_duration"],
        )
        _verify_source_snapshot(source)
        audio = _audio_artifacts(timeline, run_dir)
        manifest["artifacts"] = {
            name: {"path": path.name, "sha256": _sha256(path)}
            for name, path in (("video", run_dir / "video.mp4"), ("timeline", timeline_path))
        }
        manifest["artifacts"]["video"].update(media)
        if audio:
            manifest["artifacts"]["audio"] = audio
        manifest["metrics"]["video_seconds"] = media["duration"]
        manifest["status"] = "rendered"
    except Exception as exc:
        manifest["status"] = "failed"
        # Provider exceptions/tracebacks may contain credentials; never persist them.
        manifest["error"] = str(exc) if isinstance(exc, RenderError) else type(exc).__name__
        raise
    finally:
        manifest["metrics"]["render_seconds"] = time.perf_counter() - started
        _write_json(manifest_path, manifest)
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    """CLI shared by both platform wrappers; MANIM_PYTHON selects their interpreter."""
    parser = argparse.ArgumentParser(
        prog="render.py",
        description="Render a draft or explicitly narrated production run; encoded is not accepted.",
        epilog="Use --quality=-ql for a dash-prefixed quality. For legacy direct rendering: "
        "python -m manim -ql SCENE.py SceneName (no managed manifest).",
    )
    parser.add_argument("scene_file", type=Path)
    parser.add_argument("scene_name")
    parser.add_argument("--profile", choices=("draft", "production"), default="draft")
    parser.add_argument("--provider", choices=PROVIDERS, help="Explicit choice; defaults to MANIM_TTS_PROVIDER or none, never key detection.")
    parser.add_argument("--quality", choices=QUALITIES, help="Overrides MANIM_QUALITY; draft=-ql, production=-qh.")
    parser.add_argument("--output-dir", type=Path, default=Path("media/runs"))
    parser.add_argument(
        "--cache-dir", type=Path,
        help="Reusable speech cache root; appends provider. Overrides MANIM_TTS_CACHE_ROOT, defaults to repository media/voiceovers.",
    )
    parser.add_argument("--run-id", help="Optional unique ID; existing run directories are rejected.")
    parser.add_argument("--require-tex", action="store_true", help="Preflight latex/dvisvgm even when TeX use is hidden in helpers.")
    parser.add_argument(
        "--source-file", dest="source_files", type=Path, action="append", default=[],
        help="Declare an external/untracked source, storyboard or narration input to fingerprint; repeatable.",
    )
    for key in ("model", "voice", "speed", "style", "style_degree"):
        parser.add_argument("--" + key.replace("_", "-"), help=f"Provider {key}; unsupported settings fail before synthesis.")
    args = vars(parser.parse_args(argv))
    try:
        manifest = render(**args)
    except RenderError as exc:
        print(f"Render error: {exc}", file=sys.stderr)
        return exc.exit_code
    except (OSError, ValueError) as exc:
        print(f"Render error: {type(exc).__name__}; check scene/output paths and configuration.", file=sys.stderr)
        return 1
    print(f"Rendered (not reviewed or accepted): {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
