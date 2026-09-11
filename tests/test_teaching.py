"""Offline contracts and independent semantic oracles, not render acceptance.

Core checks avoid scene/provider imports. Static narration mappings inspect
current source literals, not runtime execution. Canonical event integration
tests add silent dry renders and inspect state at each recorded transition.
"""

import ast
import copy
from fractions import Fraction
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("teaching_under_test", ROOT / "manim_lib" / "teaching.py")
teaching = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(teaching)
CORPUS = teaching.load_contract(ROOT / "tests" / "fixtures" / "teaching" / "regressions.json")
EPISODES = (
    "ddtree_full", "dflash_visual", "ddtree_visual", "ddtree_dflash",
    "speculative_decoding_timeline", "speculative_decoding_flow",
)


def contract(episode="ddtree_full"):
    return teaching.load_contract(ROOT / "examples" / episode / "teaching.json")


def timeline_for(document):
    """Synthetic fixture for validator unit tests, never production evidence."""
    blocks = []
    events = []
    for beat in document["beats"]:
        narration = beat.get("narration")
        if narration is None:
            continue
        start = len(blocks) * 5
        blocks.append({
            "index": narration["index"], "start": start, "end": start + 5,
            "duration": 5, "text": narration["text"],
        })
        expected_events = beat.get("events", [])
        for i, event in enumerate(expected_events):
            events.append({
                "time": start + 5 * (i + 1) / (len(expected_events) + 1),
                "label": event["label"], "beat_id": beat["id"],
                **({"data": event["data"]} if "data" in event else {}),
            })
    return {"scene_duration": len(blocks) * 5, "blocks": blocks, "events": events}


def codes(report, level="errors"):
    return {issue["code"] for issue in report[level]}


@pytest.fixture
def scratch():
    path = ROOT / "tests" / f".teaching-test-{uuid.uuid4().hex}.json"
    yield path
    path.unlink(missing_ok=True)


@pytest.mark.parametrize("episode", EPISODES)
def test_public_contracts_validate_without_certifying_comprehension(episode):
    report = teaching.validate_contract(contract(episode))
    assert report["valid"], report["errors"]
    assert report["checks"] and all(check["passed"] for check in report["checks"])
    assert report["evidence"]["human_comprehension"] == "not_assessed"
    assert report["evidence"]["production_acceptance"] == "not_assessed"
    assert report["evidence"]["claim_entailment"] == "human_review_required"
    omitted = {check["check"] for check in report["omitted_checks"]}
    assert {"timeline_comparison", "source_content"} <= omitted
    assert ("visual_event_comparison" in omitted) == (not any(beat.get("events") for beat in contract(episode)["beats"]))
    json.dumps(report, allow_nan=False)


def current_source(source):
    """Read the current local source and fail on drift; never substitute history."""
    try:
        text = (ROOT / source["ref"]).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise AssertionError(
            f"Cannot read current source {source['ref']}: {error}. "
            "Restore readable UTF-8 source or correct its teaching.json reference."
        ) from error
    digest = teaching.text_digest(text)
    assert digest == source["sha256"], (
        f"Current source drift for {source['ref']}: expected SHA-256 {source['sha256']}, got {digest}. "
        "Review the current file and update its teaching.json source digest and affected "
        "expectations only if the change is intentional."
    )
    return text


@pytest.fixture
def forbid_source_subprocesses(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Current-source checks must not run Git or other subprocesses")

    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.mark.parametrize("change", ["\n# current source changed\n", "\ndef invalid("],
                         ids=["valid-python-drift", "invalid-python-drift"])
def test_combined_episode_mapping_rejects_current_scene_drift(monkeypatch, forbid_source_subprocesses, change):
    source = next(s for s in contract("ddtree_dflash")["sources"] if s["id"] == "scene")
    path = ROOT / source["ref"]
    read_text = Path.read_text
    changed = read_text(path, encoding="utf-8") + change

    def read_changed(current_path, *args, **kwargs):
        return changed if current_path == path else read_text(current_path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_changed)
    with pytest.raises(AssertionError, match="Current source drift") as error:
        test_combined_episode_maps_current_source_narration_including_loop_selections()
    message = str(error.value)
    assert source["ref"] in message
    assert source["sha256"] in message
    assert teaching.text_digest(changed) in message
    assert "Review the current file" in message


@pytest.mark.parametrize("episode", EPISODES)
@pytest.mark.parametrize("failure", [
    FileNotFoundError("file missing"),
    PermissionError("read denied"),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid UTF-8"),
], ids=["missing", "permission-denied", "invalid-utf8"])
def test_current_source_rejects_unreadable_files(monkeypatch, forbid_source_subprocesses, episode, failure):
    source = next(s for s in contract(episode)["sources"] if "://" not in s["ref"])
    path = ROOT / source["ref"]
    read_text = Path.read_text

    def read_unavailable(current_path, *args, **kwargs):
        if current_path == path:
            raise failure
        return read_text(current_path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_unavailable)
    with pytest.raises(AssertionError, match="Cannot read current source") as error:
        test_current_local_sources_match_contract(episode, forbid_source_subprocesses)
    assert source["ref"] in str(error.value)
    assert "Restore readable UTF-8 source" in str(error.value)
    assert error.value.__cause__ is failure


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_current_source_accepts_checkout_line_endings(monkeypatch, forbid_source_subprocesses, newline):
    source = next(s for s in contract("ddtree_dflash")["sources"] if s["id"] == "scene")
    path = ROOT / source["ref"]
    read_text = Path.read_text
    text = read_text(path, encoding="utf-8").replace("\r\n", "\n").replace("\n", newline)

    def read_normalized(current_path, *args, **kwargs):
        return text if current_path == path else read_text(current_path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_normalized)
    assert current_source(source) == text


def literal_assignment(path_or_text, name):
    module = ast.parse(path_or_text.read_text(encoding="utf-8") if isinstance(path_or_text, Path) else path_or_text)
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
    raise AssertionError(f"Missing literal assignment {name}")


@pytest.mark.parametrize("episode", ("ddtree_full", "dflash_visual", "ddtree_visual", "speculative_decoding_timeline"))
def test_current_source_narration_literals_match_contract(episode):
    document = contract(episode)
    for beat in document["beats"]:
        narration = beat["narration"]
        source = next(s for s in document["sources"] if s["id"] == narration["source"])
        text_source = current_source(source)
        if narration["locator"].startswith("BEATS["):
            call = literal_assignment(text_source, "BEATS").elts[narration["index"]]
            text = next((kw.value for kw in call.keywords if kw.arg == "narration"), None)
            if text is None:
                text = call.args[2]
        else:
            text = literal_assignment(text_source, "NARRATION").elts[narration["index"]]
        assert ast.literal_eval(text) == narration["text"]


@pytest.mark.parametrize("episode", ("dflash_visual", "ddtree_visual", "ddtree_dflash"))
def test_episode_contracts_bind_current_sources_without_legacy_exclusions(episode):
    document = contract(episode)
    texts = {s["id"]: current_source(s) for s in document["sources"] if "://" not in s["ref"]}
    report = teaching.validate_contract(document, source_texts=texts, timeline=timeline_for(document))
    assert report["valid"], report["errors"]
    assert document["timeline_mapping"] == "complete"
    assert "incomplete_mapping" not in codes(report, "warnings")
    assert not any(check["check"] == "complete_narration_coverage" for check in report["omitted_checks"])


def test_repaired_dflash_target_conditionals_and_greedy_output_are_independently_checked():
    document = contract("dflash_visual")
    source = next(s for s in document["sources"] if s["id"] == "storyboard")
    actual = ast.literal_eval(literal_assignment(current_source(source), "TARGET_CONDITIONALS"))
    check = document["worked_examples"][1]["checks"][0]
    supplied = {tuple(row["prefix"]): {k: Fraction(v) for k, v in row["distribution"].items()}
                for row in check["input"]["conditionals"]}
    assert supplied == {prefix: {k: Fraction(str(v)) for k, v in values.items()} for prefix, values in actual.items()}
    assert len(document["beats"]) == 12
    target_only_prefix = []
    for _ in range(2):
        probabilities = supplied[tuple(target_only_prefix)]
        target_only_prefix.append(max(probabilities, key=probabilities.get))
    result = teaching.evaluate_check(check)
    assert result["passed"]
    assert result["actual"]["emitted"] == target_only_prefix == ["the", "system"]
    assert result["actual"]["matched"] == ["the"]
    assert max(supplied[("the", "model")], key=supplied[("the", "model")].get) == "works"
    assert "works" not in result["actual"]["emitted"]


def test_combined_episode_maps_current_source_narration_including_loop_selections():
    document = contract("ddtree_dflash")
    source = next(s for s in document["sources"] if s["id"] == "scene")
    module = ast.parse(current_source(source))
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "DDTreeDFlashExplainer")
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    order = [node.value.func.attr for node in methods["construct"].body
             if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
             and isinstance(node.value.func, ast.Attribute)]
    assert order[-1] == "_finalize"
    texts = []
    for name in order[:-1]:
        method = methods[name]
        calls = sorted(
            (n for n in ast.walk(method) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "narrate"),
            key=lambda n: n.lineno,
        )
        if name == "best_first_example":
            selection_texts = next(
                ast.literal_eval(n.value) for n in ast.walk(method)
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "narration" for t in n.targets)
            )
            texts.extend([ast.literal_eval(calls[0].args[0]), *selection_texts.values(),
                          ast.literal_eval(calls[-1].args[0])])
        else:
            texts.extend(ast.literal_eval(call.args[0]) for call in calls)
    assert len(texts) == len(document["beats"]) == 30
    assert texts == [beat["narration"]["text"] for beat in document["beats"]]


def test_flow_current_source_maps_block_drafting_and_latency_qualifiers():
    document = contract("speculative_decoding_flow")
    source = next(s for s in document["sources"] if s["id"] == "scene")
    module = ast.parse(current_source(source))
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "SpeculativeDecodingFlow")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "construct")
    words = next(ast.literal_eval(n.value) for n in ast.walk(method)
                 if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "token_words" for t in n.targets))
    calls = sorted((n for n in ast.walk(method) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == "narrate"), key=lambda n: n.lineno)
    texts = []
    for call in calls:
        value = call.args[0]
        if isinstance(value, ast.JoinedStr):
            for index, word in enumerate(words, start=1):
                fields = {"index": index, "word": word}
                texts.append("".join(part.value if isinstance(part, ast.Constant) else str(fields[part.value.id])
                                     for part in value.values))
        else:
            texts.append(ast.literal_eval(value))
    assert texts == [beat["narration"]["text"] for beat in document["beats"]]
    assert len(texts) == 8
    report = teaching.validate_contract(document, timeline=timeline_for(document))
    assert report["valid"]
    assert "unresolved_claim" not in codes(report, "warnings")
    assert not any(check["check"] == "claim_support" for check in report["omitted_checks"])
    assert "block drafting" in texts[4]
    assert "not a guaranteed latency reduction" in texts[7]
    assert report["evidence"]["production_acceptance"] == "not_assessed"


def test_unresolved_claim_support_is_omitted_not_counted_as_passed():
    document = contract()
    claim = document["claims"][0]
    claim.update({"status": "unresolved", "evidence": [], "explanation": "Independent support is unavailable in this fixture."})
    report = teaching.validate_contract(document)
    assert report["valid"]
    assert "unresolved_claim" in codes(report, "warnings")
    assert any(check["check"] == "claim_support" and check["claim"] == claim["id"]
               for check in report["omitted_checks"])


def test_block_draft_cost_is_one_explicit_nonzero_pass():
    document = contract("speculative_decoding_flow")
    check = document["worked_examples"][0]["checks"][0]
    assert check["input"]["draft_steps"] == 1
    assert check["input"]["token_count"] == 3
    report = teaching.evaluate_check(check)
    assert report["passed"]
    assert Fraction(report["actual"]["draft_end"]) == Fraction("2.4")
    assert Fraction(report["actual"]["speculative_end"]) == Fraction("3.4")
    check["input"]["draft_steps"] = 0
    assert not teaching.evaluate_check(check)["passed"]


def test_partial_mapping_is_explicitly_omitted_not_counted_as_passed():
    document = contract()
    timeline = timeline_for(document)
    timeline["events"] = []
    document["timeline_mapping"] = "partial"
    document["mapping_note"] = "Only the opening two blocks are mapped in this coverage fixture."
    document["beats"] = document["beats"][:2]
    report = teaching.validate_contract(document, timeline=timeline)
    assert report["valid"]
    assert "incomplete_mapping" in codes(report, "warnings")
    assert any(check["check"] == "complete_narration_coverage" for check in report["omitted_checks"])


@pytest.mark.parametrize("episode", EPISODES)
def test_current_local_sources_match_contract(episode, forbid_source_subprocesses):
    document = contract(episode)
    texts = {s["id"]: current_source(s) for s in document["sources"] if "://" not in s["ref"]}
    report = teaching.validate_contract(document, source_texts=texts)
    assert report["valid"], report["errors"]
    assert report["evidence"]["source_content"] == "supplied"
    assert "source_unavailable" in codes(report, "warnings")
    omitted_sources = {check.get("source") for check in report["omitted_checks"] if check["check"] == "source_content"}
    assert not omitted_sources.intersection(texts)


def test_39_prefix_oracle_agrees_with_independent_full_outcome_expectation():
    document = contract()
    check = document["worked_examples"][0]["checks"][0]
    result = teaching.evaluate_check(check)
    marginals = [{token: Fraction(p) for token, p in q.items()} for q in check["input"]["marginals"]]
    selected = {tuple(path) for path in result["actual"]["selected"]}
    expectation = Fraction(0)
    for outcome in itertools.product(*marginals):
        probability = Fraction(1)
        for i, token in enumerate(outcome):
            probability *= marginals[i][token]
        matched_depth = max((i for i in range(1, len(outcome) + 1) if outcome[:i] in selected), default=0)
        expectation += probability * matched_depth
    assert result["actual"]["prefix_count"] == sum(3 ** depth for depth in range(1, 4))
    assert expectation == Fraction("1.8858")
    assert expectation == Fraction(result["actual"]["total_mass"])
    assert all(path[:-1] in selected for path in selected if len(path) > 1)


def test_oracle_not_just_canonical_constants():
    check = {
        "kind": "factorized_prefixes",
        "input": {"marginals": [{"x": "0.6", "y": "0.4"}, {"u": "0.9", "v": "0.1"}], "budget": 3},
        "expected": {"prefix_count": 6, "selected": [["x"], ["x", "u"], ["y"]],
                     "masses": ["0.6", "0.54", "0.4"], "total_mass": "1.54"},
    }
    assert teaching.evaluate_check(check)["passed"]


def test_ancestry_uses_prefix_identity_not_words_or_flat_indices():
    check = {
        "kind": "ancestry",
        "input": {"paths": [[], ["a"], ["b"], ["a", "model"], ["b", "model"]], "position_offset": 17},
        "expected": {"visibility": [[1,0,0,0,0], [1,1,0,0,0], [1,0,1,0,0],
                                   [1,1,0,1,0], [1,0,1,0,1]],
                     "position_ids": [17,18,18,19,19]},
    }
    assert teaching.evaluate_check(check)["passed"]
    check["expected"]["visibility"][4][3] = 1
    assert not teaching.evaluate_check(check)["passed"]


def test_numeric_token_identity_is_not_numeric_value():
    check = {"kind": "greedy_tree_walk",
             "input": {"paths": [[]], "decisions": [{"prefix": [], "token": "007"}]},
             "expected": {"matched": [], "emitted": ["7"], "next_anchor": "7"}}
    assert not teaching.evaluate_check(check)["passed"]


@pytest.mark.parametrize("case", CORPUS["checks"], ids=lambda case: case["id"])
def test_real_regression_checks(case):
    report = teaching.evaluate_check(case["check"])
    assert report["passed"] is case["passed"]
    if not case["passed"]:
        assert case["message"] in report["message"]


@pytest.mark.parametrize("case", CORPUS["contract_cases"], ids=lambda case: case["id"])
def test_evidence_regression_corpus(case):
    document = contract(case["episode"])
    claim = next(item for item in document["claims"] if item["id"] == case["claim_id"])
    claim[case["field"]] = case["value"]
    report = teaching.validate_contract(document)
    assert not report["valid"]
    assert case["error"] in codes(report)


def test_timeline_rubric_corpus_warns_and_requires_explanation_not_cuts():
    case = CORPUS["timeline_case"]
    document = contract(case["episode"])
    timeline = timeline_for(document)
    block = timeline["blocks"][case["block_index"]]
    block["duration"] = case["duration"]
    block["end"] = block["start"] + case["duration"]
    timeline["scene_duration"] = block["end"]
    report = teaching.validate_contract(document, timeline=timeline)
    assert report["valid"] is case["expected_valid"]
    assert case["warning"] in codes(report, "warnings")
    warning = next(w for w in report["warnings"] if w["path"] == "beats.earlier-same-prefix")
    assert "Explain pacing" in warning["message"]
    document["beats"][-1]["duration_explanation"] = "Allow a pause to inspect the common completion boundary."
    explained = teaching.validate_contract(document, timeline=timeline)
    assert explained["valid"]
    assert any("Explanation:" in w["message"] for w in explained["warnings"])
    assert explained["checks"] == report["checks"]


@pytest.mark.parametrize("change,code", [
    ("text", "narration_drift"), ("order", "timeline_order"),
    ("beat_id", "beat_drift"), ("missing", "timeline_count"),
    ("duration", "timeline_duration"), ("overlap", "timeline_order"),
])
def test_hard_timeline_drift_is_separate_from_review(change, code):
    document = contract("speculative_decoding_timeline")
    timeline = timeline_for(document)
    if change == "text":
        timeline["blocks"][0]["text"] = "The next token appears before its target pass."
    elif change == "order":
        timeline["blocks"][0], timeline["blocks"][1] = timeline["blocks"][1], timeline["blocks"][0]
    elif change == "beat_id":
        timeline["blocks"][0]["beat_id"] = "three-waits"
    elif change == "missing":
        timeline["blocks"].pop()
    elif change == "duration":
        timeline["blocks"][0]["duration"] = 1
    elif change == "overlap":
        timeline["blocks"][1]["start"] = 4
        timeline["blocks"][1]["duration"] = 6
    report = teaching.validate_contract(document, timeline=timeline)
    assert not report["valid"]
    assert code in codes(report)


def event_document():
    document = contract("speculative_decoding_timeline")
    for beat in document["beats"]:
        beat.pop("events", None)
    document["beats"][0]["events"] = [
        {"label": "target-finished", "data": {"token": "can", "accepted": True}},
        {"label": "token-visible"},
    ]
    timeline = timeline_for(document)
    timeline.update({"schema_version": 1, "run_id": "offline-fixture", "events": [
        {"time": 3, "label": "target-finished", "beat_id": "first-dependency",
         "data": {"token": "can", "accepted": True}},
        {"time": 4, "label": "token-visible", "beat_id": "first-dependency"},
    ]})
    return document, timeline


def test_optional_event_mapping_checks_data_and_cause_order():
    document, timeline = event_document()
    assert teaching.validate_contract(document, timeline=timeline)["valid"]
    timeline["events"][0]["data"]["token"] = "fast"
    assert "event_data_drift" in codes(teaching.validate_contract(document, timeline=timeline))
    document, timeline = event_document()
    timeline["events"][0]["label"], timeline["events"][1]["label"] = (
        timeline["events"][1]["label"], timeline["events"][0]["label"])
    assert "event_drift" in codes(teaching.validate_contract(document, timeline=timeline))
    document, timeline = event_document()
    timeline["events"][1]["time"] = 7
    assert "event_timing" in codes(teaching.validate_contract(document, timeline=timeline))


def test_legacy_timeline_accepted_without_optional_fields():
    document = contract()
    for beat in document["beats"]:
        beat.pop("events", None)
    timeline = timeline_for(document)
    timeline.pop("events")
    for block in timeline["blocks"]:
        del block["duration"]
    report = teaching.validate_contract(document, timeline=timeline)
    assert report["valid"], report["errors"]
    assert report["evidence"]["audiovisual_fidelity"] == "not_assessed"
    assert not any(check["check"] == "timeline_comparison" for check in report["omitted_checks"])


def test_empty_and_zero_time_narration_are_not_evidence():
    document = contract()
    assert "timeline_shape" in codes(teaching.validate_contract(document, timeline={"scene_duration": 5, "blocks": []}))
    timeline = timeline_for(document)
    timeline["blocks"][0].update({"start": 0, "end": 0, "duration": 0})
    assert "timeline_duration" in codes(teaching.validate_contract(document, timeline=timeline))
    timeline = timeline_for(document)
    timeline["scene_duration"] = 0
    assert "timeline_shape" in codes(teaching.validate_contract(document, timeline=timeline))


def test_explicit_duration_uses_absolute_millisecond_tolerance():
    document = contract()
    timeline = timeline_for(document)
    timeline["blocks"][0]["duration"] += 0.0009
    assert teaching.validate_contract(document, timeline=timeline)["valid"]
    timeline["blocks"][0]["duration"] += 0.0002
    assert "timeline_duration" in codes(teaching.validate_contract(document, timeline=timeline))


def test_source_digest_is_drift_detection_not_claim_entailment():
    document = contract()
    source = document["sources"][0]
    text = (ROOT / source["ref"]).read_text(encoding="utf-8")
    assert teaching.text_digest(text.replace("\n", "\r\n")) == source["sha256"]
    report = teaching.validate_contract(document, source_texts={source["id"]: text + "\n# changed"})
    assert "source_drift" in codes(report)
    document["claims"][0]["statement"] = "An author could still assert an unsupported inference here."
    report = teaching.validate_contract(document)
    assert report["valid"]
    assert report["evidence"]["claim_entailment"] == "human_review_required"


@pytest.mark.parametrize("key,value", [
    ("sources", None), ("sources", [False]), ("claims", {}),
    ("worked_examples", []), ("beats", [{"id": "bad"}]),
    ("transfer_questions", []), ("schema_version", True), ("prerequisites", ""),
    ("unknowns", [float("nan")]), ("audience", " "),
])
def test_malformed_contract_returns_serializable_errors(key, value):
    document = contract()
    document[key] = value
    report = teaching.validate_contract(document)
    assert not report["valid"]
    json.dumps(report, allow_nan=False)


def test_bad_crossreferences_and_duplicate_ids_are_errors():
    document = contract()
    document["beats"][0]["claim_ids"] = ["nonexistent"]
    document["sources"].append(copy.deepcopy(document["sources"][0]))
    document["claims"][0]["evidence"][0]["source"] = "missing"
    document["transfer_questions"][0]["example_ids"] = ["unknown"]
    report = teaching.validate_contract(document)
    assert {"reference", "duplicate_id"} <= codes(report)


@pytest.mark.parametrize("value", ["[]", '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', "{bad"])
def test_loader_rejects_nonobject_duplicate_nonfinite_and_bad_json(scratch, value):
    scratch.write_text(value, encoding="utf-8")
    with pytest.raises(ValueError):
        teaching.load_contract(scratch)


@pytest.mark.parametrize("check", [
    {}, [], {"kind": []},
    {"kind":"factorized_prefixes","input":{"marginals":[{"a":"0.9"}],"budget":1},"expected":{}},
    {"kind":"ancestry","input":{"paths":[[],["a","b"]]},"expected":{}},
    {"kind":"greedy_tree_walk","input":{"paths":[[]],"decisions":[]},"expected":{}},
    {"kind":"serial_cost","input":{"token_count":True,"target_pass":1,"draft_step":0.2,"verification":1},"expected":{}},
    {"kind":"probability_graphic","input":{"probability":"NaN","fill_fraction":0},"expected":{}},
])
def test_invalid_oracle_inputs_fail_cleanly(check):
    report = teaching.evaluate_check(check)
    assert not report["passed"]
    json.dumps(report, allow_nan=False)


def test_empty_expected_state_cannot_pass_vacuously():
    check = copy.deepcopy(contract()["worked_examples"][0]["checks"][0])
    check["expected"] = {}
    assert not teaching.evaluate_check(check)["passed"]


def test_measured_example_requires_real_measurement_source():
    document = contract()
    document["worked_examples"][0]["provenance"] = "measured"
    report = teaching.validate_contract(document)
    assert "provenance" in codes(report)
    document["worked_examples"][0]["source_refs"] = None
    assert "shape" in codes(teaching.validate_contract(document))


def test_event_data_types_are_semantics_not_coercions():
    document, timeline = event_document()
    timeline["events"][0]["data"]["accepted"] = 1
    assert "event_data_drift" in codes(teaching.validate_contract(document, timeline=timeline))


def test_cli_offline_json_and_exit_codes(scratch):
    command = [sys.executable, "-B", str(ROOT / "scripts" / "validate_teaching.py")]
    good = subprocess.run(
        [*command, str(ROOT / "examples" / "ddtree_full" / "teaching.json"), "--json", "--check-sources"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert good.returncode == 0, good.stderr
    assert json.loads(good.stdout)["valid"]
    document = contract()
    document["claims"][0]["evidence"] = []
    scratch.write_text(json.dumps(document), encoding="utf-8")
    bad = subprocess.run([*command, str(scratch), "--json"], cwd=ROOT, text=True, capture_output=True, check=False)
    assert bad.returncode == 1
    assert not json.loads(bad.stdout)["valid"]
    scratch.write_text("{bad", encoding="utf-8")
    broken = subprocess.run([*command, str(scratch), "--json"], cwd=ROOT, text=True, capture_output=True, check=False)
    assert broken.returncode == 2
    assert json.loads(broken.stdout)["errors"][0]["code"] == "input"


def test_validator_does_not_mutate_inputs():
    document, timeline = event_document()
    before = copy.deepcopy((document, timeline))
    teaching.validate_contract(document, timeline=timeline)
    assert (document, timeline) == before


@pytest.fixture
def artifact_paths(scratch):
    paths = [scratch.with_name(f"{scratch.stem}-{suffix}.json") for suffix in ("timeline", "report")]
    yield paths
    for path in paths:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize("run_id", [None, "offline-bound-fixture"])
def test_cli_bound_artifact_hashes_exact_bytes_and_keeps_human_evidence_separate(scratch, artifact_paths, run_id):
    timeline_path, output_path = artifact_paths
    document = contract("speculative_decoding_timeline")
    timeline = timeline_for(document)
    if run_id:
        timeline["run_id"] = run_id
    contract_bytes = ("\ufeff" + json.dumps(document, indent=2).replace("\n", "\r\n")).encode("utf-8")
    timeline_bytes = json.dumps(timeline, indent=2).replace("\n", "\r\n").encode("utf-8")
    scratch.write_bytes(contract_bytes)
    timeline_path.write_bytes(timeline_bytes)
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "validate_teaching.py"),
         str(scratch), "--timeline", str(timeline_path), "--output", str(output_path), "--json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout
    artifact = teaching.load_contract(output_path)
    assert artifact["status"] == "passed"
    assert artifact["validation"] == json.loads(result.stdout)
    assert artifact["contract"] == {"path": str(scratch.resolve()), "sha256": hashlib.sha256(contract_bytes).hexdigest()}
    assert artifact["timeline"] == {"path": str(timeline_path.resolve()), "sha256": hashlib.sha256(timeline_bytes).hexdigest()}
    assert artifact.get("run_id") == run_id
    assert artifact["validation"]["evidence"]["human_comprehension"] == "not_assessed"
    assert artifact["validation"]["evidence"]["audiovisual_fidelity"] == "not_assessed"
    assert artifact["validation"]["evidence"]["production_acceptance"] == "not_assessed"


def test_bound_artifact_requires_timeline_and_never_overwrites_inputs(scratch, artifact_paths):
    timeline_path, output_path = artifact_paths
    document = contract()
    scratch.write_text(json.dumps(document), encoding="utf-8")
    command = [sys.executable, "-B", str(ROOT / "scripts" / "validate_teaching.py"), str(scratch), "--json"]
    missing = subprocess.run([*command, "--output", str(output_path)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert missing.returncode == 2
    assert "requires --timeline" in json.loads(missing.stdout)["errors"][0]["message"]
    assert not output_path.exists()
    timeline_path.write_text(json.dumps(timeline_for(document)), encoding="utf-8")
    before = scratch.read_bytes()
    collision = subprocess.run([*command, "--timeline", str(timeline_path), "--output", str(scratch)],
                               cwd=ROOT, capture_output=True, text=True, check=False)
    assert collision.returncode == 2
    assert scratch.read_bytes() == before


def test_semantic_failure_writes_failed_not_passed_artifact(scratch, artifact_paths):
    timeline_path, output_path = artifact_paths
    document = contract()
    timeline = timeline_for(document)
    timeline["blocks"][0]["text"] = "Wrong narration from a different run."
    scratch.write_text(json.dumps(document), encoding="utf-8")
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "validate_teaching.py"),
         str(scratch), "--timeline", str(timeline_path), "--output", str(output_path), "--json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    artifact = teaching.load_contract(output_path)
    assert artifact["status"] == "failed"
    assert not artifact["validation"]["valid"]
    assert "narration_drift" in codes(artifact["validation"])


@pytest.mark.parametrize("run_id", [None, "", 1, []])
def test_present_but_invalid_run_id_is_not_legacy(run_id):
    document = contract()
    timeline = timeline_for(document)
    timeline["run_id"] = run_id
    assert "timeline_shape" in codes(teaching.validate_contract(document, timeline=timeline))


@pytest.mark.parametrize("episode", ("ddtree_full", "speculative_decoding_timeline"))
def test_canonical_event_contract_rejects_missing_or_wrong_transition(episode):
    document = contract(episode)
    timeline = timeline_for(document)
    assert timeline["events"]
    assert teaching.validate_contract(document, timeline=timeline)["valid"]
    original = copy.deepcopy(timeline)
    timeline["events"].pop()
    assert "event_drift" in codes(teaching.validate_contract(document, timeline=timeline))
    original["events"][0]["label"] = "wrong-completed-transition"
    assert "event_drift" in codes(teaching.validate_contract(document, timeline=original))


@pytest.mark.parametrize("episode,class_name", [
    ("ddtree_full", "DDTreeFullExplainer"),
    ("speculative_decoding_timeline", "SpeculativeDecodingTimeline"),
])
def test_canonical_events_follow_real_completed_state_without_changing_timing(
    monkeypatch, tmp_path, episode, class_name,
):
    from manim import tempconfig

    module = importlib.import_module(f"examples.{episode}.scene")
    scene_class = getattr(module, class_name)
    document = contract(episode)
    assert list(module.BEAT_IDS) == [beat["id"] for beat in document["beats"]]
    expected = [(beat["id"], event["label"]) for beat in document["beats"] for event in beat.get("events", [])]
    observed = []
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "none")
    monkeypatch.setenv("MANIM_RUN_ID", f"offline-events-{episode}")
    monkeypatch.setenv("MANIM_TIMELINE_PATH", str(tmp_path / "events.json"))

    with tempconfig({"dry_run": True, "skip_animations": True, "quality": "low_quality",
                     "media_dir": str(tmp_path / "media"), "verbosity": "ERROR"}):
        scene = scene_class()
        record = scene.record_visual_event

        def observe(label, *, beat_id=None):
            p = scene.picture
            families = {id(part) for mob in scene.mobjects for part in mob.get_family()}
            observed.append((scene._active_beat_id, label))
            if episode == "speculative_decoding_timeline":
                if label.startswith("baseline-token-ready:"):
                    assert p.baseline_intervals[0].progress == 1
                    assert id(p.baseline_tokens[0]) in families
                elif label.startswith("baseline-prefix-ready:"):
                    assert all(interval.progress == 1 for interval in p.baseline_intervals)
                elif label.startswith("draft-complete:"):
                    assert all(interval.progress == 1 for interval in p.drafts)
                    assert all(not candidate.accepted for candidate in p.candidates)
                    assert all(id(candidate.dot) in families for candidate in p.candidates)
                elif label == "verification-complete":
                    assert p.verifier.progress == 1
                    assert all(not candidate.accepted for candidate in p.candidates)
                elif label.startswith("output-ready:"):
                    assert p.verifier.progress == 1
                    assert all(candidate.accepted for candidate in p.candidates)
                    for index, candidate in enumerate(p.candidates):
                        assert candidate.dot.get_center() == pytest.approx(p.accepted_position(index))
                else:
                    raise AssertionError(f"Unexpected completion event: {label}")
            elif label.startswith("prefix-selected:"):
                node = p.nodes[label.split(":", 1)[1]]
                assert node in scene.mobjects
                assert node.mass in node.submobjects
                assert id(node.word) in families
            elif label == "tree-flattened":
                for key, node in p.nodes.items():
                    assert node.dot.get_center() == pytest.approx(module.FLAT_POSITIONS[key])
            elif label == "attention-mask-complete":
                assert len(scene.mask_overlays) == 22
                assert all(id(cell[1]) in families for row in p.matrix.cells for cell in row)
            elif label == "target-miss-visible:runs":
                assert scene.bonus in scene.mobjects
                assert scene.bonus_word.text == scene.choice.text == "runs"
            elif label == "output-ready:a,model,runs":
                assert [p.nodes[key].word.text for key in ("a", "a-model")] + [scene.bonus_word.text] == ["a", "model", "runs"]
                assert p.nodes["a"].dot.get_center() == pytest.approx((-1.50, 0.55, 0))
                assert p.nodes["a-model"].dot.get_center() == pytest.approx((0.45, 0.55, 0))
                assert scene.bonus_dot.get_center() == pytest.approx((3.1, 0.55, 0))
            else:
                raise AssertionError(f"Unexpected completion event: {label}")
            record(label, beat_id=beat_id)

        monkeypatch.setattr(scene, "record_visual_event", observe)
        scene.render()
        timeline = teaching.load_contract(tmp_path / "events.json")
        assert observed == expected
        assert [(event["beat_id"], event["label"]) for event in timeline["events"]] == expected
        assert [block["beat_id"] for block in timeline["blocks"]] == list(module.BEAT_IDS)
        report = teaching.validate_contract(document, timeline=timeline)
        assert report["valid"], report["errors"]
        assert not any(check["check"] == "visual_event_comparison" for check in report["omitted_checks"])
        assert report["evidence"]["audiovisual_fidelity"] == "not_assessed"
        scene_times = [(block["start"], block["end"], block["text"]) for block in timeline["blocks"]]

        monkeypatch.setenv("MANIM_TIMELINE_PATH", str(tmp_path / "unrecorded.json"))
        without_recording = scene_class()
        monkeypatch.setattr(without_recording, "record_visual_event", lambda *args, **kwargs: None)
        without_recording.render()
        assert [(block["start"], block["end"], block["text"]) for block in without_recording._review_blocks] == scene_times
        assert without_recording.time == scene.time
