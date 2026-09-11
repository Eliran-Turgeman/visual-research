"""Identical documents must have identical structural outcomes at every surface."""

import copy
from dataclasses import fields
import json
import math
from pathlib import Path

import pytest

from manim_lib import production, review, teaching
from manim_lib.timeline import Block, Event, Timeline, TimelineError, parse_timeline
from scripts import extract_narration_frames as frames


ROOT = Path(__file__).resolve().parents[1]
OMIT = object()


@pytest.fixture
def contract():
    document = teaching.load_contract(
        ROOT / "examples" / "speculative_decoding_timeline" / "teaching.json"
    )
    document["beats"] = document["beats"][:2]
    for beat in document["beats"]:
        beat.pop("events", None)
        beat.pop("duration_range", None)
    assert teaching.validate_contract(document)["valid"]
    return document


@pytest.fixture
def timeline(contract):
    return {
        "schema_version": 1, "run_id": "run-conformance", "scene_duration": 4,
        "blocks": [
            {"index": i, "start": i * 2, "end": (i + 1) * 2,
             "duration": 2, "text": beat["narration"]["text"]}
            for i, beat in enumerate(contract["beats"])
        ],
        "events": [{"time": 2, "label": "state", "data": {"nested": [True, None, 7]}}],
    }


def assert_conformance(document, contract, accepted):
    before = copy.deepcopy(document)
    report = teaching.validate_contract(contract, timeline=document)
    assert report["valid"] is accepted, report["errors"]
    json.dumps(report, allow_nan=False)
    for adapter, error_type in (
        (production.validate_timeline, production.RenderError),
        (frames.validate_timeline, frames.TimelineValidationError),
        (review.validate_timeline, review.ReviewError),
    ):
        if accepted:
            result = adapter(document)
            if adapter is production.validate_timeline:
                assert result is document
            else:
                assert isinstance(result, Timeline)
        else:
            with pytest.raises(error_type) as caught:
                adapter(document)
            cause = caught.value.__cause__
            assert isinstance(cause, TimelineError)
            assert report["errors"][0]["code"] == f"timeline_{cause.code}"
            assert report["errors"][0]["path"] == cause.path
            assert cause.path in str(caught.value)
            assert cause.message
    assert document == before


def replace(document, path, value):
    target = document
    for part in path[:-1]:
        target = target[part]
    if value is OMIT:
        target.pop(path[-1])
    else:
        target[path[-1]] = value


CASES = [
    pytest.param(("blocks",), [], False, id="empty-blocks-contradiction"),
    pytest.param(("blocks", 0, "beat_id"), None, False, id="null-beat-contradiction"),
    pytest.param(("blocks", 0, "duration"), 2.0005, True, id="half-ms-contradiction"),
    pytest.param(("blocks", 0, "duration"), OMIT, True, id="legacy-duration"),
    pytest.param(("schema_version",), OMIT, True, id="legacy-version"),
    pytest.param(("run_id",), OMIT, True, id="legacy-run"),
    pytest.param(("events",), OMIT, True, id="legacy-events"),
    pytest.param(("blocks",), None, False, id="null-blocks"),
    pytest.param(("blocks",), {}, False, id="object-blocks"),
    pytest.param(("blocks", 0), "bad", False, id="nonobject-block"),
    pytest.param(("events",), None, False, id="null-events"),
    pytest.param(("events",), {}, False, id="object-events"),
    pytest.param(("events", 0), [], False, id="nonobject-event"),
    pytest.param(("events", 0, "label"), " \t", False, id="blank-event-label"),
    pytest.param(("blocks", 0, "text"), " \t", False, id="blank-text"),
    pytest.param(("blocks", 0, "text"), False, False, id="boolean-text"),
    pytest.param(("blocks", 0, "start"), -0.0, True, id="negative-zero"),
    pytest.param(("blocks", 0, "start"), -math.ulp(0.0), False, id="negative-start"),
    pytest.param(("blocks", 0, "end"), 0, False, id="zero-block"),
    pytest.param(("blocks", 0, "end"), -1, False, id="backwards-block"),
    pytest.param(("scene_duration",), 0, False, id="zero-scene"),
    pytest.param(("scene_duration",), -1, False, id="negative-scene"),
    pytest.param(("blocks", 0, "duration"), 0, False, id="zero-duration"),
    pytest.param(("blocks", 0, "duration"), -1, False, id="negative-duration"),
]
for value in (None, True, 1.0, 2, "1"):
    CASES.append(pytest.param(("schema_version",), value, False, id=f"version-{value!r}"))
for field in ("index", "start", "end", "text"):
    CASES.append(pytest.param(("blocks", 0, field), OMIT, False, id=f"missing-{field}"))
for value in (-1, 1, True, 0.0, "0"):
    CASES.append(pytest.param(("blocks", 0, "index"), value, False, id=f"index-{value!r}"))
CASES.append(pytest.param(("blocks", 1, "index"), 0, False, id="duplicate-index"))
for path in (("run_id",), ("blocks", 0, "beat_id"), ("events", 0, "beat_id")):
    for value in (None, "", " \t", True, 1):
        CASES.append(pytest.param(path, value, False, id=f"{path}-identifier-{value!r}"))
for path in (
    ("scene_duration",), ("blocks", 0, "start"), ("blocks", 0, "end"),
    ("blocks", 0, "duration"), ("events", 0, "time"),
):
    for label, value in (
        ("bool", True), ("nan", math.nan), ("inf", math.inf),
        ("negative-inf", -math.inf), ("huge-int", 10**1000), ("string", "2"),
    ):
        CASES.append(pytest.param(path, value, False, id=f"{path}-{label}"))


@pytest.mark.parametrize("path,value,accepted", CASES)
def test_shared_documents(timeline, contract, path, value, accepted):
    replace(timeline, path, value)
    assert_conformance(timeline, contract, accepted)


@pytest.mark.parametrize("root", [[], False, "timeline", 4])
def test_nonobject_roots(root, contract):
    assert_conformance(root, contract, False)


def test_absent_teaching_evidence_is_not_a_structural_pass(contract):
    # None is the established validate_contract API's "not supplied" sentinel.
    report = teaching.validate_contract(contract, timeline=None)
    assert report["valid"]
    assert any(check["check"] == "timeline_comparison" for check in report["omitted_checks"])
    issues = []
    teaching._validate_timeline(None, {}, "unavailable", lambda *args: issues.append(args))
    assert issues[0][:2] == ("timeline_shape", "timeline")
    with pytest.raises(TimelineError, match="JSON object"):
        parse_timeline(None)


@pytest.mark.parametrize("duration,accepted", [
    (2.001, True), (math.nextafter(2.001, math.inf), False),
    (math.nextafter(2.001, 0), True),
    (1.999, True), (math.nextafter(1.999, 0), False),
    (math.nextafter(1.999, math.inf), True),
])
def test_exact_arithmetic_boundary(timeline, contract, duration, accepted):
    timeline["blocks"][0]["duration"] = duration
    assert_conformance(timeline, contract, accepted)


@pytest.mark.parametrize("end,accepted", [
    (4.001, True), (math.nextafter(4.001, math.inf), False),
    (math.nextafter(4.001, 0), True),
])
def test_exact_block_scene_overrun_boundary(timeline, contract, end, accepted):
    timeline["blocks"][-1]["end"] = end
    del timeline["blocks"][-1]["duration"]
    assert_conformance(timeline, contract, accepted)


@pytest.mark.parametrize("start,accepted", [
    (1.999999, True), (math.nextafter(1.999999, 0), False),
    (math.nextafter(1.999999, math.inf), True), (2, True), (2.5, True),
])
def test_exact_overlap_boundary_and_gaps(timeline, contract, start, accepted):
    timeline["blocks"][1]["start"] = start
    del timeline["blocks"][1]["duration"]
    assert_conformance(timeline, contract, accepted)


@pytest.mark.parametrize("time,accepted", [
    (1.999999, True), (math.nextafter(1.999999, 0), False),
    (math.nextafter(1.999999, math.inf), True), (2, True), (3, True),
])
def test_exact_event_order_boundary(timeline, contract, time, accepted):
    timeline["events"].append({"time": time, "label": "next state"})
    assert_conformance(timeline, contract, accepted)


@pytest.mark.parametrize("time,accepted", [
    (0, True), (-math.ulp(0.0), False),
    (4, True), (math.nextafter(4, math.inf), False), (4.0005, False),
])
def test_event_scene_bounds_have_no_overrun_allowance(timeline, contract, time, accepted):
    timeline["events"][0]["time"] = time
    assert_conformance(timeline, contract, accepted)


def test_does_not_sort_or_renumber(timeline, contract):
    timeline["blocks"].reverse()
    assert_conformance(timeline, contract, False)
    for i, block in enumerate(timeline["blocks"]):
        block["index"] = i
    assert_conformance(timeline, contract, False)


def test_large_finite_timestamps_without_relative_tolerance(timeline, contract):
    timeline["scene_duration"] = 1e308
    timeline["blocks"][1].update(start=1e307, end=1e308)
    del timeline["blocks"][1]["duration"]
    assert_conformance(timeline, contract, True)
    timeline["blocks"][1].update(start=0, end=1e308, duration=1e308)
    # Ordering remains invalid even at large magnitudes.
    assert_conformance(timeline, contract, False)
    timeline["blocks"][1].update(start=2, end=1e308, duration=1e308)
    # The two-second discrepancy must not vanish in float subtraction.
    assert_conformance(timeline, contract, False)


@pytest.mark.parametrize("run_id,accepted", [
    (OMIT, False), (None, False), ("", False), ("different", False), ("run-conformance", True),
], ids=["missing", "null", "blank", "stale", "matched"])
def test_managed_run_binding_is_shared(timeline, run_id, accepted):
    replace(timeline, ("run_id",), run_id)
    for adapter, error in (
        (production.validate_timeline, production.RenderError),
        (frames.validate_timeline, frames.TimelineValidationError),
        (review.validate_timeline, review.ReviewError),
    ):
        if accepted:
            adapter(timeline, run_id="run-conformance")
        else:
            with pytest.raises(error, match="run_id"):
                adapter(timeline, run_id="run-conformance")


def test_public_shapes_legacy_omissions_and_payload_preservation(timeline, contract):
    for key in ("schema_version", "run_id"):
        del timeline[key]
    for block in timeline["blocks"]:
        del block["duration"]
    payload = timeline["events"][0]["data"]
    timeline["blocks"][0]["audio"] = [{"path": "immutable.wav", "sha256": "opaque"}]
    assert_conformance(timeline, contract, True)
    parsed = frames.validate_timeline(timeline)
    assert frames.Block is Block and frames.Event is Event and frames.Timeline is Timeline
    assert [field.name for field in fields(Timeline)] == ["scene_duration", "blocks", "run_id", "events"]
    assert parsed.blocks[0] == Block(0, 0.0, 2.0, 2.0, timeline["blocks"][0]["text"])
    assert parsed.events[0].data is payload
    assert Event(1, "legacy", "beat").data is None
    assert parsed.run_id is None
    assert "run_id" not in timeline and "duration" not in timeline["blocks"][0]


@pytest.mark.parametrize("payload", [None, False, 0, "state", ["x", 1], {"nested": {"a": [False]}}])
def test_event_data_is_opaque(timeline, contract, payload):
    timeline["events"][0]["data"] = payload
    assert_conformance(timeline, contract, True)
    assert parse_timeline(timeline).events[0].data is payload


@pytest.mark.parametrize("change,code", [
    ("text", "narration_drift"), ("beat", "beat_drift"), ("count", "timeline_count"),
    ("unknown-event-beat", "reference"), ("unknown-block-beat", "reference"),
    ("label", "event_drift"), ("data", "event_data_drift"), ("timing", "event_timing"),
])
def test_only_teaching_semantics_are_stricter(timeline, contract, change, code):
    bid = contract["beats"][0]["id"]
    timeline["blocks"][0]["beat_id"] = bid
    timeline["events"][0]["beat_id"] = bid
    contract["beats"][0]["events"] = [{"label": "state", "data": {"nested": [True, None, 7]}}]
    assert_conformance(timeline, contract, True)
    if change == "text":
        timeline["blocks"][0]["text"] = "Changed narration."
    elif change == "beat":
        timeline["blocks"][0]["beat_id"] = contract["beats"][1]["id"]
    elif change == "count":
        timeline["blocks"].pop()
    elif change == "unknown-event-beat":
        timeline["events"][0]["beat_id"] = "unknown"
    elif change == "unknown-block-beat":
        timeline["blocks"][0]["beat_id"] = "unknown"
    elif change == "label":
        timeline["events"][0]["label"] = "different"
    elif change == "data":
        timeline["events"][0]["data"]["nested"][2] = 8
    else:
        timeline["events"][0]["time"] = math.nextafter(2, math.inf)
    assert production.validate_timeline(timeline) is timeline
    assert frames.validate_timeline(timeline) == review.validate_timeline(timeline)
    report = teaching.validate_contract(contract, timeline=timeline)
    assert not report["valid"]
    assert code in {issue["code"] for issue in report["errors"]}


def test_pacing_is_still_a_warning(timeline, contract):
    contract["beats"][0]["duration_range"] = [3, 5]
    assert_conformance(timeline, contract, True)
    report = teaching.validate_contract(contract, timeline=timeline)
    assert "duration_review" in {issue["code"] for issue in report["warnings"]}
