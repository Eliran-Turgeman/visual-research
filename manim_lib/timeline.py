"""The shared, stdlib-only narration timeline protocol.

``parse_timeline`` accepts legacy documents (omitted schema_version/run_id and
block duration) and version 1. It never sorts or mutates input. Blocks must be
nonempty, sequential from zero, positive-length and contain nonblank text.
Supplied optional identifiers must be nonblank strings, never null.

Numbers must be int/float (not bool), convertible to finite binary64. Comparisons
use the exact decimal spelling of those converted floats, avoiding an implicit
relative tolerance or a hidden epsilon at the boundary: <= 0.001 seconds for
duration arithmetic and block scene overrun; <= 0.000001 seconds for block
overlap and event ordering. Negative starts and events outside [0, scene_duration]
are always invalid. The boundary is inclusive; the next representable value
beyond it is not. These are NOT encoded-media/frame/codec tolerances.

Event data is opaque and preserved for teaching-specific semantic comparison.
Other extension fields (e.g. audio references) remain in the original document;
the parsed view is not a replacement serialization or an audio schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from typing import Any


SCHEMA_VERSION = 1
TIMELINE_TOLERANCE = 0.001
ORDER_TOLERANCE = 0.000001
_TIMING_LIMIT = Fraction(str(TIMELINE_TOLERANCE))
_ORDER_LIMIT = Fraction(str(ORDER_TOLERANCE))


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
    data: Any = None


@dataclass(frozen=True)
class Timeline:
    scene_duration: float
    blocks: tuple[Block, ...]
    run_id: str | None = None
    events: tuple[Event, ...] = ()


class TimelineError(ValueError):
    """An actionable structural failure with a stable category and field path."""

    def __init__(self, code: str, path: str, message: str):
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def finite_number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TimelineError("shape", path, f"Timeline has non-numeric '{path.rsplit('.', 1)[-1]}'.")
    try:
        result = float(value)
    except OverflowError as exc:
        raise TimelineError("shape", path, "Number must be finite.") from exc
    if not math.isfinite(result):
        raise TimelineError("shape", path, "Number must be finite.")
    return result


def nonblank_text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TimelineError("shape", path, "Expected a nonblank string.")
    return value


def _optional_text(data: dict, key: str, path: str) -> str | None:
    return nonblank_text(data[key], f"{path}.{key}") if key in data else None


def _exact(value: float) -> Fraction:
    return Fraction(str(value))


def parse_timeline(data: object, *, run_id: str | None = None) -> Timeline:
    """Validate once and return a typed view; optionally bind a managed run."""
    if not isinstance(data, dict):
        raise TimelineError("shape", "timeline", "Timeline root must be a JSON object.")
    if "schema_version" in data and (
        type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION
    ):
        raise TimelineError("shape", "timeline.schema_version", "Timeline schema_version must be 1.")
    identity = _optional_text(data, "run_id", "timeline")
    if run_id is not None:
        nonblank_text(run_id, "required_run_id")
        if identity != run_id:
            raise TimelineError("identity", "timeline.run_id", "Timeline run_id does not match the required run_id; refusing stale timing.")
    scene_duration = finite_number(data.get("scene_duration"), "timeline.scene_duration")
    if scene_duration <= 0:
        raise TimelineError("shape", "timeline.scene_duration", "scene_duration must be positive.")
    scene_end = _exact(scene_duration)
    raw_blocks = data.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise TimelineError("shape", "timeline.blocks", "Timeline must contain a non-empty 'blocks' list.")
    blocks = []
    seen_indices = set()
    for position, raw in enumerate(raw_blocks):
        path = f"timeline.blocks[{position}]"
        if not isinstance(raw, dict):
            raise TimelineError("shape", path, "Block must be a JSON object.")
        index = raw.get("index")
        if type(index) is not int:
            raise TimelineError("order", f"{path}.index", "Block has a non-integer 'index'.")
        if index in seen_indices:
            raise TimelineError("order", f"{path}.index", f"Duplicate block index {index}.")
        if index != position:
            raise TimelineError("order", f"{path}.index", f"Block index must be sequential from zero: expected {position}.")
        seen_indices.add(index)
        start = finite_number(raw.get("start"), f"{path}.start")
        end = finite_number(raw.get("end"), f"{path}.end")
        if start < 0:
            raise TimelineError("shape", f"{path}.start", "Block has a negative start.")
        if end <= start:
            raise TimelineError("duration", f"{path}.end", "Block has end at or before start.")
        if _exact(end) - scene_end > _TIMING_LIMIT:
            raise TimelineError("order", f"{path}.end", "Block ends after scene_duration (1 ms tolerance).")
        if blocks and _exact(blocks[-1].end) - _exact(start) > _ORDER_LIMIT:
            raise TimelineError("order", f"{path}.start", "Block is out of order or overlaps the preceding block.")
        duration = finite_number(raw.get("duration", end - start), f"{path}.duration")
        if duration <= 0 or (
            "duration" in raw and abs(_exact(duration) - (_exact(end) - _exact(start))) > _TIMING_LIMIT
        ):
            raise TimelineError("duration", f"{path}.duration", "Block duration must be positive and equal end-start within 1 ms.")
        text = nonblank_text(raw.get("text"), f"{path}.text")
        blocks.append(Block(index, start, end, duration, text, _optional_text(raw, "beat_id", path)))
    raw_events = data.get("events", [])
    if not isinstance(raw_events, list):
        raise TimelineError("shape", "timeline.events", "'events' must be a list.")
    events = []
    for position, raw in enumerate(raw_events):
        path = f"timeline.events[{position}]"
        if not isinstance(raw, dict):
            raise TimelineError("shape", path, "Event must be a JSON object.")
        time = finite_number(raw.get("time"), f"{path}.time")
        if not 0 <= time <= scene_duration:
            raise TimelineError("order", f"{path}.time", "Event time is outside scene_duration.")
        if events and _exact(events[-1].time) - _exact(time) > _ORDER_LIMIT:
            raise TimelineError("order", f"{path}.time", "Events must be in timestamp order.")
        label = nonblank_text(raw.get("label"), f"{path}.label")
        events.append(Event(time, label, _optional_text(raw, "beat_id", path), raw.get("data")))
    return Timeline(scene_duration, tuple(blocks), identity, tuple(events))
