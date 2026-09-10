"""Artifact-bound technical checks and explicit, attributed human acceptance.

This module does not import the rendering module. Explicit teaching bindings
lazily invoke the pure teaching validator against the actual bound inputs.
``inspect_production`` only verifies technical evidence; it cannot judge speech,
visual quality, correctness of a lesson, or viewer comprehension.

Timing tolerances: timeline arithmetic uses 1 ms; encoded media comparisons use
the larger of 100 ms and two video frames (codec/container rounding). Hashes
bind bytes, not authorship. Human review records are attestations, not signatures.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReviewError(ValueError):
    """Missing, invalid, or stale evidence prevents review/acceptance."""


def sha256_file(path: Path) -> str:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            raise ReviewError(f"Artifact is missing or empty: {path}")
        with path.open("rb") as source:
            return hashlib.file_digest(source, "sha256").hexdigest()
    except OSError as exc:
        raise ReviewError(f"Cannot read artifact {path}: {exc}") from exc


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReviewError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReviewError(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict) -> None:
    """Atomically publish complete evidence beside its final destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(f".{path.name}.{uuid.uuid4().hex}.writing")
    try:
        with staging.open("x", encoding="utf-8") as target:
            target.write(json.dumps(data, indent=2, allow_nan=False) + "\n")
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def finite_number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ReviewError(f"{field} must be a finite number.")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ReviewError(f"{field} must be a finite number.") from exc
    if not math.isfinite(value):
        raise ReviewError(f"{field} must be a finite number.")
    if positive and value <= 0:
        raise ReviewError(f"{field} must be positive.")
    return value


def resolve_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise ReviewError(
            "FFmpeg is unavailable; install FFmpeg or the existing imageio-ffmpeg fallback."
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def media_tolerance(fps: float | None) -> float:
    return max(0.1, 2.0 / fps) if fps and fps > 0 else 0.1


def probe_media(path: Path) -> dict:
    """Probe stream durations with ffprobe, or Manim's existing PyAV dependency."""
    sha256_file(path)
    ffprobe = shutil.which("ffprobe")
    try:
        if ffprobe:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
                check=True, capture_output=True, text=True,
            )
            streams = json.loads(result.stdout)["streams"]
            video = next((s for s in streams if s.get("codec_type") == "video"), None)
            audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

            def duration(stream):
                return float(stream["duration"]) if stream else None

            def start(stream):
                return float(stream.get("start_time", 0)) if stream else None

            fps = None
            if video:
                numerator, denominator = video["avg_frame_rate"].split("/")
                fps = float(numerator) / float(denominator)
            result = {
                "video_duration": duration(video), "audio_duration": duration(audio),
                "video_start": start(video), "audio_start": start(audio), "fps": fps,
            }
        else:
            import av

            with av.open(str(path)) as container:
                video = next(iter(container.streams.video), None)
                audio = next(iter(container.streams.audio), None)

                def duration(stream):
                    if stream is None:
                        return None
                    if stream.duration is None:
                        raise ReviewError(f"Cannot determine stream duration: {path}")
                    return float(stream.duration * stream.time_base)

                def start(stream):
                    return float((stream.start_time or 0) * stream.time_base) if stream else None

                result = {
                    "video_duration": duration(video), "audio_duration": duration(audio),
                    "video_start": start(video), "audio_start": start(audio),
                    "fps": float(video.average_rate) if video and video.average_rate else None,
                }
    except (ImportError, OSError, ValueError, KeyError, ZeroDivisionError, subprocess.SubprocessError) as exc:
        raise ReviewError(f"Cannot probe media {path}: {exc}") from exc
    for field in ("video_duration", "audio_duration", "fps"):
        if result[field] is not None:
            finite_number(result[field], field, positive=True)
    for field in ("video_start", "audio_start"):
        if result[field] is not None:
            finite_number(result[field], field)
    if result["video_duration"] is not None and result["fps"] is None:
        raise ReviewError(f"Cannot determine video frame rate: {path}")
    return result


def validate_video_timing(media: dict, scene_duration: float, *, require_audio: bool = False) -> None:
    duration = media.get("video_duration")
    if duration is None:
        raise ReviewError("Media has no video stream.")
    tolerance = media_tolerance(media.get("fps"))
    if abs(duration - scene_duration) > tolerance + 1e-6:
        raise ReviewError(
            f"Video duration {duration:.6f}s does not match scene_duration "
            f"{scene_duration:.6f}s (tolerance {tolerance:.6f}s)."
        )
    if abs(media.get("video_start") or 0) > tolerance:
        raise ReviewError("Video must start at scene time zero.")
    if require_audio:
        if media.get("audio_duration") is None:
            raise ReviewError("Production media requires an audio stream.")
        if abs(media.get("audio_start") or 0) > tolerance:
            raise ReviewError("Production audio must start at scene time zero (pad leading silence).")
        audio_end = (media.get("audio_start") or 0) + media["audio_duration"]
        if abs(audio_end - duration) > tolerance + 1e-6:
            raise ReviewError("Production audio duration must cover the full video (pad trailing silence).")


def validate_decode(path: Path) -> None:
    """Decode the complete media, failing on decoder errors, not just a header."""
    try:
        subprocess.run(
            [resolve_ffmpeg(), "-v", "error", "-xerror", "-i", str(path),
             "-map", "0:v:0?", "-map", "0:a:0?", "-f", "null", "-"],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ReviewError(f"Media decode failed for {path}: {exc.stderr.strip()}") from exc


def artifact_reference(path: Path) -> dict:
    path = path.resolve()
    return {"path": str(path), "sha256": sha256_file(path)}


def verify_reference(reference: object, base: Path, label: str) -> Path:
    if not isinstance(reference, dict):
        raise ReviewError(f"Missing {label} artifact reference.")
    raw_path, digest = reference.get("path"), reference.get("sha256")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ReviewError(f"{label} requires a path.")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ReviewError(f"{label} requires a lowercase SHA-256 digest.")
    path = (base / raw_path).resolve()
    if sha256_file(path) != digest:
        raise ReviewError(f"Stale {label}: SHA-256 mismatch for {path}.")
    return path


def _verify_audio_snapshots(artifacts: dict, timeline: dict, manifest_dir: Path, timeline_dir: Path) -> list[dict]:
    def references(raw: object, base: Path, label: str) -> list[dict]:
        if not isinstance(raw, list):
            raise ReviewError(f"{label} must be a list of audio artifact references.")
        return [
            {"path": str(verify_reference(ref, base, label)), "sha256": ref["sha256"]}
            for ref in raw
        ]

    declared = references(artifacts["audio"], manifest_dir, "manifest audio") if "audio" in artifacts else None
    if declared == []:
        raise ReviewError("Manifest audio must be omitted when no actual audio snapshots exist.")
    recorded = [
        ref for block in timeline["blocks"] if "audio" in block
        for ref in references(block["audio"], timeline_dir, f"block {block['index']} audio")
    ]
    if declared is not None and any(ref not in declared for ref in recorded):
        raise ReviewError("Timeline audio snapshot is absent from the manifest audio artifacts.")
    result = []
    for ref in declared if declared is not None else recorded:
        if ref not in result:
            result.append(ref)
    return result


def inspect_production(manifest_path: Path) -> dict:
    """Verify manifest identity, artifact hashes, timeline, durations and decode."""
    from scripts.extract_narration_frames import validate_timeline

    manifest_path = manifest_path.resolve()
    manifest_reference = artifact_reference(manifest_path)
    manifest = read_json(manifest_path)
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ReviewError("Manifest schema_version must be 1.")
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ReviewError("Manifest requires a nonblank run_id.")
    if manifest.get("profile") not in ("draft", "production"):
        raise ReviewError("Manifest profile must be draft or production.")
    if manifest.get("status") != "rendered":
        raise ReviewError("Manifest status must be rendered; review is a separate record.")
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ReviewError("Manifest artifacts must be an object.")
    video = verify_reference(artifacts.get("video"), manifest_path.parent, "video")
    timeline_path = verify_reference(artifacts.get("timeline"), manifest_path.parent, "timeline")
    timeline_document = read_json(timeline_path)
    timeline = validate_timeline(timeline_document)
    if timeline.run_id != run_id:
        raise ReviewError("Timeline run_id must match manifest run_id (legacy extraction is still supported).")
    audio = _verify_audio_snapshots(artifacts, timeline_document, manifest_path.parent, timeline_path.parent)
    media = probe_media(video)
    validate_video_timing(media, timeline.scene_duration, require_audio=manifest["profile"] == "production")
    validate_decode(video)
    for key in ("video", "timeline"):
        verify_reference(artifacts[key], manifest_path.parent, key)
    _verify_audio_snapshots(artifacts, timeline_document, manifest_path.parent, timeline_path.parent)
    if artifact_reference(manifest_path) != manifest_reference:
        raise ReviewError("Manifest changed during inspection.")
    return {
        "schema_version": 1, "run_id": run_id, "profile": manifest["profile"],
        "status": "technically_verified", "created_at": utc_now(),
        "manifest": manifest_reference,
        "artifacts": {
            "video": artifact_reference(video), "timeline": artifact_reference(timeline_path),
            **({"audio": audio} if audio else {}),
        },
        "media": media,
        "technical": {"status": "passed", "checks": [
            "artifact_hashes", "run_identity", "timeline", "media_duration", "full_decode",
            * (["audio_presence_and_duration"] if manifest["profile"] == "production" else []),
            * (["audio_snapshot_hashes"] if audio else []),
        ]},
        "human_review": None,
    }


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ReviewError(f"{label} requires an ISO-8601 timestamp with timezone.")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewError(f"{label} requires an ISO-8601 timestamp.") from exc
    if result.tzinfo is None or result > datetime.now(timezone.utc):
        raise ReviewError(f"{label} must have a timezone and must not be in the future.")
    return result


def validate_human_evidence(evidence: dict, record: dict, record_sha256: str) -> None:
    """Require explicit review of this exact record; never infer human approval."""
    if type(evidence.get("schema_version")) is not int or evidence["schema_version"] != 1:
        raise ReviewError("Human evidence schema_version must be 1.")
    if evidence.get("run_id") != record["run_id"] or evidence.get("review_sha256") != record_sha256:
        raise ReviewError("Human evidence is stale: run_id/review_sha256 must bind the current review record.")
    reviewer = evidence.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ReviewError("Human evidence requires reviewer attribution.")
    reviewed_at = _timestamp(evidence.get("reviewed_at"), "reviewed_at")
    if reviewed_at < _timestamp(record.get("created_at"), "record.created_at"):
        raise ReviewError("Human review predates the technical review record.")
    if evidence.get("decision") != "accept":
        raise ReviewError("Human acceptance requires decision='accept'.")
    confirmations = evidence.get("confirmations")
    required = ["watched_full_video", "visual_quality", "synchronization", "teaching_correctness"]
    if record["profile"] == "production":
        required.append("listened_full_audio")
    if not isinstance(confirmations, dict) or any(confirmations.get(key) is not True for key in required):
        raise ReviewError(f"Explicit human confirmations required: {', '.join(required)}.")
    for label in ("audiovisual_notes", "teaching_notes"):
        if not isinstance(evidence.get(label), str) or not evidence[label].strip():
            raise ReviewError(f"Human evidence requires nonblank {label}.")
    findings = evidence.get("findings")
    if not isinstance(findings, list):
        raise ReviewError("Human findings must be an explicit list (empty only when none were found).")
    finding_ids = set()
    for position, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ReviewError(f"Finding {position} must be an object.")
        for field in ("id", "description", "expected_behavior"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise ReviewError(f"Finding {position} requires {field}.")
        if finding["id"] in finding_ids:
            raise ReviewError(f"Duplicate finding id: {finding['id']}.")
        finding_ids.add(finding["id"])
        if finding.get("severity") not in ("blocker", "major", "minor", "info"):
            raise ReviewError(f"Finding {position} has invalid severity.")
        time = finite_number(finding.get("time_seconds"), f"Finding {position} time_seconds")
        if not 0 <= time <= record["media"]["video_duration"]:
            raise ReviewError(f"Finding {position} time_seconds is outside the video.")
        if finding.get("status") not in ("open", "resolved"):
            raise ReviewError(f"Finding {position} status must be open or resolved.")
        if finding["status"] == "resolved":
            for field in ("resolution", "resolved_by"):
                if not isinstance(finding.get(field), str) or not finding[field].strip():
                    raise ReviewError(f"Resolved finding {position} requires {field}.")
            resolved_at = _timestamp(finding.get("resolved_at"), "resolved_at")
            if not _timestamp(record.get("created_at"), "record.created_at") <= resolved_at <= reviewed_at:
                raise ReviewError("Finding resolution must occur between technical and human review.")
        elif finding["severity"] in ("blocker", "major"):
            raise ReviewError(f"Unresolved {finding['severity']} finding prevents acceptance: {finding['id']}.")


def _validate_teaching_binding(
    contract_path: Path, validation_path: Path, record: dict, evidence: dict,
) -> dict:
    from manim_lib.teaching import loads_contract, validate_contract

    validation_reference = artifact_reference(validation_path)
    envelope = read_json(validation_path)
    if type(envelope.get("schema_version")) is not int or envelope["schema_version"] != 1:
        raise ReviewError("Teaching validation schema_version must be 1.")
    result = envelope.get("validation")
    if (
        envelope.get("status") != "passed" or not isinstance(result, dict)
        or result.get("valid") is not True or result.get("errors") != []
    ):
        raise ReviewError("Teaching validation requires status=passed, validation.valid=true and no errors.")
    bound_contract = verify_reference(envelope.get("contract"), validation_path.parent, "teaching contract")
    if bound_contract != contract_path.resolve():
        raise ReviewError("Teaching validation references a different contract.")
    verify_reference(envelope.get("timeline"), validation_path.parent, "teaching timeline")
    if envelope["timeline"]["sha256"] != record["artifacts"]["timeline"]["sha256"]:
        raise ReviewError("Teaching validation timeline differs from the reviewed manifest timeline.")
    if envelope.get("run_id") != record["run_id"]:
        raise ReviewError("Teaching validation requires the reviewed run_id (legacy unbound reports cannot be accepted).")
    timeline_reference = record["artifacts"]["timeline"]
    timeline_path = verify_reference(timeline_reference, validation_path.parent, "manifest timeline")
    contract_reference = artifact_reference(contract_path)
    if evidence.get("teaching_contract_sha256") != contract_reference["sha256"]:
        raise ReviewError("Human evidence must bind teaching_contract_sha256 explicitly.")

    def bound_document(path: Path, digest: str) -> dict:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReviewError(f"Cannot read bound teaching input {path}: {exc}") from exc
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ReviewError(f"Bound teaching input changed: {path}.")
        try:
            return loads_contract(raw.decode("utf-8-sig"))
        except ValueError as exc:
            raise ReviewError(f"Invalid bound teaching input {path}: {exc}") from exc

    recomputed = validate_contract(
        bound_document(contract_path, contract_reference["sha256"]),
        timeline=bound_document(timeline_path, timeline_reference["sha256"]),
    )
    if not recomputed["valid"]:
        details = "; ".join(
            f"{error['code']} at {error['path']}: {error['message']}"
            for error in recomputed["errors"]
        )
        raise ReviewError(f"Recomputed teaching validation failed: {details}")
    if artifact_reference(validation_path) != validation_reference:
        raise ReviewError("Teaching validation changed during acceptance.")
    if (
        envelope["contract"]["sha256"] != contract_reference["sha256"]
        or artifact_reference(contract_path) != contract_reference
    ):
        raise ReviewError("Teaching contract changed during acceptance.")
    verify_reference(timeline_reference, validation_path.parent, "manifest timeline")
    return {
        "contract": contract_reference, "validation": validation_reference,
        "recomputed_validation": recomputed,
    }


def accept_production(
    manifest_path: Path, record_path: Path, evidence_path: Path,
    *, teaching_contract: Path | None = None, teaching_validation: Path | None = None,
) -> dict:
    """Recheck current artifacts and return a separate human acceptance record.

    Evidence format: schema_version, run_id, review_sha256, reviewer, reviewed_at,
    decision='accept', confirmations (watched_full_video, listened_full_audio,
    visual_quality, synchronization, teaching_correctness), audiovisual_notes,
    teaching_notes, findings. Every finding has id, time_seconds, severity
    (blocker/major/minor/info), description, expected_behavior, status (open or
    resolved); resolved findings also require resolution/resolved_by/resolved_at.
    Both open blocker and open major findings prevent acceptance.
    When binding a teaching contract, evidence.teaching_contract_sha256 must
    explicitly name its digest. The validation artifact must contain
    schema_version=1, status='passed', matching run_id, contract and timeline
    {path, sha256} references, and validation={valid: true, errors: [], ...}.
    Its timeline hash must match the manifest; raw/unbound validator output
    cannot authorize acceptance. Both acceptance and later verification rerun
    teaching.validate_contract on the hash-bound contract and actual manifest
    timeline. The independent result is retained as teaching.recomputed_validation.
    Source text is not loaded or fetched: source/event omissions and all human
    judgment boundaries remain explicit in that result, never assumed passed.
    Preserve the original technical record and validation envelope files.
    """
    record = read_json(record_path)
    record_digest = sha256_file(record_path)
    if record.get("schema_version") != 1 or record.get("status") != "technically_verified":
        raise ReviewError("Acceptance requires a technically_verified review record.")
    verify_reference(record.get("manifest"), record_path.parent, "review manifest")
    current = inspect_production(manifest_path)
    for field in ("run_id", "profile", "manifest", "artifacts", "media", "technical"):
        if record.get(field) != current[field]:
            raise ReviewError(f"Review record is stale or altered: {field} differs.")
    frames = record.get("frame_evidence")
    if frames is None:
        raise ReviewError("Acceptance requires frame_evidence; run inspect with --frames-dir.")
    index_path = verify_reference(frames, record_path.parent, "frame index")
    validate_frame_evidence(index_path, current)
    evidence_reference = artifact_reference(evidence_path)
    evidence = read_json(evidence_path)
    validate_human_evidence(evidence, record, record_digest)
    if (teaching_contract is None) != (teaching_validation is None):
        raise ReviewError("Provide both teaching contract and teaching validation artifacts.")
    if teaching_contract is not None:
        record["teaching"] = _validate_teaching_binding(teaching_contract, teaching_validation, record, evidence)
    record.update(
        status="accepted", accepted_at=utc_now(), technical_review_sha256=record_digest,
        technical_review={"path": str(record_path.resolve()), "sha256": record_digest},
        human_review=evidence, human_evidence=evidence_reference,
    )
    if sha256_file(record_path) != record_digest or artifact_reference(evidence_path) != evidence_reference:
        raise ReviewError("Technical record or human evidence changed during acceptance.")
    return record


def verify_acceptance(manifest_path: Path, accepted_path: Path) -> dict:
    """Revalidate durable acceptance and every retained source of evidence."""
    accepted = read_json(accepted_path)
    if accepted.get("status") != "accepted":
        raise ReviewError("Record is not accepted.")
    technical_path = verify_reference(accepted.get("technical_review"), accepted_path.parent, "technical review")
    human_path = verify_reference(accepted.get("human_evidence"), accepted_path.parent, "human evidence")
    contract, validation = None, None
    if "teaching" in accepted:
        teaching = accepted["teaching"]
        if not isinstance(teaching, dict):
            raise ReviewError("Teaching binding must be an object.")
        contract = verify_reference(teaching.get("contract"), accepted_path.parent, "teaching contract")
        validation = verify_reference(teaching.get("validation"), accepted_path.parent, "teaching validation")
    expected = accept_production(
        manifest_path, technical_path, human_path,
        teaching_contract=contract, teaching_validation=validation,
    )
    for key, value in expected.items():
        if key != "accepted_at" and accepted.get(key) != value:
            raise ReviewError(f"Accepted record was altered: {key}.")
    accepted_at = _timestamp(accepted.get("accepted_at"), "accepted_at")
    if accepted_at < _timestamp(accepted["human_review"]["reviewed_at"], "reviewed_at"):
        raise ReviewError("Acceptance predates human review.")
    return accepted


def validate_frame_evidence(index_path: Path, record: dict) -> dict:
    """Require complete frame evidence for the exact current video and timeline."""
    from scripts.extract_narration_frames import build_index, validate_timeline, verify_jpeg

    index = read_json(index_path)
    if index.get("run_id") != record["run_id"]:
        raise ReviewError("Frame evidence run_id differs from the manifest.")
    for key in ("video", "timeline"):
        if index.get("artifacts", {}).get(key) != record["artifacts"][key]:
            raise ReviewError(f"Frame evidence is stale: {key} differs.")
    timeline = validate_timeline(read_json(Path(record["artifacts"]["timeline"]["path"])))
    expected = build_index(
        timeline, index_path.parent / "frames", fps=record["media"]["fps"],
        media_duration=record["media"]["video_duration"],
        max_frames=index.get("max_frames", 512),
    )
    actual = index.get("frames")
    if not isinstance(actual, list) or len(actual) != len(expected) or index.get("frame_count") != len(expected):
        raise ReviewError("Frame evidence is incomplete.")
    for wanted, frame in zip(expected, actual):
        if not isinstance(frame, dict) or any(frame.get(k) != v for k, v in wanted.items()):
            raise ReviewError("Frame evidence sampling plan is stale or incomplete.")
        verify_reference({"path": frame["file"], "sha256": frame.get("sha256")}, index_path.parent, "frame")
        verify_jpeg(Path(frame["file"]))
    for sheet in index.get("contact_sheets", []):
        verify_reference(sheet, index_path.parent, "contact sheet")
    return index
