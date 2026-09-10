"""Offline contracts and independent semantic oracles, not render acceptance.

No scenes, speech providers, production algorithm or Manim are imported.
Scratch files remain under this worktree and are removed after each test.
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
    blocks = []
    for beat in document["beats"]:
        narration = beat.get("narration")
        if narration is None:
            continue
        start = len(blocks) * 5
        blocks.append({
            "index": narration["index"], "start": start, "end": start + 5,
            "duration": 5, "text": narration["text"],
        })
    return {"scene_duration": len(blocks) * 5, "blocks": blocks}


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
    json.dumps(report, allow_nan=False)


def literal_assignment(path, name):
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
    raise AssertionError(f"Missing {name} in {path}")


@pytest.mark.parametrize("episode", ("ddtree_full", "dflash_visual", "ddtree_visual", "speculative_decoding_timeline"))
def test_actual_narration_mapping_is_not_invented(episode):
    document = contract(episode)
    for beat in document["beats"]:
        narration = beat["narration"]
        source = next(s for s in document["sources"] if s["id"] == narration["source"])
        path = ROOT / source["ref"]
        if narration["locator"].startswith("BEATS["):
            call = literal_assignment(path, "BEATS").elts[narration["index"]]
            text = next((kw.value for kw in call.keywords if kw.arg == "narration"), None)
            if text is None:
                text = call.args[2]
        else:
            text = literal_assignment(path, "NARRATION").elts[narration["index"]]
        assert ast.literal_eval(text) == narration["text"]


@pytest.mark.parametrize("episode", ("ddtree_full", "speculative_decoding_timeline"))
def test_pinned_canonical_local_sources_match(episode):
    document = contract(episode)
    texts = {s["id"]: (ROOT / s["ref"]).read_text(encoding="utf-8")
             for s in document["sources"] if "://" not in s["ref"]}
    report = teaching.validate_contract(document, source_texts=texts)
    assert report["valid"], report["errors"]
    assert report["evidence"]["source_content"] == "supplied"
    assert "source_unavailable" in codes(report, "warnings")


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
    report = teaching.validate_contract(document, timeline=timeline_for(document))
    assert report["valid"], report["errors"]
    assert report["evidence"]["audiovisual_fidelity"] == "not_assessed"


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
