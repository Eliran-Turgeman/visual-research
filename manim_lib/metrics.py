"""Offline production accounting; no provider prices, paid calls, or routing.

Input schemas (JSON, version 1)
==============================
Manifests are the actual per-attempt production records: ``schema_version``,
``run_id``, ``profile``, ``status``, ``scene_file``, ``scene_name``, ``settings``,
and ``metrics`` are required. Optional ``manifest_id`` must also be unique.
Other production fields/artifacts are preserved for the review validator.
``metrics.render_seconds`` is managed-wrapper render/validation elapsed time,
not CPU seconds, end-to-end production latency, dollars, or human labor. Optional measured fields
are ``video_seconds``, ``narration_requests``, ``repeated_narration_requests``,
``narration_cache_hits``, ``repair_count``, and ``cost``. Repeated requests count
requests for previously requested narration; cache hits count served requests,
not bytes or savings. All measurements are per-run increments, not cumulative
process snapshots. Nothing is inferred from the existence of cache files.

Optional SUPPLIED accounting is a separate object, for example::

    {"schema_version": 1, "runs": [{
      "run_id": "attempt-1",
      "task_id": "explain-speculation-v1", "episode_id": "episode-7",
      "cohort": {"id": "baseline", "model": "explicit-model-id", "settings": {}},
      "source": "invoice plus operator stopwatch",
      "cost": {"amount": 0.42, "currency": "USD", "coverage": "complete"},
      "video_seconds": 60, "human_correction_seconds": 120,
      "repair_count": 1,
      "narration_requests": 5, "repeated_narration_requests": 2,
      "narration_cache_hits": 1
    }]}

``source`` is required for supplied measurements; it describes provenance, not
independent verification. Cost must explicitly specify currency and coverage
(``complete`` or ``lower_bound``) of THAT run's included production costs.
Human correction time is always separate and is never converted to money.
Accounting may fill missing manifest measurements, never overwrite them.
Task/episode/cohort identity may instead be in the manifest, with the same shape.
Cohort ``model`` identifies the explicitly reported generation model; cohort
``settings`` describe generation settings, while actual manifest settings and
profile are additionally checked for consistency within each cohort.

Reviews are separate explicit review records indexed by ``run_id``. The trusted
``validate_review(manifest, review) -> bool`` adapter MUST verify explicit review
evidence, current manifest/artifact hash bindings, and acceptance requirements.
There is deliberately no default validator and no manifest acceptance flag.
The CLI uses the repository's review validator rather than inventing approvals.

Reports preserve unknowns as null. Partial nonnegative sums are marked
``lower_bound``; ratios with incomplete duration denominators remain unknown.
All attempted runs (including failures/repairs) contribute costs. Comparisons
require one identical explicit task/episode, stable settings per cohort, and
one currency; sample sizes are descriptive, not causal savings evidence.
Without task/episode identity, an inventory may combine only the same exact
scene file/class, and comparisons remain disabled.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any


class MetricsError(ValueError):
    """Invalid, ambiguous, or incomparable production/accounting evidence."""


ReviewValidator = Callable[[Mapping[str, Any], Mapping[str, Any]], bool]
_COUNTS = (
    "narration_requests",
    "repeated_narration_requests",
    "narration_cache_hits",
    "repair_count",
)
_MEASUREMENTS = ("render_seconds", "video_seconds", *_COUNTS, "human_correction_seconds")
_IDENTITY = ("task_id", "episode_id", "cohort")


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MetricsError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise MetricsError(f"{label} must be a nonempty, trimmed string")
    return value


def _version(record: Mapping[str, Any], label: str) -> None:
    if type(record.get("schema_version")) is not int or record["schema_version"] != 1:
        raise MetricsError(f"{label}.schema_version must be 1")


def _number(value: object, label: str, *, count: bool = False) -> float | int | None:
    if value is None:
        return None
    if type(value) not in (int, float):
        raise MetricsError(f"{label} must be a finite nonnegative number or null")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < 0 or (count and type(value) is not int):
        raise MetricsError(f"{label} must be a finite nonnegative {'integer' if count else 'number'}")
    return value


def _canonical(value: object, label: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise MetricsError(f"{label} must contain finite JSON values") from exc


def _indexed(records: Iterable[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    result = {}
    for raw in records:
        record = _object(raw, label)
        run_id = _text(record.get("run_id"), f"{label}.run_id")
        if run_id in result:
            raise MetricsError(f"Duplicate {label} run_id: {run_id}")
        result[run_id] = record
    return result


def _accounting(data: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if data is None:
        return {}
    data = _object(data, "accounting")
    _version(data, "accounting")
    if set(data) - {"schema_version", "runs"}:
        raise MetricsError("Unknown accounting fields")
    if not isinstance(data.get("runs"), list):
        raise MetricsError("accounting.runs must be an array")
    result = _indexed(data["runs"], "accounting")
    for run_id, row in result.items():
        if set(row) - {"run_id", "source", "cost", *_IDENTITY, *_MEASUREMENTS}:
            raise MetricsError(f"Unknown accounting fields for {run_id}")
        if any(row.get(key) is not None for key in (*_MEASUREMENTS, "cost")):
            _text(row.get("source"), f"accounting[{run_id}].source")
    return result


def _cost(value: object, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    cost = _object(value, label)
    if set(cost) != {"amount", "currency", "coverage"}:
        raise MetricsError(f"{label} requires exactly amount, currency, coverage")
    amount = _number(cost["amount"], f"{label}.amount")
    if amount is None:
        raise MetricsError(f"{label}.amount must be known; use null for unknown cost")
    currency = _text(cost["currency"], f"{label}.currency")
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise MetricsError(f"{label}.currency must be a three-letter uppercase currency code")
    if cost["coverage"] not in ("complete", "lower_bound"):
        raise MetricsError(f"{label}.coverage must be complete or lower_bound")
    return dict(cost)


def _cohort(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    cohort = _object(value, "cohort")
    if set(cohort) != {"id", "model", "settings"}:
        raise MetricsError("cohort requires exactly id, model, settings")
    _text(cohort["id"], "cohort.id")
    _text(cohort["model"], "cohort.model")
    _object(cohort["settings"], "cohort.settings")
    _canonical(cohort, "cohort")
    return dict(cohort)


def _sum(values: Iterable[float | int]) -> float:
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise MetricsError("Measurement total is not finite") from exc
    if not math.isfinite(result):
        raise MetricsError("Measurement total is not finite")
    return result


def _measurement(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    known = [row for row in rows if row["values"][key] is not None]
    total = None
    if known:
        values = [row["values"][key] for row in known]
        total = _number(sum(values), key, count=True) if key in _COUNTS else _sum(values)
    return {
        "value": total,
        "coverage": "complete" if known and len(known) == len(rows) else "lower_bound" if known else "unknown",
        "reported_runs": len(known),
        "total_runs": len(rows),
        "provenance": {
            "manifest": sum(row["origins"][key] == "manifest" for row in known),
            "supplied": sum(row["origins"][key] == "supplied" for row in known),
        },
    }


def _ratio(
    cost: dict[str, Any], denominator: float | None, *, unit: str, reason: str
) -> dict[str, Any]:
    amount = None
    coverage = "unknown"
    if denominator is not None and denominator > 0 and cost["amount"] is not None:
        amount = cost["amount"] / denominator
        if not math.isfinite(amount):
            raise MetricsError("Cost ratio is not finite")
        coverage = cost["coverage"]
        reason = f"all attempted-run costs / {unit}"
    return {
        "amount": amount, "currency": cost["currency"], "coverage": coverage,
        "denominator_unit": unit, "basis": reason,
    }


def _totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in rows if row["accepted"]]
    known_costs = [row for row in rows if row["cost"] is not None]
    costs_complete = len(known_costs) == len(rows) and all(
        row["cost"]["coverage"] == "complete" for row in known_costs
    )
    cost = {
        "amount": _sum(row["cost"]["amount"] for row in known_costs) if known_costs else None,
        "currency": known_costs[0]["cost"]["currency"] if known_costs else None,
        "coverage": "complete" if known_costs and costs_complete else "lower_bound" if known_costs else "unknown",
        "reported_runs": len(known_costs),
        "total_runs": len(rows),
        "provenance": {
            "manifest": sum(row["origins"]["cost"] == "manifest" for row in known_costs),
            "supplied": sum(row["origins"]["cost"] == "supplied" for row in known_costs),
        },
    }
    duration = _measurement(accepted, "video_seconds")
    minutes = duration["value"] / 60 if duration["coverage"] == "complete" else None
    return {
        "attempts": len(rows),
        "accepted_outputs": len(accepted),
        "acceptance_rate": len(accepted) / len(rows) if rows else None,
        "reviewed_runs": sum(row["reviewed"] for row in rows),
        "render_seconds": _measurement(rows, "render_seconds"),
        **{key: _measurement(rows, key) for key in _COUNTS},
        "human_correction_seconds": _measurement(rows, "human_correction_seconds"),
        "accepted_video_seconds": duration,
        "cost": cost,
        "cost_per_accepted_video": _ratio(
            cost, len(accepted), unit="accepted videos", reason="no accepted outputs or unknown cost"
        ),
        "cost_per_accepted_minute": _ratio(
            cost, minutes, unit="accepted video minutes",
            reason="accepted duration incomplete/zero, no accepted outputs, or unknown cost",
        ),
    }


def summarize_runs(
    manifests: Iterable[Mapping[str, Any]],
    accounting: Mapping[str, Any] | None = None,
    reviews: Iterable[Mapping[str, Any]] = (),
    *,
    validate_review: ReviewValidator | None = None,
    compare: bool = False,
) -> dict[str, Any]:
    """Validate and aggregate without I/O; a supplied validator is a trust boundary.

    Duplicate/unknown run IDs, conflicting measurements, mixed currency or
    task/episode identity fail the entire report rather than being skipped.
    No review means *unverified*, not rejected. ``acceptance_rate`` is therefore
    the verified-accepted yield over all attempts, not a reviewer pass rate.
    """
    manifests_by_id = _indexed(manifests, "manifest")
    supplied = _accounting(accounting)
    review_by_id = _indexed(reviews, "review")
    for label, records in (("accounting", supplied), ("review", review_by_id)):
        unknown = set(records) - set(manifests_by_id)
        if unknown:
            raise MetricsError(f"{label} references unknown run IDs: {', '.join(sorted(unknown))}")
    if review_by_id and validate_review is None:
        raise MetricsError("Explicit reviews require a trusted bound-review validator")

    rows = []
    identities = set()
    unidentified_scenes = set()
    manifest_ids = set()
    cohort_settings = {}
    for run_id, manifest in manifests_by_id.items():
        _version(manifest, f"manifest[{run_id}]")
        if manifest.get("manifest_id") is not None:
            manifest_id = _text(manifest["manifest_id"], "manifest.manifest_id")
            if manifest_id in manifest_ids:
                raise MetricsError(f"Duplicate manifest_id: {manifest_id}")
            manifest_ids.add(manifest_id)
        profile = _text(manifest.get("profile"), "manifest.profile")
        _text(manifest.get("status"), "manifest.status")
        scene = tuple(
            _text(manifest.get(key), f"manifest.{key}") for key in ("scene_file", "scene_name")
        )
        settings = _object(manifest.get("settings"), "manifest.settings")
        _canonical(settings, "manifest.settings")
        measured = _object(manifest.get("metrics"), "manifest.metrics")
        extra = supplied.get(run_id, {})
        values, origins = {}, {}
        for key in (*_MEASUREMENTS, "cost", *_IDENTITY):
            original = manifest.get(key) if key in _IDENTITY else measured.get(key)
            replacement = extra.get(key)
            if original is not None and replacement is not None:
                raise MetricsError(f"{run_id}: {key} supplied twice; cannot override manifest evidence")
            values[key] = original if original is not None else replacement
            origins[key] = "manifest" if original is not None else "supplied" if replacement is not None else None
        if measured.get("human_correction_seconds") is not None:
            raise MetricsError("Human correction time belongs in supplied accounting, not render measurements")
        for key in _MEASUREMENTS:
            values[key] = _number(values[key], f"{run_id}.{key}", count=key in _COUNTS)
        requests = values["narration_requests"]
        for key in ("repeated_narration_requests", "narration_cache_hits"):
            if requests is not None and values[key] is not None and values[key] > requests:
                raise MetricsError(f"{run_id}.{key} cannot exceed narration_requests")
        cost = _cost(values["cost"], f"{run_id}.cost")
        identity = tuple(
            _text(values[key], key) if values[key] is not None else None
            for key in ("task_id", "episode_id")
        )
        if (identity[0] is None) != (identity[1] is None):
            raise MetricsError("task_id and episode_id must be provided together")
        identities.add(identity)
        if identity == (None, None):
            unidentified_scenes.add(scene)
        cohort = _cohort(values["cohort"])
        if cohort is not None:
            fingerprint = _canonical([cohort, settings, profile], "cohort settings")
            previous = cohort_settings.setdefault(cohort["id"], fingerprint)
            if previous != fingerprint:
                raise MetricsError(f"Incomparable model/settings/profile within cohort {cohort['id']}")
        accepted = False
        review = review_by_id.get(run_id)
        if review is not None:
            accepted = validate_review(manifest, review)
            if type(accepted) is not bool:
                raise MetricsError("Bound-review validator must return bool, not a truthy record")
        rows.append({
            "run_id": run_id, "values": values, "origins": origins, "cost": cost,
            "cohort": cohort, "settings": settings, "profile": profile,
            "accepted": accepted, "reviewed": review is not None,
        })

    if len(identities) > 1:
        raise MetricsError("Incomparable task/episode identities; report each task/episode separately")
    if len(unidentified_scenes) > 1:
        raise MetricsError("Incomparable unidentified scenes; supply explicit matching task/episode identity")
    identity = next(iter(identities), (None, None))
    currencies = {row["cost"]["currency"] for row in rows if row["cost"] is not None}
    if len(currencies) > 1:
        raise MetricsError("Mixed incomparable currencies; no exchange rates are inferred")
    if compare and (not rows or None in identity or any(row["cohort"] is None for row in rows)):
        raise MetricsError("Cohort comparison requires explicit task_id, episode_id, and cohort on every run")
    cohorts = []
    if compare:
        for cohort_id in sorted(cohort_settings):
            members = [row for row in rows if row["cohort"]["id"] == cohort_id]
            cohorts.append({
                **members[0]["cohort"],
                "manifest_settings": dict(members[0]["settings"]),
                "profile": members[0]["profile"],
                "sample_size_attempts": len(members),
                "sample_size_accepted": sum(row["accepted"] for row in members),
                "totals": _totals(members),
            })
    return {
        "schema_version": 1,
        "task_id": identity[0],
        "episode_id": identity[1],
        "run_ids": sorted(manifests_by_id),
        "totals": _totals(rows),
        "comparison": {
            "enabled": compare,
            "matched_task_episodes": 1 if compare else None,
            "cohorts": cohorts,
            "interpretation": "Descriptive samples only; no measured savings, causal effect, or routing recommendation.",
        },
        "notes": [
            "render_seconds sums managed-wrapper render/validation elapsed durations; not CPU time or global production wall-clock latency.",
            "Manifest measurements and supplied accounting have separate provenance; supplied values are not independently audited.",
            "Costs cover all attempted runs; human correction time is separate and has no assigned hourly price.",
            "Unknown values are null; partial nonnegative sums/cost ratios have lower_bound coverage.",
            "Accepted outputs require explicit bound review validation; unreviewed attempts are not reviewer rejections.",
            "No provider prices, automatic model selection, paid API batching, or routing are implemented.",
        ],
    }
