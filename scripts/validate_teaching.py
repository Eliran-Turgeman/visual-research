"""Validate an offline teaching contract without rendering or importing Manim.

From the repository root:
    python scripts\\validate_teaching.py examples\\ddtree_full\\teaching.json --json
    python scripts\\validate_teaching.py examples\\ddtree_full\\teaching.json ^
        --timeline media\\review\\ddtree_full\\timeline.json --check-sources ^
        --output media\\review\\ddtree_full\\teaching-validation.json

Exit 0: deterministic checks pass (review warnings may remain).
Exit 1: contract, semantic, source-content or timeline drift errors.
Exit 2: malformed/unreadable input. No outcome certifies comprehension.
--check-sources reads local source refs only, rooted at --root (default repo).
It never fetches external refs, evaluates source code, or contacts a provider.

--output requires --timeline and writes a bound artifact:
{schema_version: 1, status: passed|failed, contract: {path, sha256},
 timeline: {path, sha256}, run_id?: timeline.run_id, validation: full_report}.
Paths are absolute; hashes cover the exact raw input bytes, not normalized text.
Legacy timelines omit run_id. This is not a production-acceptance record.
Consumers must recompute hashes, match the manifest's timeline and run ID, and
require explicit audiovisual/teaching review. The artifact alone proves neither
media existence nor human comprehension. --json stdout remains the raw report.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from manim_lib import teaching


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--timeline", type=Path)
    parser.add_argument("--check-sources", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable result")
    parser.add_argument("--output", type=Path, help="Write bound validation artifact; requires --timeline")
    args = parser.parse_args(argv)
    try:
        if args.output and not args.timeline:
            raise ValueError("--output requires --timeline; an unbound contract pass is not media evidence")
        if args.output and args.output.resolve() in (args.contract.resolve(), args.timeline.resolve()):
            raise ValueError("--output must not overwrite the contract or timeline")
        contract_bytes = args.contract.read_bytes()
        contract = teaching.loads_contract(contract_bytes.decode("utf-8-sig"))
        timeline_bytes = args.timeline.read_bytes() if args.timeline else None
        timeline = teaching.loads_contract(timeline_bytes.decode("utf-8-sig")) if timeline_bytes is not None else None
        texts = None
        if args.check_sources:
            texts = {}
            root = args.root.resolve()
            sources = contract.get("sources", [])
            if isinstance(sources, list):
                for source in sources:
                    if not isinstance(source, dict) or not isinstance(source.get("ref"), str):
                        continue
                    ref = source["ref"]
                    if "://" in ref or not isinstance(source.get("id"), str):
                        continue
                    path = (root / ref.replace("\\", "/")).resolve()
                    if not path.is_relative_to(root):
                        raise ValueError(f"Source must remain inside --root: {ref}")
                    if path.is_file():
                        texts[source["id"]] = path.read_text(encoding="utf-8-sig")
        report = teaching.validate_contract(contract, timeline=timeline, source_texts=texts)
        code = 0 if report["valid"] else 1
        if args.output:
            artifact = {
                "schema_version": 1,
                "status": "passed" if report["valid"] else "failed",
                "contract": {"path": str(args.contract.resolve()), "sha256": hashlib.sha256(contract_bytes).hexdigest()},
                "timeline": {"path": str(args.timeline.resolve()), "sha256": hashlib.sha256(timeline_bytes).hexdigest()},
                "validation": report,
            }
            if isinstance(timeline.get("run_id"), str) and timeline["run_id"].strip():
                artifact["run_id"] = timeline["run_id"]
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(artifact, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError) as exc:
        report = {"valid": False, "errors": [{"code": "input", "path": str(args.contract), "message": str(exc)}],
                  "warnings": [], "checks": []}
        code = 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))
    else:
        print(f"Deterministic checks: {'PASS' if report['valid'] else 'FAIL'}")
        for level in ("errors", "warnings"):
            for issue in report[level]:
                print(f"{level[:-1].upper()} {issue['code']} {issue['path']}: {issue['message']}")
        print("Human comprehension, audiovisual fidelity and production acceptance are not assessed.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
