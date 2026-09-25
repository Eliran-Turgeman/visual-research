"""Cache short MAI-Voice-2 clips. Paid requests require explicit --generate."""

from array import array
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import wave

import imageio_ffmpeg


ENDPOINT = "https://openrouter.ai/api/v1/audio/speech"
SETTINGS = {
    "model": "microsoft/mai-voice-2",
    "voice": "en-US-Harper:MAI-Voice-2",
    "response_format": "mp3",
    "speed": 1.0,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def audio_stats(path: Path) -> dict:
    with wave.open(str(path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 48000):
            raise ValueError(f"Expected 48 kHz mono PCM16 speech: {path}")
        values = array("h", wav.readframes(wav.getnframes()))
        if len(values) != wav.getnframes() or not values:
            raise ValueError(f"Empty or truncated WAV: {path}")
        if sys.byteorder == "big":
            values.byteswap()
        duration = len(values) / wav.getframerate()
    rms = math.sqrt(sum(v * v for v in values) / len(values)) / 32768
    peak = max(abs(v) for v in values) / 32768
    if duration < 0.1 or rms < 0.001 or peak < 0.01:
        raise ValueError(f"Speech is too short or silent: {path}")
    return {"duration": duration, "rms": rms, "peak": peak}


def request_audio(body: dict) -> tuple[bytes, str | None]:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is missing; no speech request made.")
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            audio = response.read()
            content_type = response.headers.get("Content-Type", "")
            generation = response.headers.get("X-Generation-Id")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"MAI speech HTTP {exc.code}; no automatic paid retry.") from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError("MAI speech transport failure; no automatic paid retry.") from None
    if len(audio) < 512 or "json" in content_type:
        raise ValueError("MAI did not return plausible raw MP3 audio.")
    return audio, generation


def clip(body: dict, cache: Path, *, generate: bool) -> dict:
    key = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    mp3, wav, metadata = (cache / f"{key}.{ext}" for ext in ("mp3", "wav", "json"))
    if metadata.exists():
        entry = json.loads(metadata.read_text(encoding="utf-8"))
        if not isinstance(entry, dict):
            raise ValueError(f"Malformed speech cache metadata: {key}")
        if entry.get("request") != body or not mp3.is_file() or entry.get("mp3_sha256") != digest(mp3):
            raise ValueError(f"Altered/incomplete speech cache: {key}. Preserve it for inspection.")
    else:
        if mp3.exists() or wav.exists():
            raise ValueError(f"Audio without cache metadata: {key}. Preserve it for inspection.")
        if not generate:
            raise ValueError("Speech is not cached. Use --generate to authorize missing MAI requests.")
        audio, generation = request_audio(body)
        temporary = mp3.with_suffix(".part")
        temporary.write_bytes(audio)
        temporary.replace(mp3)
        entry = {"request": body, "generation_id": generation, "mp3_sha256": digest(mp3)}
        write_json(metadata, entry)
    if wav.exists():
        if entry.get("wav_sha256") != digest(wav):
            raise ValueError(f"Altered WAV cache: {key}. Preserve it for inspection.")
    else:
        # Retain the paid MP3 if conversion fails; the next run can retry locally.
        temporary = wav.with_suffix(".part.wav")
        result = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
             "-nostdin", "-y", "-i", str(mp3), "-ac", "1", "-ar", "48000",
             "-c:a", "pcm_s16le", str(temporary)],
            capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise ValueError(f"Speech conversion failed: {result.stderr.strip()}")
        audio_stats(temporary)
        temporary.replace(wav)
        entry["wav_sha256"] = digest(wav)
        write_json(metadata, entry)
    stats = audio_stats(wav)
    return {
        "request": body, "generation_id": entry.get("generation_id"),
        "wav": str(Path("cache") / wav.name), "wav_sha256": digest(wav), **stats,
    }


def prepare(storyboard: Path, output: Path, *, generate: bool = False, beat: str | None = None) -> dict:
    beats = json.loads(storyboard.read_text(encoding="utf-8-sig"))
    if not isinstance(beats, list) or not beats:
        raise ValueError("Storyboard must be a nonempty list.")
    ids = []
    for item in beats:
        if not isinstance(item, dict) or any(
            not isinstance(item.get(field), str) or not item[field].strip()
            for field in ("id", "narration")
        ):
            raise ValueError("Each beat needs nonblank id and narration strings.")
        ids.append(item["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("Beat IDs must be unique.")
    if beat is not None and beat not in ids:
        raise ValueError(f"Unknown beat: {beat}")
    cache = output / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    manifest = {"settings": SETTINGS, "beats": {}}
    for item in beats:
        body = {**SETTINGS, "input": item["narration"]}
        key = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        selected = beat is None or item["id"] == beat
        if not selected and not (cache / f"{key}.json").exists():
            continue
        entry = clip(body, cache, generate=generate and selected)
        manifest["beats"][item["id"]] = entry
        print(f"{item['id']}: {entry['duration']:.2f}s", flush=True)
    write_json(output / "manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", type=Path, help="JSON list of {id, narration} objects")
    parser.add_argument("--output", type=Path, help="audio directory; default: beside storyboard")
    parser.add_argument("--beat", help="prepare one beat; retain other valid current clips")
    parser.add_argument("--generate", action="store_true", help="permit missing paid MAI requests")
    args = parser.parse_args(argv)
    try:
        prepare(args.storyboard, args.output or args.storyboard.parent / "audio",
                generate=args.generate, beat=args.beat)
    except (OSError, ValueError, wave.Error, EOFError) as exc:
        print(f"Narration failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
