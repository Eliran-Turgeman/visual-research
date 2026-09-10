"""Extract artifact-bound narration and transition review frames.

Usage: python scripts\\extract_narration_frames.py VIDEO TIMELINE OUTPUT_DIR

Valid legacy timelines have scene_duration and ordered, zero-based blocks with
index/start/end/text; omitted duration is inferred. Optional schema_version=1,
run_id, events=[{time, label, beat_id?}], and block beat_id are preserved.
All numbers must be finite. Duration arithmetic/scene overrun tolerance is 1 ms;
ordering/overlap tolerance is 1 microsecond. Video duration must agree within
max(100 ms, two frames). Input order is validated, never silently sorted.

The plan contains three samples per block plus the first/final usable frames
and the frames before/after every block boundary and declared event. Additional
samples on the same encoded frame are merged while retaining all their labels.
At most 512 JPEGs are extracted by default; an excessive plan fails explicitly
rather than omitting transitions. The output directory must be empty, preventing
old frames/indexes from masquerading as a successful run. index.json is published
only after every JPEG and optional contact sheet has been verified and hashed.
Still frames cannot establish audiovisual quality or comprehension.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from manim_lib.review import (
    ReviewError, artifact_reference, probe_media, resolve_ffmpeg, sha256_file,
    validate_video_timing, write_json,
)

FRAME_EPSILON = 0.02
MAX_BOUNDARY_OFFSET = 0.4
BOUNDARY_OFFSET_FRACTION = 0.15
PHASES = ("start", "mid", "end")
MAX_ROWS_PER_CONTACT_SHEET = 8
TIMELINE_TOLERANCE = 0.001
ORDER_TOLERANCE = 1e-6
MAX_REVIEW_FRAMES = 512


@dataclass(frozen=True)
class Block:
    index: int
    start: float
    end: float
    duration: float
    text: str
    beat_id: str | None = None


@dataclass(frozen=True)
class Event:
    time: float
    label: str
    beat_id: str | None = None


@dataclass(frozen=True)
class Timeline:
    scene_duration: float
    blocks: tuple[Block, ...]
    run_id: str | None = None
    events: tuple[Event, ...] = ()


class TimelineValidationError(ReviewError):
    """The timeline does not describe a finite, ordered recorded scene."""


def load_timeline(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TimelineValidationError(f"Could not read timeline file: {exc}") from exc
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise TimelineValidationError(f"Timeline file is not valid JSON: {exc}") from exc


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TimelineValidationError(f"Timeline has non-numeric {field}.")
    try:
        value = float(value)
    except OverflowError as exc:
        raise TimelineValidationError(f"{field} must be finite.") from exc
    if not math.isfinite(value):
        raise TimelineValidationError(f"{field} must be finite.")
    return value


def _optional_text(data: dict, key: str) -> str | None:
    value = data.get(key)
    if key in data and (not isinstance(value, str) or not value.strip()):
        raise TimelineValidationError(f"'{key}' must be a nonblank string when present.")
    return value


def validate_timeline(data: object) -> Timeline:
    if not isinstance(data, dict):
        raise TimelineValidationError("Timeline root must be a JSON object.")
    if "schema_version" in data and (type(data["schema_version"]) is not int or data["schema_version"] != 1):
        raise TimelineValidationError("Timeline schema_version must be 1.")
    scene_duration = _number(data.get("scene_duration"), "'scene_duration'")
    if scene_duration <= 0:
        raise TimelineValidationError("'scene_duration' must be positive.")
    run_id = _optional_text(data, "run_id")
    raw_blocks = data.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise TimelineValidationError("Timeline must contain a non-empty 'blocks' list.")
    blocks = []
    seen_indices = set()
    for position, raw in enumerate(raw_blocks):
        if not isinstance(raw, dict):
            raise TimelineValidationError(f"Block at position {position} must be a JSON object.")
        index = raw.get("index")
        if type(index) is not int:
            raise TimelineValidationError(f"Block at position {position} has a non-integer 'index'.")
        if index in seen_indices:
            raise TimelineValidationError(f"Duplicate block index {index}.")
        if index != position:
            raise TimelineValidationError(f"Block index must be sequential from zero: expected {position}, got {index}.")
        seen_indices.add(index)
        start = _number(raw.get("start"), "'start'")
        end = _number(raw.get("end"), "'end'")
        if start < 0:
            raise TimelineValidationError(f"Block {index} has a negative start.")
        if end <= start:
            raise TimelineValidationError(f"Block {index} has end at or before start.")
        if end > scene_duration + TIMELINE_TOLERANCE:
            raise TimelineValidationError(f"Block {index} ends after scene_duration.")
        if blocks and start < blocks[-1].end - ORDER_TOLERANCE:
            raise TimelineValidationError(f"Block {index} is out of order or overlaps the preceding block.")
        duration = _number(raw.get("duration", end - start), "'duration'")
        if duration <= 0 or abs(duration - (end - start)) > TIMELINE_TOLERANCE + 1e-9:
            raise TimelineValidationError(f"Block {index} duration must be positive and equal end-start within 1 ms.")
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise TimelineValidationError(f"Block {index} has empty 'text'.")
        blocks.append(Block(index, start, end, duration, text, _optional_text(raw, "beat_id")))
    raw_events = data.get("events", [])
    if not isinstance(raw_events, list):
        raise TimelineValidationError("'events' must be a list.")
    events = []
    for raw in raw_events:
        if not isinstance(raw, dict):
            raise TimelineValidationError("Every event must be a JSON object.")
        time = _number(raw.get("time"), "event time")
        if not 0 <= time <= scene_duration:
            raise TimelineValidationError("Event time is outside scene_duration.")
        if events and time < events[-1].time - ORDER_TOLERANCE:
            raise TimelineValidationError("Events must be in timestamp order.")
        label = raw.get("label")
        if not isinstance(label, str) or not label.strip():
            raise TimelineValidationError("Event label must be nonblank.")
        events.append(Event(time, label, _optional_text(raw, "beat_id")))
    return Timeline(scene_duration, tuple(blocks), run_id, tuple(events))


def compute_review_timestamps(start: float, end: float, scene_duration: float) -> dict[str, float]:
    start = _number(start, "start")
    end = _number(end, "end")
    scene_duration = _number(scene_duration, "scene_duration")
    if end < start:
        raise ValueError("end must not be before start")
    if start < 0 or scene_duration <= 0:
        raise ValueError("start must be nonnegative and scene_duration positive")
    duration = end - start
    offset = min(MAX_BOUNDARY_OFFSET, duration * BOUNDARY_OFFSET_FRACTION, duration * 0.49)
    raw = {"start": start + offset, "mid": (start + end) / 2, "end": end - offset}
    lower = min(FRAME_EPSILON, scene_duration / 4)
    upper = max(lower, scene_duration - FRAME_EPSILON)
    return {phase: min(upper, max(lower, value)) for phase, value in raw.items()}


def frame_filename(index: int, phase: str, index_width: int) -> str:
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}, got {phase!r}")
    return f"block{index:0{index_width}d}_{phase}.jpg"


def build_index(
    timeline: Timeline, frames_dir: Path, *, fps: float = 30.0,
    media_duration: float | None = None, max_frames: int = MAX_REVIEW_FRAMES,
) -> list[dict]:
    """Build a bounded deterministic plan retaining event/boundary provenance."""
    fps = _number(fps, "fps")
    if fps <= 0:
        raise TimelineValidationError("fps must be positive.")
    duration = timeline.scene_duration if media_duration is None else _number(media_duration, "media_duration")
    if duration <= 0:
        raise TimelineValidationError("media_duration must be positive.")
    if type(max_frames) is not int or max_frames <= 0:
        raise TimelineValidationError("max_frames must be a positive integer.")
    last = max(0.0, duration - 1.0 / fps)
    index_width = max(2, len(str(max(block.index for block in timeline.blocks))))
    entries = []
    for block in timeline.blocks:
        timestamps = compute_review_timestamps(block.start, block.end, timeline.scene_duration)
        for phase in PHASES:
            entry = {
                "file": str(frames_dir / frame_filename(block.index, phase, index_width)),
                "block_index": block.index, "phase": phase,
                "timestamp": min(last, timestamps[phase]),
                "block_start": block.start, "block_end": block.end, "text": block.text,
            }
            if block.beat_id is not None:
                entry["beat_id"] = block.beat_id
            entries.append(entry)
    sampled = {math.ceil(entry["timestamp"] * fps - 1e-7): entry for entry in entries}

    def additional(time: float, source: dict) -> None:
        time = min(last, max(0.0, time))
        frame_number = math.ceil(time * fps - 1e-7)
        entry = sampled.get(frame_number)
        if entry is None:
            entry = {
                "file": str(frames_dir / f"boundary{len(sampled):04d}.jpg"),
                "block_index": None, "phase": "boundary", "timestamp": time,
                "text": source["label"],
            }
            sampled[frame_number] = entry
            entries.append(entry)
        entry.setdefault("sample_sources", []).append(source)

    # Explicit endpoints are sampled first and are not displaced by near-end events.
    additional(0.0, {"kind": "scene", "label": "first usable frame"})
    additional(last, {"kind": "scene", "label": "final usable frame"})
    for block in timeline.blocks:
        for side, time in (("start", block.start), ("end", block.end)):
            for phase, offset in (("before", -1.0 / fps), ("after", 1.0 / fps)):
                additional(time + offset, {
                    "kind": "block_boundary", "block_index": block.index,
                    "label": f"block {block.index} {side} {phase}", "time": time,
                    "beat_id": block.beat_id,
                })
    for event in timeline.events:
        for phase, offset in (("before", -1.0 / fps), ("after", 1.0 / fps)):
            additional(event.time + offset, {
                "kind": "event", "label": event.label, "phase": phase,
                "time": event.time, "beat_id": event.beat_id,
            })
    if len(entries) > max_frames:
        raise TimelineValidationError(
            f"Review plan needs {len(entries)} frames, exceeding limit {max_frames}; "
            "raise --max-frames explicitly or split the scene."
        )
    return entries


def verify_jpeg(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ReviewError(f"FFmpeg did not produce a nonempty frame: {path}")
    with path.open("rb") as source:
        if source.read(2) != b"\xff\xd8":
            raise ReviewError(f"Extracted file is not a JPEG: {path}")
    try:
        from PIL import Image
    except ImportError:
        return
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, ValueError) as exc:
        raise ReviewError(f"Invalid extracted JPEG {path}: {exc}") from exc


def extract_frame(ffmpeg_exe: str, video: Path, timestamp: float, output: Path) -> None:
    if output.exists():
        raise ReviewError(f"Refusing stale/existing frame output: {output}")
    try:
        subprocess.run(
            [ffmpeg_exe, "-n", "-loglevel", "error", "-xerror", "-ss", f"{timestamp:.9f}",
             "-i", str(video), "-frames:v", "1", "-q:v", "2", "-update", "1", str(output)],
            check=True, capture_output=True, text=True,
        )
        verify_jpeg(output)
    except Exception:
        output.unlink(missing_ok=True)
        raise


def build_contact_sheets(entries: list[dict], output_dir: Path) -> list[Path]:
    """Include every planned frame; missing/corrupt entries are errors."""
    for entry in entries:
        verify_jpeg(Path(entry["file"]))
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow unavailable; validated JPEGs remain available without contact sheets.", file=sys.stderr)
        return []
    thumb_width, thumb_height = 320, 180
    padding, caption_height = 8, 66
    columns = 3
    chunk_size = columns * MAX_ROWS_PER_CONTACT_SHEET
    font = ImageFont.load_default()
    sheets = []
    for number, offset in enumerate(range(0, len(entries), chunk_size), start=1):
        chunk = entries[offset:offset + chunk_size]
        rows = math.ceil(len(chunk) / columns)
        sheet = Image.new(
            "RGB", (padding + columns * (thumb_width + padding),
                    padding + rows * (thumb_height + caption_height + padding)), (20, 20, 24),
        )
        draw = ImageDraw.Draw(sheet)
        for position, entry in enumerate(chunk):
            x = padding + (position % columns) * (thumb_width + padding)
            y = padding + (position // columns) * (thumb_height + caption_height + padding)
            with Image.open(entry["file"]) as source:
                thumb = source.convert("RGB")
                thumb.thumbnail((thumb_width, thumb_height))
                sheet.paste(thumb, (x, y))
            caption = f"#{entry['block_index']} {entry['phase']} @ {entry['timestamp']:.3f}s"
            draw.text((x, y + thumb_height), caption, fill=(230, 230, 230), font=font)
            draw.text((x, y + thumb_height + 16), _wrap_text(entry["text"], 46),
                      fill=(150, 200, 255), font=font)
        path = output_dir / f"contact_sheet_{number:03d}.jpg"
        sheet.save(path, quality=88)
        verify_jpeg(path)
        sheets.append(path)
    return sheets


def _wrap_text(text: str, width: int) -> str:
    import textwrap
    return "\n".join(textwrap.wrap(text, width)[:2])


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-frames", type=int, default=MAX_REVIEW_FRAMES)
    return parser.parse_args(argv)


def validate_cli_inputs(video: Path, timeline: Path, output_dir: Path) -> None:
    for label, path in (("Video", video), ("Timeline", timeline)):
        if not path.exists():
            raise SystemExit(f"{label} file does not exist: {path}")
        if not path.is_file():
            raise SystemExit(f"{label} path is not a file: {path}")
        if not path.stat().st_size:
            raise SystemExit(f"{label} file is empty: {path}")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise SystemExit(f"Output path exists and is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise SystemExit(f"Output directory must be empty; use a fresh run directory: {output_dir}")


def extract_review(video: Path, timeline_path: Path, output_dir: Path, *, max_frames: int = MAX_REVIEW_FRAMES) -> Path:
    video, timeline_path, output_dir = video.resolve(), timeline_path.resolve(), output_dir.resolve()
    validate_cli_inputs(video, timeline_path, output_dir)
    artifacts = {"video": artifact_reference(video), "timeline": artifact_reference(timeline_path)}
    timeline = validate_timeline(load_timeline(timeline_path))
    media = probe_media(video)
    validate_video_timing(media, timeline.scene_duration)
    frames_dir = output_dir / "frames"
    entries = build_index(timeline, frames_dir, fps=media["fps"],
                          media_duration=media["video_duration"], max_frames=max_frames)
    frames_dir.mkdir(parents=True, exist_ok=False)
    ffmpeg = resolve_ffmpeg()
    for entry in entries:
        output = Path(entry["file"])
        extract_frame(ffmpeg, video, entry["timestamp"], output)
        entry["sha256"] = sha256_file(output)
    sheets = build_contact_sheets(entries, output_dir)
    if artifacts != {"video": artifact_reference(video), "timeline": artifact_reference(timeline_path)}:
        raise ReviewError("Source artifacts changed during extraction; discard this incomplete run.")
    index_path = output_dir / "index.json"
    write_json(index_path, {
        "schema_version": 1, "run_id": timeline.run_id, "artifacts": artifacts,
        "video": str(video), "timeline": str(timeline_path), "media": media,
        "scene_duration": timeline.scene_duration, "block_count": len(timeline.blocks),
        "frame_count": len(entries), "max_frames": max_frames, "frames": entries,
        "contact_sheets": [artifact_reference(sheet) for sheet in sheets],
    })
    return index_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        index = extract_review(args.video, args.timeline, args.output_dir, max_frames=args.max_frames)
    except (ReviewError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Frame extraction failed: {exc}") from exc
    print(f"Verified frame evidence written to {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
