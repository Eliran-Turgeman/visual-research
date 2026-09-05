"""Extract start/middle/end review frames for every narration block.

This is a general-purpose review tool: it knows nothing about any specific
scene. It only needs a rendered video and a "narration timeline" JSON file
shaped like::

    {
      "scene_duration": 87.4,
      "blocks": [
        {"index": 0, "start": 0.0, "end": 6.2, "duration": 6.2, "text": "..."},
        ...
      ]
    }

Any scene that records this shape (see ``DDTreeDFlashExplainer.narrate`` in
``examples/ddtree_dflash/scene.py`` for one such producer) can be reviewed
with this script.

Usage::

    python scripts/extract_narration_frames.py VIDEO TIMELINE OUTPUT_DIR

For every block it extracts three JPEG frames -- near the start, the
midpoint, and near the end of the block -- nudged away from the exact block
boundaries and clamped inside the rendered scene duration. It also writes an
``index.json`` mapping every extracted frame back to its block's narration
text and timestamp, and assembles one or more contact-sheet images (using
Pillow, only if it is already installed) so a whole render can be skimmed at
a glance.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

FRAME_EPSILON = 0.02  # Never sample exactly at 0 or exactly at scene_duration.
MAX_BOUNDARY_OFFSET = 0.4  # Cap how far "near start"/"near end" nudge inward.
BOUNDARY_OFFSET_FRACTION = 0.15  # Fraction of block duration used as a nudge.
PHASES = ("start", "mid", "end")
MAX_ROWS_PER_CONTACT_SHEET = 8


@dataclass(frozen=True)
class Block:
    index: int
    start: float
    end: float
    duration: float
    text: str


@dataclass(frozen=True)
class Timeline:
    scene_duration: float
    blocks: tuple[Block, ...]


class TimelineValidationError(ValueError):
    """Raised when a timeline.json file does not match the expected shape."""


# --------------------------------------------------------------------------
# Pure, ffmpeg-free logic: kept separate from the subprocess/IO code below so
# it can be exercised directly by unit tests.
# --------------------------------------------------------------------------


def load_timeline(path: Path) -> dict:
    """Read and JSON-parse a timeline file, raising a clear error on failure."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TimelineValidationError(f"Could not read timeline file: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TimelineValidationError(
            f"Timeline file is not valid JSON: {exc}"
        ) from exc


def validate_timeline(data: object) -> Timeline:
    """Validate and normalize a parsed timeline document.

    Raises ``TimelineValidationError`` with a specific, actionable message for
    every way the document can be malformed: wrong types, a non-positive
    scene duration, an empty block list, out-of-order/negative/overlapping
    timestamps, blocks that run past the scene duration, duplicate or
    non-sequential indices, or missing/blank narration text.
    """
    if not isinstance(data, dict):
        raise TimelineValidationError("Timeline root must be a JSON object.")

    if "scene_duration" not in data:
        raise TimelineValidationError("Timeline is missing 'scene_duration'.")
    scene_duration = data["scene_duration"]
    if isinstance(scene_duration, bool) or not isinstance(
        scene_duration, (int, float)
    ):
        raise TimelineValidationError("'scene_duration' must be a number.")
    scene_duration = float(scene_duration)
    if scene_duration <= 0:
        raise TimelineValidationError("'scene_duration' must be positive.")

    raw_blocks = data.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise TimelineValidationError(
            "Timeline must contain a non-empty 'blocks' list."
        )

    blocks: list[Block] = []
    seen_indices: set[int] = set()
    for position, raw_block in enumerate(raw_blocks):
        if not isinstance(raw_block, dict):
            raise TimelineValidationError(
                f"Block at position {position} must be a JSON object."
            )

        index = raw_block.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise TimelineValidationError(
                f"Block at position {position} has a non-integer 'index'."
            )
        if index in seen_indices:
            raise TimelineValidationError(f"Duplicate block index {index}.")
        seen_indices.add(index)

        start = raw_block.get("start")
        end = raw_block.get("end")
        for field_name, value in (("start", start), ("end", end)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TimelineValidationError(
                    f"Block {index} has a non-numeric '{field_name}'."
                )
        start = float(start)
        end = float(end)

        if start < 0:
            raise TimelineValidationError(f"Block {index} has a negative start.")
        if end <= start:
            raise TimelineValidationError(
                f"Block {index} has end ({end}) at or before start ({start})."
            )
        # A small render-timing tolerance: the last block's synchronization
        # wait can land a few milliseconds past a scene_duration snapshot
        # taken a moment earlier.
        if end > scene_duration + 0.5:
            raise TimelineValidationError(
                f"Block {index} ends ({end}) after scene_duration "
                f"({scene_duration})."
            )

        text = raw_block.get("text")
        if not isinstance(text, str) or not text.strip():
            raise TimelineValidationError(f"Block {index} has empty 'text'.")

        duration = raw_block.get("duration", end - start)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise TimelineValidationError(
                f"Block {index} has a non-numeric 'duration'."
            )
        duration = float(duration)

        blocks.append(
            Block(index=index, start=start, end=end, duration=duration, text=text)
        )

    blocks.sort(key=lambda block: block.start)
    for previous, current in zip(blocks, blocks[1:]):
        if current.start < previous.end - 1e-6:
            raise TimelineValidationError(
                f"Block {current.index} starts ({current.start}) before block "
                f"{previous.index} ends ({previous.end}); narration blocks must "
                "not overlap."
            )

    return Timeline(scene_duration=scene_duration, blocks=tuple(blocks))


def compute_review_timestamps(
    start: float, end: float, scene_duration: float
) -> dict[str, float]:
    """Pick safe start/mid/end sample timestamps for one narration block.

    The start/end samples are nudged inward by a fraction of the block's
    duration (capped at ``MAX_BOUNDARY_OFFSET`` seconds) so they land just
    inside the block instead of exactly on a boundary shared with the
    previous or next block. The midpoint is the block's true center. Every
    timestamp is then clamped strictly inside ``(0, scene_duration)`` so
    ffmpeg is never asked to seek to, or past, the very first or last frame
    of the video.
    """
    if end < start:
        raise ValueError("end must not be before start")
    if scene_duration <= 0:
        raise ValueError("scene_duration must be positive")

    duration = end - start
    half = duration / 2
    offset = min(MAX_BOUNDARY_OFFSET, duration * BOUNDARY_OFFSET_FRACTION, half * 0.98)
    offset = max(offset, 0.0)

    raw = {
        "start": start + offset,
        "mid": (start + end) / 2,
        "end": end - offset,
    }

    lower = min(FRAME_EPSILON, scene_duration / 4)
    upper = max(lower, scene_duration - FRAME_EPSILON)
    return {phase: min(upper, max(lower, value)) for phase, value in raw.items()}


def frame_filename(index: int, phase: str, index_width: int) -> str:
    """Deterministic, sortable frame filename for one block/phase pair."""
    if phase not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}, got {phase!r}")
    return f"block{index:0{index_width}d}_{phase}.jpg"


def build_index(timeline: Timeline, frames_dir: Path) -> list[dict]:
    """Build the frame -> narration-text/timestamp mapping written to index.json."""
    index_width = max(2, len(str(max(block.index for block in timeline.blocks))))
    entries = []
    for block in timeline.blocks:
        timestamps = compute_review_timestamps(
            block.start, block.end, timeline.scene_duration
        )
        for phase in PHASES:
            filename = frame_filename(block.index, phase, index_width)
            entries.append(
                {
                    "file": str(frames_dir / filename),
                    "block_index": block.index,
                    "phase": phase,
                    "timestamp": timestamps[phase],
                    "block_start": block.start,
                    "block_end": block.end,
                    "text": block.text,
                }
            )
    return entries


# --------------------------------------------------------------------------
# ffmpeg / filesystem side effects.
# --------------------------------------------------------------------------


def resolve_ffmpeg() -> str:
    """Find an ffmpeg executable: system PATH first, then imageio_ffmpeg."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise SystemExit(
            "No ffmpeg executable found on PATH, and imageio_ffmpeg is not "
            "installed. Install FFmpeg, or run "
            "`pip install imageio-ffmpeg`."
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_frame(ffmpeg_exe: str, video: Path, timestamp: float, output: Path) -> None:
    command = [
        ffmpeg_exe,
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output),
    ]
    subprocess.run(command, check=True)


def build_contact_sheets(entries: list[dict], output_dir: Path) -> list[Path]:
    """Assemble readable contact sheets from already-extracted frames.

    Uses Pillow, which is already a transitive dependency of this repository
    (Manim itself depends on it) -- no new dependency is added. If Pillow is
    not importable for any reason, contact sheets are silently skipped; the
    per-frame JPEGs and index.json remain fully usable on their own.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print(
            "Pillow is not available; skipping contact sheet assembly "
            "(per-frame JPEGs and index.json were still written).",
            file=sys.stderr,
        )
        return []

    thumb_width = 320
    caption_height = 54
    padding = 8
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover - defensive against odd PIL builds
        font = None

    by_block: dict[int, dict[str, dict]] = {}
    for entry in entries:
        by_block.setdefault(entry["block_index"], {})[entry["phase"]] = entry
    block_indices = sorted(by_block)

    sheets: list[Path] = []
    chunk_size = MAX_ROWS_PER_CONTACT_SHEET
    for sheet_number, chunk_start in enumerate(
        range(0, len(block_indices), chunk_size), start=1
    ):
        chunk = block_indices[chunk_start : chunk_start + chunk_size]
        thumbs: dict[int, dict[str, "Image.Image"]] = {}
        thumb_height = None
        for index in chunk:
            thumbs[index] = {}
            for phase in PHASES:
                entry = by_block[index].get(phase)
                if entry is None:
                    continue
                frame_path = Path(entry["file"])
                if not frame_path.exists():
                    continue
                with Image.open(frame_path) as source:
                    ratio = thumb_width / source.width
                    height = max(1, round(source.height * ratio))
                    thumb_height = thumb_height or height
                    thumbs[index][phase] = source.convert("RGB").resize(
                        (thumb_width, height)
                    )
        thumb_height = thumb_height or round(thumb_width * 9 / 16)

        row_height = thumb_height + caption_height
        sheet_width = padding + len(PHASES) * (thumb_width + padding)
        sheet_height = padding + len(chunk) * (row_height + padding)
        sheet = Image.new("RGB", (sheet_width, sheet_height), color=(20, 20, 24))
        draw = ImageDraw.Draw(sheet)

        for row, index in enumerate(chunk):
            y = padding + row * (row_height + padding)
            text = by_block[index][PHASES[0]]["text"] if PHASES[0] in by_block[index] else ""
            for column, phase in enumerate(PHASES):
                x = padding + column * (thumb_width + padding)
                thumb = thumbs[index].get(phase)
                if thumb is not None:
                    sheet.paste(thumb, (x, y))
                entry = by_block[index].get(phase)
                caption = f"#{index} {phase}"
                if entry is not None:
                    caption += f" @ {entry['timestamp']:.2f}s"
                draw.text((x + 2, y + thumb_height + 2), caption, fill=(230, 230, 230), font=font)
            wrapped = _wrap_text(text, 92)
            draw.text(
                (padding, y + thumb_height + 18),
                wrapped,
                fill=(150, 200, 255),
                font=font,
            )

        sheet_path = output_dir / f"contact_sheet_{sheet_number:03d}.jpg"
        sheet.save(sheet_path, quality=88)
        sheets.append(sheet_path)

    return sheets


def _wrap_text(text: str, width: int) -> str:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines[:2])


# --------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract start/middle/end review frames and contact sheets for "
            "every narration block of a rendered Manim video."
        )
    )
    parser.add_argument("video", type=Path, help="Path to the rendered video file.")
    parser.add_argument(
        "timeline", type=Path, help="Path to the narration timeline.json file."
    )
    parser.add_argument(
        "output_dir", type=Path, help="Directory to write frames and index.json into."
    )
    return parser.parse_args(argv)


def validate_cli_inputs(video: Path, timeline: Path, output_dir: Path) -> None:
    if not video.exists():
        raise SystemExit(f"Video file does not exist: {video}")
    if not video.is_file():
        raise SystemExit(f"Video path is not a file: {video}")
    if video.stat().st_size == 0:
        raise SystemExit(f"Video file is empty: {video}")

    if not timeline.exists():
        raise SystemExit(f"Timeline file does not exist: {timeline}")
    if not timeline.is_file():
        raise SystemExit(f"Timeline path is not a file: {timeline}")

    if output_dir.exists() and not output_dir.is_dir():
        raise SystemExit(f"Output path exists and is not a directory: {output_dir}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    video = args.video.resolve()
    timeline_path = args.timeline.resolve()
    output_dir = args.output_dir.resolve()

    validate_cli_inputs(video, timeline_path, output_dir)

    try:
        timeline = validate_timeline(load_timeline(timeline_path))
    except TimelineValidationError as exc:
        raise SystemExit(f"Invalid timeline: {exc}") from exc

    ffmpeg_exe = resolve_ffmpeg()

    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    entries = build_index(timeline, frames_dir)
    for entry in entries:
        extract_frame(ffmpeg_exe, video, entry["timestamp"], Path(entry["file"]))

    index_path = output_dir / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "video": str(video),
                "timeline": str(timeline_path),
                "scene_duration": timeline.scene_duration,
                "block_count": len(timeline.blocks),
                "frame_count": len(entries),
                "frames": entries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    sheets = build_contact_sheets(entries, output_dir)

    print(
        f"Extracted {len(entries)} frames for {len(timeline.blocks)} narration "
        f"blocks -> {frames_dir}"
    )
    print(f"Index written to {index_path}")
    if sheets:
        print(f"Contact sheet(s): {', '.join(str(sheet) for sheet in sheets)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
