"""Offline, version-one teaching contracts; no model calls or scene imports.

API:
    load_contract(path) -> dict
    loads_contract(text) -> dict
    validate_contract(contract, *, timeline=None, source_texts=None) -> dict
    evaluate_check(check) -> dict

``validate_contract`` is pure: source_texts is an optional source-ID -> text
mapping supplied by the caller. It never opens a source or executes its code.
Results contain JSON-serializable errors, review warnings and computed checks.
``omitted_checks`` explicitly lists missing source/timeline/event evidence and
partial narration coverage; missing evidence is never a passed check.
``valid`` means the supplied deterministic checks passed, NOT that research
claims are true, a movie is faithful, or a viewer understood it.

Schema v1 (see examples\\ddtree_full\\teaching.json):
* episode, audience, prerequisites[], objective, scope, assumptions[], unknowns[];
* sources[]: id, kind, ref, revision (or null + revision_note), inspection;
* claims[]: id, kind, statement, status (mapped/unresolved), evidence[] of
  {source, locator, support}; unresolved claims also need an explanation;
* worked_examples[]: id, description, provenance (toy/measured/derived),
  source_refs[], checks[]; each check has kind, input, expected;
* beats[]: stable id, purpose, claim_ids[], example_ids[], optional question,
  narration {index, text, source, locator}, duration_range, duration_explanation,
  events[] of {label, data?}. Indices are zero-based rendered block positions;
* transfer_questions[]: id, question, expected_answer, justification,
  claim_ids[], example_ids[]; author answers are not comprehension evidence.

``timeline_mapping`` is complete, partial, or unavailable; partial/unavailable
requires mapping_note. No timing/event mapping is invented for uninstrumented
scenes. Optional timeline blocks follow the repository's legacy or v1 format.
Text, index/order, event-data and mathematical drift are hard errors. Duration
ranges are review warnings, even when exceeded; explain rather than cut speech.
Source digests (optional sha256, UTF-8 with LF newlines) detect content drift,
not whether evidence entails a claim. No digest implies an explicit warning.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = 1
CHECK_KINDS = (
    "factorized_prefixes", "ancestry", "greedy_tree_walk", "serial_cost",
    "rounded_product", "probability_graphic",
)


def text_digest(text: str) -> str:
    """Hash text consistently across LF/CRLF checkouts, retaining other text."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def load_contract(path: str | Path) -> dict:
    """Load strict JSON, rejecting duplicate keys, non-finite values and arrays.

    File-system errors remain OSError; malformed documents raise ValueError.
    This loader also accepts timeline documents for use with the pure validator.
    """
    return loads_contract(Path(path).read_text(encoding="utf-8-sig"))


def loads_contract(text: str) -> dict:
    """Parse a strict JSON object without I/O; useful for hashing loaded bytes."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    def floating(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"Non-finite JSON number: {value}")
        return result

    result = json.loads(
        text,
        object_pairs_hook=pairs, parse_constant=constant, parse_float=floating,
    )
    if not isinstance(result, dict):
        raise ValueError("Document must be a JSON object")
    return result


def _number(value, *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Expected a finite decimal number")
    result = Decimal(str(value))
    if not result.is_finite() or result < minimum:
        raise ValueError(f"Expected a finite number >= {minimum}")
    return result


def _integer(value, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"Expected an integer >= {minimum}")
    return value


def _paths(value):
    if not isinstance(value, list) or not value:
        raise ValueError("Expected nonempty paths")
    paths = []
    for path in value:
        if not isinstance(path, list) or not all(_text(token) for token in path):
            raise ValueError("Paths must be token arrays, never joined display keys")
        paths.append(tuple(path))
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate path")
    if () not in paths or any(path[:-1] not in paths for path in paths if path):
        raise ValueError("Paths must include root and every parent")
    return paths


def _compute(kind, data):
    if kind == "factorized_prefixes":
        marginals = data["marginals"]
        if not isinstance(marginals, list) or not marginals:
            raise ValueError("Expected nonempty marginal distributions")
        distributions = []
        count = 0
        width = 1
        for marginal in marginals:
            if not isinstance(marginal, dict) or not marginal:
                raise ValueError("Expected a nonempty marginal object")
            if not all(_text(token) for token in marginal):
                raise ValueError("Tokens must be nonempty strings")
            values = {token: _number(p) for token, p in marginal.items()}
            if sum(values.values()) != 1:
                raise ValueError("Each marginal must sum exactly to one")
            distributions.append(values)
            width *= len(values)
            count += width
            if count > 10000:
                raise ValueError("Exhaustive oracle limited to 10000 toy prefixes")
        budget = _integer(data["budget"], minimum=1)
        if budget > count:
            raise ValueError("Budget exceeds the available prefix count")
        # Exhaustive Cartesian enumeration, deliberately not the production heap.
        ranked = []
        for depth in range(1, len(distributions) + 1):
            for path in itertools.product(*distributions[:depth]):
                mass = math.prod(distributions[i][word] for i, word in enumerate(path))
                ranked.append((path, mass))
        ranked.sort(key=lambda item: (-item[1], len(item[0]), item[0]))
        selected = ranked[:budget]
        return {
            "prefix_count": count,
            "selected": [list(path) for path, _ in selected],
            "masses": [mass for _, mass in selected],
            "total_mass": sum(mass for _, mass in selected),
        }
    if kind == "ancestry":
        paths = _paths(data["paths"])
        offset = _integer(data.get("position_offset", 0))
        return {
            "visibility": [
                [int(row[:len(column)] == column) for column in paths]
                for row in paths
            ],
            "position_ids": [offset + len(path) for path in paths],
        }
    if kind == "greedy_tree_walk":
        paths = _paths(data["paths"])
        decisions = {}
        for decision in data["decisions"]:
            if not isinstance(decision["prefix"], list) or not all(_text(t) for t in decision["prefix"]):
                raise ValueError("Decision prefix must be a token array")
            prefix = tuple(decision["prefix"])
            if prefix not in paths or prefix in decisions or not _text(decision["token"]):
                raise ValueError("Decision must name a unique tree prefix and token")
            decisions[prefix] = decision["token"]
        current = ()
        matched = []
        while current in decisions:
            token = decisions[current]
            if (*current, token) not in paths:
                return {"matched": matched, "emitted": [*matched, token], "next_anchor": token}
            matched.append(token)
            current = (*current, token)
        raise ValueError("Target decisions must cover the walk through its first miss")
    if kind == "serial_cost":
        count = _integer(data["token_count"], minimum=1)
        costs = [_number(data[name]) for name in ("target_pass", "draft_step", "verification")]
        if any(value <= 0 for value in costs):
            raise ValueError("Illustrative work durations must be positive")
        target, draft, verification = costs
        return {
            "baseline_end": count * target,
            "draft_end": count * draft,
            "speculative_end": count * draft + verification,
        }
    if kind == "rounded_product":
        if not isinstance(data["factors"], list) or not data["factors"]:
            raise ValueError("Expected at least one factor")
        product = math.prod(_number(value) for value in data["factors"])
        displayed = _number(data["displayed"])
        relation = data["relation"]
        places = _integer(data["decimal_places"])
        if places > 20:
            raise ValueError("At most 20 display decimal places")
        if relation not in ("=", "approximately"):
            raise ValueError("Relation must be = or approximately")
        if relation == "=" and product != displayed:
            raise ValueError("False equality: rounded output requires approximately")
        if relation == "approximately" and abs(product - displayed) > Decimal(5).scaleb(-places - 1):
            raise ValueError("Displayed approximation exceeds the stated precision")
        return {"exact_product": product}
    if kind == "probability_graphic":
        probability = _number(data["probability"])
        fill = _number(data["fill_fraction"])
        if probability > 1 or fill > 1 or fill != probability:
            raise ValueError("Probability fill must represent mass, including exactly zero")
        return {"fill_fraction": probability}
    raise ValueError(f"Unknown check kind: {kind}")


def _equivalent(actual, expected):
    if isinstance(actual, dict):
        return (
            isinstance(expected, dict) and actual.keys() == expected.keys()
            and all(_equivalent(value, expected[key]) for key, value in actual.items())
        )
    if isinstance(actual, list):
        return (
            isinstance(expected, list) and len(actual) == len(expected)
            and all(_equivalent(a, b) for a, b in zip(actual, expected))
        )
    if type(actual) is int:
        return type(expected) is int and actual == expected
    if isinstance(actual, Decimal):
        try:
            return actual == _number(expected)
        except (ValueError, ArithmeticError):
            return False
    return type(actual) is type(expected) and actual == expected


def evaluate_check(check: Mapping[str, Any]) -> dict:
    """Evaluate one bounded independent toy oracle, with no production imports.

    Ties in exhaustive prefix enumeration use shorter paths then lexical tokens;
    this is an oracle convention, not a claim about an implementation's tie order.
    Expected output must be complete, so an empty object cannot pass vacuously.
    """
    actual = None
    kind = check.get("kind") if isinstance(check, dict) else None
    if not isinstance(kind, str):
        return {"passed": False, "kind": None, "actual": None, "message": "Check kind must be a string"}
    try:
        if not isinstance(check, dict) or not isinstance(check.get("input"), dict):
            raise ValueError("Check requires kind, input object and expected object")
        actual = _compute(check["kind"], check["input"])
        if not _equivalent(actual, check["expected"]):
            raise ValueError("Expected state disagrees with independent calculation")
        return {"passed": True, "kind": kind, "actual": json.loads(json.dumps(actual, default=str))}
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        return {"passed": False, "kind": kind,
                "actual": json.loads(json.dumps(actual, default=str)), "message": str(exc)}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_contract(contract: Any, *, timeline=None, source_texts=None) -> dict:
    """Validate shape, references and supplied evidence; never certify learning."""
    errors, warnings, checks, omitted_checks = [], [], [], []

    def issue(code, path, message, *, warning=False):
        (warnings if warning else errors).append({"code": code, "path": path, "message": message})

    def require_text(obj, key, path):
        if not _text(obj.get(key)):
            issue("shape", f"{path}.{key}", "Expected a nonempty string")

    def strings(obj, key, path, *, empty=False):
        value = obj.get(key)
        if not isinstance(value, list) or (not value and not empty) or not all(_text(x) for x in value):
            issue("shape", f"{path}.{key}", "Expected an array of nonempty strings")
            return []
        return value

    def records(key, *, empty=False):
        value = contract.get(key)
        if not isinstance(value, list) or (not value and not empty):
            issue("shape", key, "Expected a nonempty object array" if not empty else "Expected an object array")
            return {}
        result = {}
        for i, obj in enumerate(value):
            path = f"{key}[{i}]"
            if not isinstance(obj, dict) or not _text(obj.get("id")):
                issue("shape", path, "Expected an object with nonempty id")
            elif obj["id"] in result:
                issue("duplicate_id", path, f"Duplicate id {obj['id']}")
            else:
                result[obj["id"]] = obj
        return result

    def refs(obj, key, known, path, *, empty=False):
        for ref in strings(obj, key, path, empty=empty):
            if ref not in known:
                issue("reference", f"{path}.{key}", f"Unknown reference: {ref}")

    def result():
        return {
            "schema_version": SCHEMA_VERSION, "valid": not errors,
            "errors": errors, "warnings": warnings, "checks": checks,
            "omitted_checks": omitted_checks,
            "evidence": {
                "source_content": "supplied" if source_texts is not None else "not_checked",
                "timeline": "supplied" if timeline is not None else "not_checked",
                "claim_entailment": "human_review_required",
                "audiovisual_fidelity": "not_assessed",
                "human_comprehension": "not_assessed",
                "production_acceptance": "not_assessed",
            },
        }

    if not isinstance(contract, dict):
        issue("shape", "$", "Contract must be an object")
        return result()
    try:
        json.dumps(contract, allow_nan=False)
    except (TypeError, ValueError):
        issue("shape", "$", "Contract must contain only finite JSON values")
        return result()
    if type(contract.get("schema_version")) is not int or contract["schema_version"] != SCHEMA_VERSION:
        issue("schema_version", "schema_version", "Expected schema_version 1")
    for key in ("episode", "audience", "objective", "scope"):
        require_text(contract, key, "$")
    for key in ("prerequisites", "assumptions", "unknowns"):
        strings(contract, key, "$", empty=key == "unknowns")
    for unknown in contract.get("unknowns", []) if isinstance(contract.get("unknowns"), list) else []:
        if _text(unknown):
            issue("declared_unknown", "unknowns", unknown, warning=True)
    sources = records("sources")
    claims = records("claims")
    examples = records("worked_examples")
    beats = records("beats", empty=True)
    questions = records("transfer_questions")
    if timeline is None:
        omitted_checks.append({"check": "timeline_comparison", "reason": "No timeline supplied"})
    if not 1 <= len(questions) <= 2:
        issue("question_count", "transfer_questions", "Provide one or two transfer questions")
    for sid, source in sources.items():
        path = f"sources.{sid}"
        for key in ("kind", "ref", "inspection"):
            require_text(source, key, path)
        if source.get("kind") not in ("implementation", "paper", "toy", "measurement", "documentation"):
            issue("source_kind", path, "Unsupported source kind")
        if source.get("inspection") not in ("inspected", "unverified"):
            issue("source_inspection", path, "Use inspected or unverified")
        if source.get("inspection") == "unverified":
            issue("unverified_source", path, "Source has not been independently inspected", warning=True)
        if not _text(source.get("revision")):
            require_text(source, "revision_note", path)
            issue("unpinned_source", path, "Revision unknown; inspect before relying on this reference", warning=True)
        digest = source.get("sha256")
        if digest is not None and (
            not isinstance(digest, str) or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            issue("shape", f"{path}.sha256", "Expected lowercase SHA-256")
        if not isinstance(source_texts, Mapping) or sid not in source_texts:
            omitted_checks.append({"check": "source_content", "source": sid, "reason": "No source text supplied"})
        elif not digest:
            omitted_checks.append({"check": "source_content", "source": sid, "reason": "No pinned content digest"})
        if source_texts is not None:
            if not isinstance(source_texts, Mapping) or sid not in source_texts:
                issue("source_unavailable", path, "No text supplied for this source", warning=True)
            elif not isinstance(source_texts[sid], str):
                issue("shape", path, "Source text must be a string")
            elif not digest:
                issue("source_unhashed", path, "No digest: supplied content is not revision-checked", warning=True)
            elif text_digest(source_texts[sid]) != digest:
                issue("source_drift", path, "Source text differs from the contracted revision")
    for cid, claim in claims.items():
        path = f"claims.{cid}"
        require_text(claim, "statement", path)
        if claim.get("kind") not in ("mechanism", "toy", "empirical", "scope"):
            issue("claim_kind", path, "Use mechanism, toy, empirical, or scope")
        status = claim.get("status")
        if status not in ("mapped", "unresolved"):
            issue("claim_status", path, "Use mapped or unresolved; neither is automatic proof")
        if status == "unresolved":
            require_text(claim, "explanation", path)
            issue("unresolved_claim", path, str(claim.get("explanation", "")), warning=True)
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or (not evidence and status != "unresolved"):
            issue("unsupported_claim", path, "Mapped claim requires nonempty evidence")
            continue
        for i, support in enumerate(evidence):
            ep = f"{path}.evidence[{i}]"
            if not isinstance(support, dict):
                issue("shape", ep, "Expected source, locator and support object")
                continue
            for key in ("source", "locator", "support"):
                require_text(support, key, ep)
            source = sources.get(support.get("source")) if isinstance(support.get("source"), str) else None
            if source is None:
                issue("reference", ep, "Evidence references an unknown source")
            elif status == "mapped":
                if source.get("inspection") != "inspected":
                    issue("unsupported_claim", ep, "Uninspected source cannot support a mapped claim")
                if claim.get("kind") == "empirical" and source.get("kind") != "measurement":
                    issue("unsupported_claim", ep, "Toy values or mechanism prose are not measured evidence")
                if claim.get("kind") == "mechanism" and source.get("kind") == "toy":
                    issue("unsupported_claim", ep, "Toy example alone cannot support a general mechanism")
    for eid, example in examples.items():
        path = f"worked_examples.{eid}"
        require_text(example, "description", path)
        if example.get("provenance") not in ("toy", "measured", "derived"):
            issue("provenance", path, "Label values toy, measured, or derived")
        refs(example, "source_refs", sources, path)
        source_refs = example.get("source_refs")
        if example.get("provenance") == "measured" and not any(
            sources.get(ref, {}).get("kind") == "measurement"
            for ref in (source_refs if isinstance(source_refs, list) else []) if isinstance(ref, str)
        ):
            issue("provenance", path, "Measured examples require a measurement source")
        sample_checks = example.get("checks")
        if not isinstance(sample_checks, list) or not sample_checks:
            issue("unchecked_example", path, "Example needs at least one independent check")
            continue
        for i, check in enumerate(sample_checks):
            check_result = evaluate_check(check)
            checks.append({"path": f"{path}.checks[{i}]", **check_result})
            if not check_result["passed"]:
                issue("semantic_check", f"{path}.checks[{i}]", check_result["message"])
    mapping = contract.get("timeline_mapping")
    if mapping not in ("complete", "partial", "unavailable"):
        issue("timeline_mapping", "timeline_mapping", "Use complete, partial, or unavailable")
    if mapping != "complete":
        require_text(contract, "mapping_note", "$")
        issue("incomplete_mapping", "timeline_mapping", str(contract.get("mapping_note", "")), warning=True)
        omitted_checks.append({"check": "complete_narration_coverage", "reason": str(contract.get("mapping_note", ""))})
    if not any(isinstance(beat.get("events"), list) and beat["events"] for beat in beats.values()):
        omitted_checks.append({"check": "visual_event_comparison", "reason": "No expected visual events are mapped"})
    indices = []
    for bid, beat in beats.items():
        path = f"beats.{bid}"
        require_text(beat, "purpose", path)
        refs(beat, "claim_ids", claims, path)
        refs(beat, "example_ids", examples, path, empty=True)
        if "question" in beat:
            require_text(beat, "question", path)
        narration = beat.get("narration")
        if narration is None:
            if mapping == "complete":
                issue("narration_mapping", path, "Complete mapping requires narration on every beat")
        elif not isinstance(narration, dict):
            issue("shape", f"{path}.narration", "Expected a narration object")
        else:
            for key in ("text", "source", "locator"):
                require_text(narration, key, f"{path}.narration")
            index = narration.get("index")
            if type(index) is not int or index < 0:
                issue("shape", f"{path}.narration.index", "Expected a nonnegative integer")
            else:
                indices.append(index)
            if not isinstance(narration.get("source"), str) or narration["source"] not in sources:
                issue("reference", f"{path}.narration", "Unknown narration source")
        duration = beat.get("duration_range")
        if duration is not None and not (
            isinstance(duration, list) and len(duration) == 2
            and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in duration)
            and duration[0] <= duration[1]
        ):
            issue("shape", f"{path}.duration_range", "Expected ordered positive finite [min, max]")
        events = beat.get("events", [])
        if not isinstance(events, list):
            issue("shape", f"{path}.events", "Expected an event array")
        else:
            labels = set()
            for event in events:
                if not isinstance(event, dict) or not _text(event.get("label")):
                    issue("shape", f"{path}.events", "Event must have a nonempty label")
                elif event["label"] in labels:
                    issue("duplicate_id", f"{path}.events", "Event labels must be unique within a beat")
                else:
                    labels.add(event["label"])
    if indices != sorted(set(indices)):
        issue("beat_order", "beats", "Narration indices must be unique and in order")
    if mapping == "complete" and (not indices or indices != list(range(len(beats)))):
        issue("narration_mapping", "beats", "Complete mapping requires contiguous indices from zero")
    for qid, question in questions.items():
        path = f"transfer_questions.{qid}"
        for key in ("question", "expected_answer", "justification"):
            require_text(question, key, path)
        refs(question, "claim_ids", claims, path)
        refs(question, "example_ids", examples, path)
    if timeline is not None and not errors:
        _validate_timeline(timeline, beats, mapping, issue)
    elif timeline is not None:
        omitted_checks.append({"check": "timeline_comparison", "reason": "Skipped because contract validation has hard errors"})
    return result()


def _validate_timeline(timeline, beats, mapping, issue):
    if not isinstance(timeline, dict) or not isinstance(timeline.get("blocks"), list):
        issue("timeline_shape", "timeline", "Expected timeline object with blocks array")
        return
    if "schema_version" in timeline and (
        type(timeline["schema_version"]) is not int or timeline["schema_version"] != 1
    ):
        issue("timeline_shape", "timeline.schema_version", "Unsupported timeline version")
    if "run_id" in timeline and not _text(timeline["run_id"]):
        issue("timeline_shape", "timeline.run_id", "When supplied, run_id must be a nonempty string")
    duration = timeline.get("scene_duration")
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        issue("timeline_shape", "timeline.scene_duration", "Expected finite nonnegative scene duration")
        return
    blocks = timeline["blocks"]
    if mapping == "complete" and len(blocks) != len(beats):
        issue("timeline_count", "timeline.blocks", "Block count differs from the complete beat mapping")
    last_end = 0
    for i, block in enumerate(blocks):
        path = f"timeline.blocks[{i}]"
        if not isinstance(block, dict):
            issue("timeline_shape", path, "Expected block object")
            continue
        if type(block.get("index")) is not int or block["index"] != i:
            issue("timeline_order", path, "Index must match the block's rendered order")
        if not _text(block.get("text")):
            issue("timeline_shape", path, "Narration text must be nonempty")
        values = [block.get(key) for key in ("start", "end", "duration")]
        if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values):
            issue("timeline_shape", path, "Expected finite nonnegative timestamps")
            continue
        start, end, block_duration = values
        if end < start or start < last_end - 1e-6 or end > duration + 1e-6:
            issue("timeline_order", path, "Blocks must be ordered, nonoverlapping and within scene duration")
        if not math.isclose(end - start, block_duration, abs_tol=1e-6):
            issue("timeline_duration", path, "Duration differs from end minus start")
        last_end = end
    events = timeline.get("events", [])
    if not isinstance(events, list):
        issue("timeline_shape", "timeline.events", "Expected events array")
        events = []
    valid_events = []
    last_time = 0
    for i, event in enumerate(events):
        if not isinstance(event, dict) or not _text(event.get("label")):
            issue("timeline_shape", f"timeline.events[{i}]", "Expected labeled event")
            continue
        time = event.get("time")
        if type(time) not in (int, float) or not math.isfinite(time) or not last_time <= time <= duration:
            issue("timeline_order", f"timeline.events[{i}]", "Events must be ordered and within the scene")
            continue
        last_time = time
        if "beat_id" in event and (
            not isinstance(event["beat_id"], str) or event["beat_id"] not in beats
        ):
            issue("reference", f"timeline.events[{i}]", "Unknown event beat_id")
        valid_events.append(event)
    for bid, beat in beats.items():
        narration = beat.get("narration")
        if not narration:
            continue
        index = narration["index"]
        if index >= len(blocks) or not isinstance(blocks[index], dict):
            issue("timeline_missing", f"beats.{bid}", "Mapped narration block is absent")
            continue
        block = blocks[index]
        if block.get("text") != narration["text"]:
            issue("narration_drift", f"beats.{bid}", "Narration text differs; review and remap, do not silently accept")
        if "beat_id" in block and block["beat_id"] != bid:
            issue("beat_drift", f"beats.{bid}", "Timeline beat_id disagrees with mapped order")
        bounds = beat.get("duration_range")
        actual_duration = block.get("duration")
        if bounds and type(actual_duration) in (int, float) and not bounds[0] <= actual_duration <= bounds[1]:
            explanation = beat.get("duration_explanation")
            issue(
                "duration_review", f"beats.{bid}",
                f"Duration {actual_duration} is outside {bounds}. "
                + (f"Explanation: {explanation}" if _text(explanation) else "Explain pacing in review; do not force narration cuts."),
                warning=True,
            )
        actual_events = [event for event in valid_events if event.get("beat_id") == bid]
        expected_events = beat.get("events", [])
        if expected_events and [e["label"] for e in actual_events] != [e["label"] for e in expected_events]:
            issue("event_drift", f"beats.{bid}.events", "Mapped event labels/order differ or are missing")
        for actual, expected in zip(actual_events, expected_events):
            if "data" in expected and not _equivalent(actual.get("data"), expected["data"]):
                issue("event_data_drift", f"beats.{bid}.events", "Event data differs from the contracted state")
        for event in actual_events:
            if all(type(block.get(key)) in (int, float) for key in ("start", "end")):
                if not block["start"] <= event["time"] <= block["end"]:
                    issue("event_timing", f"beats.{bid}.events", "Event lies outside its narration block")
