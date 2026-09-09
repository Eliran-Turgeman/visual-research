"""Pre-cache the episode using the same MAI service/cache as Manim Voiceover."""

import json
from pathlib import Path

import av

from examples.ddtree_full.storyboard import BEATS
from manim_lib.openrouter_voiceover import OpenRouterSpeechService


def main():
    service = OpenRouterSpeechService(speed=0.96)
    tracks = []
    for index, beat in enumerate(BEATS):
        # Use Voiceover's wrapper so the render finds the identical cache entry.
        result = service._wrap_generate_from_text(beat.narration)
        audio_path = Path(service.cache_dir) / result["final_audio"]
        with av.open(str(audio_path)) as audio:
            duration = float(audio.duration / av.time_base)
        tracks.append({
            "index": index,
            "chapter": beat.chapter,
            "text": beat.narration,
            "file": str(audio_path.resolve()),
            "duration": duration,
        })
        print(f"MAI segment {index + 1}/{len(BEATS)}: {duration:.2f}s", flush=True)
    output = Path("media/review/ddtree_full/narration.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "provider": "openrouter",
        "model": service.model,
        "voice": service.voice,
        "speed": service.speed,
        "speech_duration": sum(track["duration"] for track in tracks),
        "tracks": tracks,
    }, indent=2), encoding="utf-8")
    print(f"Narration manifest: {output}", flush=True)


if __name__ == "__main__":
    main()
