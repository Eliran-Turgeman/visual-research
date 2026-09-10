"""Reproducible technical inspection followed by explicit human acceptance.

inspect MANIFEST --output RECORD --frames-dir NEW_DIRECTORY
accept MANIFEST --record RECORD --evidence HUMAN_JSON [--output ACCEPTED_RECORD]
       [--teaching-contract CONTRACT --teaching-validation VALIDATION]
verify MANIFEST --record ACCEPTED_RECORD

Human evidence must bind sha256(RECORD) as review_sha256; see
manim_lib.review.accept_production for its full schema. Acceptance preserves RECORD
and writes RECORD_STEM.accepted.json by default, retaining hashes and references to
both the technical review and attributed human evidence. verify rechecks all
retained evidence. No command modifies the manifest. No automated check approves perceptual
quality or comprehension. All paths in generated records are absolute.

Optional teaching validation must be a run/timeline/contract-hash-bound artifact
from validate_teaching.py --timeline TIMELINE --output VALIDATION, not its raw
--json report. The human evidence must also name teaching_contract_sha256.
accept and verify rerun the pure teaching validator on the bound contract and
actual manifest timeline; a hand-authored success report is not semantic proof.
The accepted record retains teaching.recomputed_validation including warnings
and omitted checks. Source content is not fetched or independently inspected;
unperformed source/event checks and human judgments remain explicitly unassessed.
Optional manifest audio-snapshot lists and timeline block audio references are
hash-checked and retained; absent snapshot metadata remains legacy-compatible.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from manim_lib.review import (
    ReviewError, accept_production, artifact_reference, inspect_production,
    validate_frame_evidence, verify_acceptance, write_json,
)
from scripts.extract_narration_frames import extract_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Technical checks only; never human approval.")
    inspect.add_argument("manifest", type=Path)
    inspect.add_argument("--output", type=Path, required=True)
    inspect.add_argument("--frames-dir", type=Path)
    accept = commands.add_parser("accept", help="Require current evidence and explicit human acceptance.")
    accept.add_argument("manifest", type=Path)
    accept.add_argument("--record", type=Path, required=True)
    accept.add_argument("--evidence", type=Path, required=True)
    accept.add_argument("--output", type=Path)
    accept.add_argument("--teaching-contract", type=Path)
    accept.add_argument("--teaching-validation", type=Path)
    verify = commands.add_parser("verify", help="Recheck a retained accepted record for staleness.")
    verify.add_argument("manifest", type=Path)
    verify.add_argument("--record", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            if args.output.exists():
                raise ReviewError("Review output already exists; choose a new record path.")
            record = inspect_production(args.manifest)
            if args.frames_dir:
                index = extract_review(
                    Path(record["artifacts"]["video"]["path"]),
                    Path(record["artifacts"]["timeline"]["path"]), args.frames_dir,
                )
                validate_frame_evidence(index, record)
                record["frame_evidence"] = artifact_reference(index)
            if args.output.exists():
                raise ReviewError("Review output overlaps an extracted artifact; choose a separate record path.")
            write_json(args.output, record)
            print(f"Technically verified (NOT human accepted): {args.output}")
        elif args.command == "accept":
            output = args.output or args.record.with_name(f"{args.record.stem}.accepted.json")
            if output.exists():
                raise ReviewError("Acceptance output already exists; preserve evidence and choose a fresh path.")
            record = accept_production(
                args.manifest, args.record, args.evidence,
                teaching_contract=args.teaching_contract, teaching_validation=args.teaching_validation,
            )
            write_json(output, record)
            print(f"Accepted by {record['human_review']['reviewer']}: {output}")
        else:
            record = verify_acceptance(args.manifest, args.record)
            print(f"Accepted evidence remains current for run {record['run_id']}: {args.record}")
    except (ReviewError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Review failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
