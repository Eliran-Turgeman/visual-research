"""Mux explicitly paired external narration without trimming a visual hold.

Usage: python examples\\ddtree_dflash\\mux_audio.py VIDEO OUTPUT --manifest JSON
       [--timeline TIMELINE] [--run-id EXPECTED_RUN]

Preferred manifest: schema_version=1, run_id, scene_duration,
video={path,sha256}, tracks=[{file,sha256,start,duration,text}].
Paths are manifest-relative or absolute. Versioned manifests require hashes
for the selected silent video and every audio track. A legacy manifest has
scene_duration/tracks and requires --timeline: scene/video duration, block count,
text, starts and track durations are cross-checked. This is meaningful legacy
compatibility, not cryptographic proof that an unbound old timeline belongs to
the video; use versioned hash-bound manifests for strong provenance.

Inputs must already exist. No speech is generated or requested here. Track
overlap/truncation, stale hashes, unsupported versions and an already-audible
input video are errors. Output is published only after complete decode and
audio/video-duration verification; failed muxes cannot replace a good output.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from manim_lib.review import (
    ReviewError, artifact_reference, finite_number, media_tolerance, probe_media,
    read_json, resolve_ffmpeg, sha256_file, validate_decode, validate_video_timing,
    verify_reference, write_json,
)
from scripts.extract_narration_frames import TIMELINE_TOLERANCE, load_timeline, validate_timeline


def ffmpeg_executable() -> str:
    return resolve_ffmpeg()


def validate_pairing(
    video: Path, manifest_path: Path, *, timeline_path: Path | None = None,
    run_id: str | None = None,
) -> tuple[dict, dict, list[dict]]:
    manifest = read_json(manifest_path)
    scene_duration = finite_number(manifest.get("scene_duration"), "scene_duration", positive=True)
    versioned = "schema_version" in manifest
    if versioned and (type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1):
        raise ReviewError("External narration schema_version must be 1.")
    if versioned and (not isinstance(manifest.get("run_id"), str) or not manifest["run_id"].strip()):
        raise ReviewError("Versioned narration manifest requires run_id.")
    if run_id is not None and manifest.get("run_id") != run_id:
        raise ReviewError("Narration manifest does not match the requested run_id.")
    reference = manifest.get("video")
    if versioned and reference is None:
        raise ReviewError("Versioned narration manifest requires a video hash binding.")
    if reference is not None:
        paired_video = verify_reference(reference, manifest_path.parent, "silent video")
        if paired_video != video.resolve():
            raise ReviewError("Narration manifest is paired with a different video path.")
    elif timeline_path is None:
        raise ReviewError("Legacy narration requires --timeline to validate the video/track pairing.")
    media = probe_media(video)
    validate_video_timing(media, scene_duration)
    if media["audio_duration"] is not None:
        raise ReviewError("Input video already has audio; provide the matching silent render.")
    raw_tracks = manifest.get("tracks")
    if not isinstance(raw_tracks, list) or not raw_tracks:
        raise ReviewError("The narration manifest must contain a nonempty tracks list.")
    timeline = validate_timeline(load_timeline(timeline_path)) if timeline_path else None
    if timeline is not None:
        if abs(timeline.scene_duration - scene_duration) > TIMELINE_TOLERANCE:
            raise ReviewError("Narration manifest and timeline scene_duration differ.")
        if manifest.get("run_id") is not None and timeline.run_id != manifest["run_id"]:
            raise ReviewError("Narration manifest and timeline run_id differ.")
        if len(timeline.blocks) != len(raw_tracks):
            raise ReviewError("Narration track count differs from timeline block count.")
    tracks = []
    previous_end = 0.0
    for index, raw in enumerate(raw_tracks):
        if not isinstance(raw, dict):
            raise ReviewError(f"Track {index} must be an object.")
        start = finite_number(raw.get("start"), f"Track {index} start")
        duration = finite_number(raw.get("duration"), f"Track {index} duration", positive=True)
        if start < 0 or start < previous_end - TIMELINE_TOLERANCE:
            raise ReviewError(f"Track {index} has negative, overlapping or out-of-order timing.")
        if start + duration > scene_duration + TIMELINE_TOLERANCE:
            raise ReviewError(f"Track {index} exceeds the recorded scene duration; narration would be cut off.")
        filename = raw.get("file")
        if not isinstance(filename, str) or not filename.strip():
            raise ReviewError(f"Track {index} requires a file.")
        path = (manifest_path.parent / filename).resolve()
        digest = sha256_file(path)
        if versioned or "sha256" in raw:
            verify_reference({"path": str(path), "sha256": raw.get("sha256")}, manifest_path.parent, f"track {index}")
        audio = probe_media(path)
        if audio["audio_duration"] is None or audio["video_duration"] is not None:
            raise ReviewError(f"Track {index} must be an audio-only media file.")
        # MP3/AAC padding may affect the probed duration, never an entire spoken tail.
        if abs(audio["audio_duration"] - duration) > 0.1 + 1e-6:
            raise ReviewError(f"Track {index} duration disagrees with the actual audio (100 ms tolerance).")
        if abs(audio["audio_start"] or 0) > 0.1:
            raise ReviewError(f"Track {index} audio must start at zero.")
        if timeline is not None:
            block = timeline.blocks[index]
            if abs(start - block.start) > TIMELINE_TOLERANCE or raw.get("text") != block.text:
                raise ReviewError(f"Track {index} start/text does not match the selected timeline.")
            if start + duration > block.end + TIMELINE_TOLERANCE:
                raise ReviewError(f"Track {index} exceeds its timeline block.")
        tracks.append({"file": str(path), "sha256": digest, "start": start, "duration": duration})
        previous_end = start + duration
    return manifest, media, tracks


def mux_audio(
    video: Path, output: Path, manifest_path: Path, *,
    timeline_path: Path | None = None, run_id: str | None = None,
) -> Path:
    video, output, manifest_path = video.resolve(), output.resolve(), manifest_path.resolve()
    if output.exists():
        raise ReviewError(f"Output already exists; choose a fresh path: {output}")
    manifest, media, tracks = validate_pairing(
        video, manifest_path, timeline_path=timeline_path, run_id=run_id,
    )
    inputs = [video, manifest_path, *(Path(t["file"]) for t in tracks)]
    if timeline_path is not None:
        inputs.append(timeline_path.resolve())
    if output in inputs:
        raise ReviewError("Output cannot overwrite an input artifact.")
    before = [artifact_reference(path) for path in inputs]
    duration = media["video_duration"]
    # Never extend beyond the encoded video; only codec rounding may be trimmed.
    if any(t["start"] + t["duration"] > duration + media_tolerance(media["fps"]) for t in tracks):
        raise ReviewError("Narration exceeds encoded video duration.")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(f".{output.stem}.{uuid.uuid4().hex}.muxing{output.suffix}")
    receipt = output.with_suffix(output.suffix + ".mux.json")
    if receipt.exists():
        raise ReviewError(f"Mux receipt already exists: {receipt}")
    command = [
        ffmpeg_executable(), "-nostdin", "-v", "error", "-xerror", "-n",
        "-filter_complex_threads", "1", "-i", str(video),
    ]
    for track in tracks:
        command.extend(["-i", track["file"]])
    filters, labels = [], []
    for index, track in enumerate(tracks, start=1):
        label = f"a{index}"
        delay = round(track["start"] * 48000)
        filters.append(
            f"[{index}:a:0]aresample=48000,atrim=duration={track['duration']:.9f},"
            f"asetpts=PTS-STARTPTS,adelay=delays={delay}S:all=1[{label}]"
        )
        labels.append(f"[{label}]")
    # Count samples, not inherited EOF timestamps: amix/apad can emit unset PTS.
    scene_samples = round(duration * 48000)
    filters.append(
        "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
        f"apad=whole_len={scene_samples},atrim=end_sample={scene_samples},asetpts=N/SR/TB[aout]"
    )
    command.extend([
        "-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", str(staging),
    ])
    try:
        subprocess.run(command, check=True, capture_output=True, text=True,
                       timeout=max(120, duration * 4 + 60))
        validate_video_timing(probe_media(staging), duration, require_audio=True)
        validate_decode(staging)
        if before != [artifact_reference(path) for path in inputs]:
            raise ReviewError("Inputs changed during muxing; refusing to publish mixed-run output.")
        staging.replace(output)
        write_json(receipt, {
            "schema_version": 1, "run_id": manifest.get("run_id"), "status": "muxed",
            "pairing": "hash_bound" if manifest.get("video") else "legacy_timeline_checked",
            "inputs": before, "output": artifact_reference(output),
            "scene_duration": manifest["scene_duration"], "media": probe_media(output),
        })
    except subprocess.CalledProcessError as exc:
        raise ReviewError(f"FFmpeg mux failed: {exc.stderr.strip()}") from exc
    finally:
        staging.unlink(missing_ok=True)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--timeline", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    try:
        result = mux_audio(args.video, args.output, args.manifest, timeline_path=args.timeline, run_id=args.run_id)
    except (ReviewError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Audio mux failed: {exc}\n")
    print(f"Verified full-duration narrated video: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
