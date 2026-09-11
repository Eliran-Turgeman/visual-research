"""Check retained smoke artifacts without installing pytest or TTS extras."""

from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path


OPTIONAL_DISTRIBUTIONS = (
    "pytest", "manim-voiceover", "openai", "gTTS", "azure-cognitiveservices-speech",
)


def verify_base_environment() -> None:
    unexpected = []
    for distribution in OPTIONAL_DISTRIBUTIONS:
        try:
            metadata.version(distribution)
        except metadata.PackageNotFoundError:
            continue
        unexpected.append(distribution)
    if unexpected:
        raise ValueError(f"Smoke environment is not base-only: {', '.join(unexpected)}")


def verify_run(run_dir: Path) -> None:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    timeline = json.loads((run_dir / "timeline.json").read_text(encoding="utf-8"))
    if manifest["status"] != "rendered":
        raise ValueError("Smoke manifest is not rendered")
    if manifest["run_id"] != run_dir.name or timeline["run_id"] != run_dir.name:
        raise ValueError("Smoke run IDs do not match")
    if manifest["scene_name"] != "InstallationSmoke":
        raise ValueError("Wrong smoke scene")
    if manifest["profile"] != "draft" or manifest["settings"]["provider"] != "none":
        raise ValueError("Smoke render must be a silent draft")
    for name, filename in (("video", "video.mp4"), ("timeline", "timeline.json")):
        artifact = manifest["artifacts"][name]
        path = run_dir / filename
        if artifact["path"] != filename or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing or unexpected {name} artifact")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if artifact["sha256"] != digest:
            raise ValueError(f"Smoke {name} hash does not match")
    video = manifest["artifacts"]["video"]
    if video["has_audio"] is not False:
        raise ValueError("Silent smoke video contains audio")
    if not (video["duration"] > 0 and video["frame_rate"] > 0):
        raise ValueError("Smoke video has invalid timing")
    if not (video["width"] > 0 and video["height"] > 0):
        raise ValueError("Smoke video has invalid dimensions")
    tolerance = max(0.15, 2 / video["frame_rate"])
    if abs(video["duration"] - timeline["scene_duration"]) > tolerance:
        raise ValueError("Smoke video and timeline durations do not match")
    if not timeline["blocks"] or not timeline["events"]:
        raise ValueError("Smoke timeline has no narration blocks or visual events")
    if timeline["blocks"][0]["beat_id"] != "installation":
        raise ValueError("Smoke timeline does not identify the installation beat")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    verify_base_environment()
    verify_run(args.run_dir)
    print(f"Verified silent managed render: {args.run_dir}")


if __name__ == "__main__":
    main()
