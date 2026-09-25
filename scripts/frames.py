"""Extract labeled review frames and contact sheets; this does not approve a video."""

import argparse
import json
import math
from pathlib import Path
import sys

import av
from PIL import Image, ImageDraw, ImageFont


def extract(video: Path, output: Path, times: list[float]) -> dict:
    if output.exists():
        raise ValueError("Review output already exists; use a new directory.")
    if any(not math.isfinite(t) or t < 0 for t in times):
        raise ValueError("Frame times must be finite, nonnegative seconds.")
    with av.open(str(video)) as container:
        if not container.streams.video:
            raise ValueError("The file has no video stream.")
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 0)
        duration = float(stream.duration * stream.time_base) if stream.duration is not None else 0
        if not math.isfinite(duration) or duration <= 0 or not math.isfinite(fps) or fps <= 0:
            raise ValueError("Video duration/frame rate is unavailable or invalid.")
        if any(t >= duration for t in times):
            raise ValueError(f"Frame times must be below video duration ({duration:.3f}s).")
        end = max(0, duration - 1 / fps)
        targets = sorted(set([0.0, end, *times] if times else [end * i / 7 for i in range(8)]))
        output.mkdir(parents=True)
        samples, last = [], None

        def save(frame, requested):
            name = f"frame-{len(samples):03d}.jpg"
            frame.to_image().save(output / name, quality=95)
            samples.append({"requested": requested, "actual": float(frame.time), "file": name})

        for frame in container.decode(video=0):
            if frame.time is None:
                raise ValueError("Decoded video frame lacks a timestamp.")
            last = frame
            while len(samples) < len(targets) and frame.time >= targets[len(samples)]:
                save(frame, targets[len(samples)])
        if last is None:
            raise ValueError("Video decoded no frames.")
        while len(samples) < len(targets):
            target = targets[len(samples)]
            if target >= last.time + 1 / fps + 0.001:
                raise ValueError("Video ended before a requested review time.")
            save(last, target)
        report = {
            "video": str(video.resolve()), "duration": duration, "fps": fps,
            "width": stream.width, "height": stream.height,
            "has_audio": bool(container.streams.audio), "frames": samples,
        }
    font = ImageFont.load_default(size=18)
    sheets = []
    for start in range(0, len(samples), 12):
        batch = samples[start:start + 12]
        sheet = Image.new("RGB", (1200, 250 * math.ceil(len(batch) / 3)), "#eeeeee")
        draw = ImageDraw.Draw(sheet)
        for index, sample in enumerate(batch):
            x, y = (index % 3) * 400, (index // 3) * 250
            with Image.open(output / sample["file"]) as image:
                image.thumbnail((400, 225))
                sheet.paste(image, (x, y + 25))
            draw.text((x + 6, y + 3), f"{start + index}: {sample['actual']:.3f}s", font=font, fill="black")
        name = f"contact-{len(sheets) + 1:02d}.jpg"
        sheet.save(output / name, quality=92)
        sheets.append(name)
    report["contact_sheets"] = sheets
    (output / "frames.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new directory")
    parser.add_argument("--at", type=float, nargs="+", default=[], help="seconds; endpoints always included")
    args = parser.parse_args(argv)
    try:
        report = extract(args.video, args.output, args.at)
    except (OSError, ValueError, av.error.FFmpegError) as exc:
        print(f"Frame extraction failed: {exc}", file=sys.stderr)
        return 1
    print(f"Extracted {len(report['frames'])} frames to {args.output}. Open the sheets; also watch/listen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
