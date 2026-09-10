"""Validate an offline teaching contract without rendering or importing Manim.

From the repository root:
    python scripts\\validate_teaching.py examples\\ddtree_full\\teaching.json --json
    python scripts\\validate_teaching.py examples\\ddtree_full\\teaching.json ^
        --timeline media\\review\\ddtree_full\\timeline.json --check-sources

Exit 0: deterministic checks pass (review warnings may remain).
Exit 1: contract, semantic, source-content or timeline drift errors.
Exit 2: malformed/unreadable input. No outcome certifies comprehension.
--check-sources reads local source refs only, rooted at --root (default repo).
It never fetches external refs, evaluates source code, or contacts a provider.
"""

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# The existing package __init__ imports Manim. Load this stdlib-only module
# directly so the validation CLI does not require graphics/audio dependencies.
_spec = importlib.util.spec_from_file_location("teaching_contract", ROOT / "manim_lib" / "teaching.py")
teaching = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(teaching)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--timeline", type=Path)
    parser.add_argument("--check-sources", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable result")
    args = parser.parse_args(argv)
    try:
        contract = teaching.load_contract(args.contract)
        timeline = teaching.load_contract(args.timeline) if args.timeline else None
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
