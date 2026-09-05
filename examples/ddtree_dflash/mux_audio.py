"""Mux externally timed narration tracks into a rendered Manim video."""

import json
from pathlib import Path
import shutil
import subprocess
import sys


def ffmpeg_executable() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise SystemExit(
            "FFmpeg was not found. Install FFmpeg or `pip install imageio-ffmpeg`."
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: mux_audio.py SILENT_VIDEO OUTPUT_VIDEO")

    video = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    manifest_path = Path("media/voiceovers/ddtree_external/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tracks = manifest["tracks"]
    if not tracks:
        raise SystemExit("The narration manifest contains no tracks.")

    command = [ffmpeg_executable(), "-y", "-i", str(video)]
    for track in tracks:
        command.extend(["-i", track["file"]])

    delayed = []
    filters = []
    for index, track in enumerate(tracks, start=1):
        label = f"a{index}"
        delay_ms = round(track["start"] * 1000)
        filters.append(
            f"[{index}:a]adelay=delays={delay_ms}:all=1[{label}]"
        )
        delayed.append(f"[{label}]")
    filters.append(
        "".join(delayed)
        + f"amix=inputs={len(delayed)}:duration=longest:normalize=0[aout]"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output),
        ]
    )
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
