# Impressive sample

A short speculative-decoding explainer designed to demonstrate the repository's
visual language rather than merely display its components.

```powershell
$env:MANIM_TTS_PROVIDER = "gtts"
.\.venv\Scripts\python.exe -m manim render -qm `
  examples\impressive_sample\scene.py ImpressiveSample
```

Use `MANIM_TTS_PROVIDER=none` for a silent draft.
