"""Offline fixtures: no rendering, speech providers, API calls, or prices."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
from types import ModuleType
from pathlib import Path

import pytest

from manim_lib.metrics import MetricsError, summarize_runs


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "summarize_production.py"
spec = importlib.util.spec_from_file_location("summarize_production", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def manifest(run_id="run-1", **metrics):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "profile": "production",
        "status": "rendered",
        "created_at": "2026-09-10T18:00:00Z",
        "scene_file": "scene.py",
        "scene_name": "Explainer",
        "source": {"git_commit": "fixture-revision", "dirty": False},
        "settings": {"quality": "-qh", "provider": "fixture"},
        "environment": {"python": "3.12", "manim": "0.19"},
        "metrics": {"render_seconds": 12, **metrics},
        "artifacts": {
            "video": {"path": f"{run_id}.mp4", "sha256": "a" * 64},
            "timeline": {"path": f"{run_id}.json", "sha256": "b" * 64},
        },
    }


def accounting(*rows):
    return {"schema_version": 1, "runs": list(rows)}


def supplied(run_id="run-1", **values):
    return {"run_id": run_id, "source": "explicit offline fixture measurements", **values}


def cost(amount=0.42, currency="USD", coverage="complete"):
    return {"amount": amount, "currency": currency, "coverage": coverage}


def identity(cohort="baseline", model="reported-model"):
    return {
        "task_id": "explain-speculation-v1",
        "episode_id": "episode-7",
        "cohort": {"id": cohort, "model": model, "settings": {"temperature": 0.2}},
    }


def review(record, *, accepted=True):
    return {
        "run_id": record["run_id"],
        "status": "accepted" if accepted else "technically_verified",
        "decision": "accepted" if accepted else "rejected",
        "reviewer": "fixture-human",
        "artifact_sha256": record["artifacts"]["video"]["sha256"],
    }


def fixture_validator(record, evidence):
    """Stand-in for the separately owned full filesystem/hash review validator."""
    if (
        evidence.get("reviewer") != "fixture-human"
        or evidence.get("artifact_sha256") != record["artifacts"]["video"]["sha256"]
        or evidence.get("run_id") != record["run_id"]
    ):
        raise MetricsError("Invalid bound fixture review")
    return evidence["decision"] == "accepted"


def test_unknown_cost_usage_and_human_time_are_not_zero():
    record = manifest()
    record.update(accepted=True, status="accepted")
    total = summarize_runs([record])["totals"]
    assert total["attempts"] == 1
    assert total["accepted_outputs"] == total["reviewed_runs"] == 0
    assert total["render_seconds"]["value"] == 12
    for key in ("narration_requests", "repair_count", "human_correction_seconds"):
        assert total[key]["value"] is None
        assert total[key]["coverage"] == "unknown"
    for key in ("cost", "cost_per_accepted_video", "cost_per_accepted_minute"):
        assert total[key]["amount"] is None
        assert total[key]["currency"] is None


def test_complete_accounting_counts_failed_attempt_costs_and_separates_human_time():
    first, second = manifest("run-1"), manifest("run-2", render_seconds=18)
    first["status"] = "failed"
    rows = accounting(
        supplied("run-1", cost=cost(0.2), repair_count=0, human_correction_seconds=120),
        supplied("run-2", cost=cost(0.4), repair_count=1, human_correction_seconds=30, video_seconds=120),
    )
    total = summarize_runs(
        [first, second], rows, [review(second)], validate_review=fixture_validator
    )["totals"]
    assert total["attempts"] == 2
    assert total["accepted_outputs"] == 1
    assert total["acceptance_rate"] == 0.5
    assert total["render_seconds"]["value"] == 30
    assert total["human_correction_seconds"]["value"] == 150
    assert total["repair_count"]["value"] == 1
    assert total["cost"]["amount"] == pytest.approx(0.6)
    assert total["cost"]["coverage"] == "complete"
    assert total["cost_per_accepted_video"]["amount"] == pytest.approx(0.6)
    assert total["cost_per_accepted_minute"]["amount"] == pytest.approx(0.3)


def test_partial_cost_is_a_lower_bound_not_total_savings():
    runs = [manifest("run-1", video_seconds=60), manifest("run-2")]
    total = summarize_runs(
        runs, accounting(supplied(cost=cost(0.2))), [review(runs[0])],
        validate_review=fixture_validator,
    )["totals"]
    for key in ("cost", "cost_per_accepted_video", "cost_per_accepted_minute"):
        assert total[key]["amount"] == 0.2
        assert total[key]["coverage"] == "lower_bound"
    assert total["cost"]["reported_runs"] == 1
    assert total["cost"]["total_runs"] == 2


def test_explicit_lower_bound_remains_lower_bound_with_all_runs_reported():
    total = summarize_runs(
        [manifest()], accounting(supplied(cost=cost(0, coverage="lower_bound")))
    )["totals"]
    assert total["cost"]["amount"] == 0
    assert total["cost"]["coverage"] == "lower_bound"


def test_missing_accepted_duration_never_produces_a_bounded_ratio():
    runs = [manifest("run-1", video_seconds=60), manifest("run-2")]
    total = summarize_runs(
        runs, accounting(supplied(cost=cost(0.2))), [review(run) for run in runs],
        validate_review=fixture_validator,
    )["totals"]
    assert total["accepted_video_seconds"]["coverage"] == "lower_bound"
    assert total["cost_per_accepted_minute"]["amount"] is None
    assert total["cost_per_accepted_minute"]["coverage"] == "unknown"


def test_verified_review_duration_enables_cost_per_minute_without_supplied_duration():
    record = manifest()
    accepted = {**review(record), "media": {"video_duration": 120}}
    total = summarize_runs(
        [record], accounting(supplied(cost=cost(0.4))), [accepted],
        validate_review=fixture_validator,
    )["totals"]
    assert total["accepted_video_seconds"]["value"] == 120
    assert total["accepted_video_seconds"]["provenance"] == {
        "manifest": 0, "supplied": 0, "verified_review": 1,
    }
    assert total["cost_per_accepted_minute"]["amount"] == pytest.approx(0.2)
    assert total["cost_per_accepted_minute"]["coverage"] == "complete"


def test_unaccepted_review_metadata_cannot_supply_accepted_duration():
    record = manifest()
    evidence = {**review(record, accepted=False), "media": {"video_duration": 120}}
    total = summarize_runs(
        [record], accounting(supplied(cost=cost())), [evidence],
        validate_review=fixture_validator,
    )["totals"]
    assert total["accepted_outputs"] == 0
    assert total["accepted_video_seconds"]["value"] is None
    assert total["cost_per_accepted_minute"]["amount"] is None


@pytest.mark.parametrize("duration", [-1, 0, float("nan"), float("inf"), True])
def test_invalid_verified_review_duration_is_rejected(duration):
    record = manifest()
    accepted = {**review(record), "media": {"video_duration": duration}}
    with pytest.raises(MetricsError):
        summarize_runs([record], reviews=[accepted], validate_review=fixture_validator)


def test_conflicting_verified_and_reported_durations_are_rejected():
    record = manifest(video_seconds=60)
    accepted = {**review(record), "media": {"video_duration": 120}}
    with pytest.raises(MetricsError, match="conflicts with verified review"):
        summarize_runs([record], reviews=[accepted], validate_review=fixture_validator)
    accepted["media"]["video_duration"] = 60.0001
    total = summarize_runs([record], reviews=[accepted], validate_review=fixture_validator)["totals"]
    assert total["accepted_video_seconds"]["value"] == 60.0001
    assert total["accepted_video_seconds"]["provenance"]["verified_review"] == 1


def test_measured_usage_and_supplied_usage_have_explicit_provenance():
    runs = [
        manifest("run-1", narration_requests=4, repeated_narration_requests=2, narration_cache_hits=1),
        manifest("run-2"),
    ]
    total = summarize_runs(
        runs, accounting(supplied("run-2", narration_requests=2, narration_cache_hits=0))
    )["totals"]
    assert total["narration_requests"]["value"] == 6
    assert type(total["narration_requests"]["value"]) is int
    assert total["narration_requests"]["provenance"] == {"manifest": 1, "supplied": 1}
    assert total["narration_cache_hits"]["value"] == 1
    assert total["narration_cache_hits"]["coverage"] == "complete"
    assert total["repeated_narration_requests"]["value"] == 2
    assert total["repeated_narration_requests"]["coverage"] == "lower_bound"


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), -float("inf"), True, "1", 10**400])
@pytest.mark.parametrize("key", ["render_seconds", "video_seconds", "repair_count", "narration_requests"])
def test_rejects_invalid_measurements(value, key):
    with pytest.raises(MetricsError, match="finite nonnegative"):
        summarize_runs([manifest(**{key: value})])


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_rejects_invalid_supplied_cost_and_human_time(value):
    for entry in (supplied(cost=cost(value)), supplied(human_correction_seconds=value)):
        with pytest.raises(MetricsError, match="finite nonnegative"):
            summarize_runs([manifest()], accounting(entry))


def test_rejects_fractional_counts_and_inconsistent_usage():
    for metrics in (
        {"repair_count": 0.5},
        {"narration_requests": 1, "narration_cache_hits": 2},
        {"narration_requests": 1, "repeated_narration_requests": 2},
    ):
        with pytest.raises(MetricsError):
            summarize_runs([manifest(**metrics)])


def test_rejects_overflowing_total():
    with pytest.raises(MetricsError, match="not finite"):
        summarize_runs([manifest("a", render_seconds=1e308), manifest("b", render_seconds=1e308)])


def test_rejects_duplicate_manifest_accounting_and_review_ids():
    record = manifest()
    with pytest.raises(MetricsError, match="Duplicate manifest"):
        summarize_runs([record, copy.deepcopy(record)])
    with pytest.raises(MetricsError, match="Duplicate accounting"):
        summarize_runs([record], accounting(supplied(), supplied()))
    with pytest.raises(MetricsError, match="Duplicate review"):
        summarize_runs([record], reviews=[review(record), review(record)], validate_review=fixture_validator)
    other = manifest("run-2")
    record["manifest_id"] = other["manifest_id"] = "same-manifest"
    with pytest.raises(MetricsError, match="Duplicate manifest_id"):
        summarize_runs([record, other])


def test_rejects_unknown_ids_and_overridden_measurements():
    with pytest.raises(MetricsError, match="unknown run"):
        summarize_runs([manifest()], accounting(supplied("missing")))
    with pytest.raises(MetricsError, match="unknown run"):
        summarize_runs([manifest()], reviews=[review(manifest("missing"))], validate_review=fixture_validator)
    with pytest.raises(MetricsError, match="supplied twice"):
        summarize_runs([manifest()], accounting(supplied(render_seconds=12)))


def test_supplied_measurements_require_source_and_cannot_hide_misspellings():
    with pytest.raises(MetricsError, match="source"):
        summarize_runs([manifest()], accounting({"run_id": "run-1", "cost": cost()}))
    with pytest.raises(MetricsError, match="Unknown accounting"):
        summarize_runs([manifest()], accounting(supplied(human_seconds=3)))


def test_rejects_currency_and_cost_coverage_ambiguity():
    with pytest.raises(MetricsError, match="Mixed incomparable currencies"):
        summarize_runs(
            [manifest("a"), manifest("b")],
            accounting(supplied("a", cost=cost()), supplied("b", cost=cost(currency="EUR"))),
        )
    for invalid in (
        {"amount": 1, "currency": "USD"},
        cost(currency="usd"), cost(coverage="estimate"), cost(amount=None),
    ):
        with pytest.raises(MetricsError):
            summarize_runs([manifest()], accounting(supplied(cost=invalid)))


def test_reviews_require_bound_validator_and_explicit_evidence():
    record = manifest(video_seconds=60)
    with pytest.raises(MetricsError, match="trusted bound-review validator"):
        summarize_runs([record], reviews=[review(record)])
    bad = review(record)
    bad["artifact_sha256"] = "f" * 64
    with pytest.raises(MetricsError, match="Invalid bound"):
        summarize_runs([record], reviews=[bad], validate_review=fixture_validator)
    with pytest.raises(MetricsError, match="must return bool"):
        summarize_runs([record], reviews=[review(record)], validate_review=lambda *_: {"accepted": True})
    total = summarize_runs(
        [record], reviews=[review(record, accepted=False)], validate_review=fixture_validator
    )["totals"]
    assert total["reviewed_runs"] == 1
    assert total["accepted_outputs"] == 0


def test_compare_matched_cohorts_annotates_samples_without_savings_claim():
    runs = [manifest("a"), manifest("b"), manifest("c")]
    rows = accounting(
        supplied("a", **identity(), cost=cost(0.2)),
        supplied("b", **identity(), cost=cost(0.3)),
        supplied("c", **identity("candidate", "another-model"), cost=cost(0.1)),
    )
    report = summarize_runs(runs, rows, [review(runs[2])], validate_review=fixture_validator, compare=True)
    comparison = report["comparison"]
    assert comparison["matched_task_episodes"] == 1
    baseline, candidate = comparison["cohorts"]
    assert baseline["sample_size_attempts"] == 2
    assert baseline["sample_size_accepted"] == 0
    assert baseline["totals"]["cost_per_accepted_video"]["amount"] is None
    assert candidate["sample_size_attempts"] == candidate["sample_size_accepted"] == 1
    assert "Descriptive samples only" in comparison["interpretation"]


def test_comparison_requires_explicit_matched_task_episode_and_cohorts():
    with pytest.raises(MetricsError, match="requires explicit"):
        summarize_runs([manifest()], compare=True)
    first, second = supplied("a", **identity()), supplied("b", **identity("candidate"))
    for key in ("task_id", "episode_id"):
        altered = {**second, key: "different"}
        with pytest.raises(MetricsError, match="Incomparable task/episode"):
            summarize_runs([manifest("a"), manifest("b")], accounting(first, altered), compare=True)
    with pytest.raises(MetricsError, match="Incomparable task/episode"):
        summarize_runs([manifest("a"), manifest("b")], accounting(first))
    with pytest.raises(MetricsError, match="provided together"):
        summarize_runs([manifest()], accounting(supplied(task_id="task")))
    different_scene = manifest("other")
    different_scene["scene_name"] = "DifferentEpisode"
    with pytest.raises(MetricsError, match="Incomparable unidentified scenes"):
        summarize_runs([manifest(), different_scene])


@pytest.mark.parametrize("change", ["model", "generation_settings", "render_settings", "profile"])
def test_same_cohort_cannot_merge_incomparable_settings(change):
    first, second = manifest("a"), manifest("b")
    a, b = supplied("a", **identity()), supplied("b", **identity())
    if change == "model":
        b["cohort"]["model"] = "other"
    elif change == "generation_settings":
        b["cohort"]["settings"]["temperature"] = 0.9
    elif change == "render_settings":
        second["settings"]["quality"] = "-ql"
    else:
        second["profile"] = "draft"
    with pytest.raises(MetricsError, match="Incomparable model/settings/profile"):
        summarize_runs([first, second], accounting(a, b), compare=True)


def test_empty_report_and_pure_function_does_not_mutate_inputs():
    empty = summarize_runs([])["totals"]
    assert empty["attempts"] == 0
    assert empty["render_seconds"]["value"] is None
    assert empty["cost"]["amount"] is None
    inputs = [manifest()]
    original = copy.deepcopy(inputs)
    summarize_runs(inputs)
    assert inputs == original


def write_json(directory, name, data):
    path = directory / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_cli_offline_output_and_duplicate_paths(tmp_path, capsys):
    path = write_json(tmp_path, "manifest.json", manifest())
    assert cli.main([str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["totals"]["attempts"] == 1
    with pytest.raises(SystemExit) as exc:
        cli.main([str(path), str(path)])
    assert exc.value.code == 2
    assert "Duplicate input path" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main([str(path), "--output", str(path)])
    assert json.loads(path.read_text())["run_id"] == "run-1"


def test_real_cli_stdout_is_json_without_importing_multimedia_stack(tmp_path):
    path = write_json(tmp_path, "manifest.json", manifest())
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [sys.executable, "-S", str(SCRIPT), str(path)],
        capture_output=True, text=True, check=False, env=env,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["totals"]["attempts"] == 1


def test_cli_uses_bound_adapter_and_never_silently_skips_unreadable(tmp_path, capsys):
    record = manifest()
    path = write_json(tmp_path, "manifest.json", record)
    evidence = write_json(tmp_path, "review.json", review(record))
    output = tmp_path / "report.json"
    factories = []

    def factory(manifests, reviews):
        factories.append((manifests, reviews))
        return fixture_validator

    assert cli.main(
        [str(path), "--review", str(evidence), "--output", str(output)],
        validator_factory=factory,
    ) == 0
    assert factories == [({"run-1": path}, {"run-1": evidence})]
    assert json.loads(output.read_text())["totals"]["accepted_outputs"] == 1
    with pytest.raises(SystemExit) as exc:
        cli.main([str(path), str(tmp_path / "missing.json")])
    assert exc.value.code == 2
    assert "Cannot read" in capsys.readouterr().err


@pytest.mark.parametrize(
    "text",
    ['{"run_id": "a", "run_id": "b"}', '{"value": NaN}', '{"value": 1e999}', "[]", "{"],
)
def test_cli_rejects_ambiguous_or_malformed_json(tmp_path, text):
    path = tmp_path / "invalid.json"
    path.write_text(text)
    with pytest.raises(MetricsError):
        cli.load_record(path)


def test_cli_help_states_accounting_and_no_routing(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "SUPPLIED" in help_text
    assert "human correction time" in help_text
    assert "paid API batching/routing" in help_text


def test_cli_fails_closed_if_review_adapter_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "manim_lib.review", None)
    with pytest.raises(MetricsError, match="Bound review validation is unavailable"):
        cli._bound_validator({}, {})


def test_bound_adapter_verifies_current_paths_and_detects_changed_inputs(tmp_path, monkeypatch):
    record = manifest()
    evidence = review(record)
    manifest_path = write_json(tmp_path, "manifest.json", record)
    review_path = write_json(tmp_path, "review.json", evidence)
    adapter = ModuleType("manim_lib.review")
    calls = []

    def verify_acceptance(manifest_file, review_file):
        calls.append((manifest_file, review_file))
        accepted = cli.load_record(review_file)
        if not fixture_validator(cli.load_record(manifest_file), accepted):
            raise MetricsError("Record is not accepted")
        return accepted

    adapter.verify_acceptance = verify_acceptance
    monkeypatch.setitem(sys.modules, "manim_lib.review", adapter)
    validate = cli._bound_validator({"run-1": manifest_path}, {"run-1": review_path})
    assert validate(record, evidence) is True
    assert calls == [(manifest_path, review_path)]
    write_json(tmp_path, "manifest.json", {**record, "status": "changed"})
    with pytest.raises(MetricsError, match="changed during reporting"):
        validate(record, evidence)


@pytest.mark.parametrize(
    "result",
    [True, {}, {"status": "technically_verified", "run_id": "run-1"},
     {"status": "accepted", "run_id": "wrong"}],
)
def test_bound_adapter_rejects_invalid_verifier_results(tmp_path, monkeypatch, result):
    record = manifest()
    evidence = review(record)
    manifest_path = write_json(tmp_path, "manifest.json", record)
    review_path = write_json(tmp_path, "review.json", evidence)
    adapter = ModuleType("manim_lib.review")
    adapter.verify_acceptance = lambda *_: result
    monkeypatch.setitem(sys.modules, "manim_lib.review", adapter)
    validate = cli._bound_validator({"run-1": manifest_path}, {"run-1": review_path})
    with pytest.raises(MetricsError, match="did not return the bound accepted review"):
        validate(record, evidence)


def test_zero_accepted_duration_has_no_per_minute_ratio():
    record = manifest(video_seconds=0)
    total = summarize_runs(
        [record], accounting(supplied(cost=cost())), [review(record)],
        validate_review=fixture_validator,
    )["totals"]
    assert total["cost_per_accepted_video"]["amount"] == 0.42
    assert total["cost_per_accepted_minute"]["amount"] is None


def test_manifest_cost_and_identity_are_supported_without_supplied_overrides():
    record = manifest(cost=cost(0.1))
    record.update(identity())
    report = summarize_runs([record], compare=True)
    assert report["totals"]["cost"]["provenance"] == {"manifest": 1, "supplied": 0}
    assert report["comparison"]["cohorts"][0]["sample_size_attempts"] == 1
