"""Print an offline production report; accounting schema: ``manim_lib.metrics``."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


def _load_module(name: str) -> ModuleType:
    # Offline accounting must not initialize Manim/voiceover or pollute JSON stdout.
    qualified = f"manim_lib.{name}"
    if qualified in sys.modules:
        module = sys.modules[qualified]
        if module is None:
            raise ImportError(f"{qualified} is unavailable")
        return module
    path = _ROOT / "manim_lib" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {qualified}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(qualified, None)
        raise
    return module


_metrics = _load_module("metrics")
MetricsError = _metrics.MetricsError
ReviewValidator = _metrics.ReviewValidator
summarize_runs = _metrics.summarize_runs


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise MetricsError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise MetricsError(f"Nonfinite JSON value: {value}")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise MetricsError(f"Nonfinite JSON value: {value}")
    return result


def load_record(path: Path) -> Mapping[str, Any]:
    """Strict JSON loading: unreadable/malformed records fail, never disappear."""
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_keys,
            parse_constant=_invalid_constant,
            parse_float=_finite_float,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise MetricsError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MetricsError(f"{path}: record must be a JSON object")
    return value


def _bound_validator(
    manifest_paths: Mapping[str, Path], review_paths: Mapping[str, Path]
) -> ReviewValidator:
    """Load the review owner's validator only when explicit reviews are used."""
    try:
        verify_acceptance = _load_module("review").verify_acceptance
    except (ImportError, AttributeError, OSError) as exc:
        raise MetricsError(
            "Bound review validation is unavailable. Merge/install the artifact-review "
            "implementation; reviews cannot be counted using manifest status alone."
        ) from exc

    def validate(manifest: Mapping[str, Any], review: Mapping[str, Any]) -> bool:
        run_id = manifest["run_id"]
        manifest_path, review_path = manifest_paths[run_id], review_paths[run_id]
        if load_record(manifest_path) != manifest or load_record(review_path) != review:
            raise MetricsError(f"{run_id}: input records changed during reporting")
        result = verify_acceptance(manifest_path, review_path)
        if (
            not isinstance(result, Mapping)
            or result.get("status") != "accepted"
            or result.get("run_id") != run_id
            or result != review
        ):
            raise MetricsError(f"{run_id}: verifier did not return the bound accepted review")
        if load_record(manifest_path) != manifest or load_record(review_path) != review:
            raise MetricsError(f"{run_id}: input records changed during review validation")
        return True

    return validate


def _paths_by_id(paths: list[Path], records: list[Mapping[str, Any]], label: str) -> dict[str, Path]:
    result = {}
    for path, record in zip(paths, records, strict=True):
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            raise MetricsError(f"{path}: {label}.run_id is required")
        if run_id in result:
            raise MetricsError(f"Duplicate {label} run_id: {run_id}")
        result[run_id] = path
    return result


def main(
    argv: list[str] | None = None,
    *,
    validator_factory: Callable[[Mapping[str, Path], Mapping[str, Path]], ReviewValidator] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Offline report over actual per-run manifests. Render/validation elapsed seconds and "
            "optional manifest usage are measured fields; --accounting is separately "
            "SUPPLIED cost/usage/human-time evidence, not independently audited."
        ),
        epilog=(
            "Accounting JSON schema/examples: manim_lib\\metrics.py. Unknown costs/usage "
            "stay null; partial sums are lower bounds. Dollars, render elapsed time and "
            "human correction time remain separate. Accepted outputs require a current "
            "bound explicit review, never an encoded-success flag. No current paid API "
            "batching/routing implementation, automatic model selection, inferred provider "
            "prices, paid calls, or measured-savings claims."
        ),
    )
    parser.add_argument("manifests", nargs="+", type=Path, help="Actual per-attempt manifest JSON paths")
    parser.add_argument("--accounting", type=Path, help="Optional supplied version-1 accounting JSON")
    parser.add_argument("--review", action="append", type=Path, default=[], help="Durable accepted review JSON, not a technical-only record; repeat per accepted run")
    parser.add_argument("--compare", action="store_true", help="Compare descriptive cohorts for one explicit matching task/episode; include sample sizes")
    parser.add_argument("--output", type=Path, help="Write JSON here instead of stdout (must not be an input)")
    args = parser.parse_args(argv)
    try:
        input_paths = [*args.manifests, *args.review]
        if args.accounting is not None:
            input_paths.append(args.accounting)
        if len({path.resolve() for path in input_paths}) != len(input_paths):
            raise MetricsError("Duplicate input path; a manifest/review/accounting file must be supplied once")
        if args.output and args.output.resolve() in {path.resolve() for path in input_paths}:
            raise MetricsError("Output must not overwrite an input record")
        manifests = [load_record(path) for path in args.manifests]
        reviews = [load_record(path) for path in args.review]
        manifest_paths = _paths_by_id(args.manifests, manifests, "manifest")
        review_paths = _paths_by_id(args.review, reviews, "review")
        validator = None
        if reviews:
            validator = (validator_factory or _bound_validator)(manifest_paths, review_paths)
        report = summarize_runs(
            manifests,
            load_record(args.accounting) if args.accounting else None,
            reviews,
            validate_review=validator,
            compare=args.compare,
        )
        rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (MetricsError, OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
