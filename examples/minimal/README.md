# Minimal example

`MinimalExplainer` shows three speculative token proposals becoming accepted
tokens. It demonstrates progressive construction, semantic token components,
an in-place state transformation, and narration blocks synchronized with their
visual actions.

First follow the [root quick start](../../README.md#quick-start) to install
native prerequisites and run the platform's setup wrapper. The commands below
automatically select the resulting `.venv`; no activation, API keys, or LaTeX
are needed for this `Text`-based silent example.

The scene uses `NarratedScene` and records three teaching beats (`context`,
`draft-proposals`, `verification`) with corresponding visual events. From the
repository root, make the managed draft settings explicit:

```bash
./scripts/render.sh examples/minimal/scene.py MinimalExplainer \
  --profile draft --provider none --output-dir media/runs --run-id minimal-draft-01
```

On PowerShell:

```powershell
.\scripts\render.ps1 examples\minimal\scene.py MinimalExplainer `
  --profile draft --provider none --output-dir media\runs --run-id minimal-draft-01
```

Credentials alone must not select paid narration in managed wrappers.
The run preserves `video.mp4`, `timeline.json`, and `manifest.json` under
`media\runs\minimal-draft-01\`. Choose a fresh run ID each time.

For narrated production, install the optional dependencies with
`.\scripts\setup.ps1 --provider openrouter` (or
`./scripts/setup.sh --provider openrouter`), configure the OpenRouter key in
the process, then:

```powershell
.\scripts\render.ps1 examples\minimal\scene.py MinimalExplainer `
  --profile production --provider openrouter `
  --output-dir media\runs --run-id minimal-production-01
```

See the [root production workflow](../../README.md#render-a-managed-episode)
for profile options and review requirements.
OpenRouter's selected service defaults to `microsoft/mai-voice-2` /
`en-US-Harper:MAI-Voice-2`; model and voice overrides are
`OPENROUTER_TTS_MODEL` and `OPENROUTER_TTS_VOICE`.

Direct Manim remains available without a managed manifest:

```powershell
$env:MANIM_TTS_PROVIDER = "none"
.\.venv\Scripts\python.exe -m manim -ql examples\minimal\scene.py MinimalExplainer
```

This is a component/narration example, not a complete treatment of speculative
decoding. Use [the timeline example](../speculative_decoding_timeline/README.md)
for drafting overhead and conditional acceptance. Rendering alone does not
establish technical, audiovisual, or teaching acceptance.
