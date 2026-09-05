# Minimal example

`MinimalExplainer` shows three speculative token proposals becoming accepted
tokens. It demonstrates progressive construction, semantic token components,
an in-place state transformation, and narration blocks synchronized with their
visual actions.

From the repository root:

```bash
./scripts/render.sh examples/minimal/scene.py MinimalExplainer
```

On PowerShell:

```powershell
.\scripts\render.ps1 examples\minimal\scene.py MinimalExplainer
```

With `OPENROUTER_API_KEY` set, the example uses
`microsoft/mai-voice-2` and `en-US-Harper:MAI-Voice-2` automatically:

```bash
./scripts/render.sh examples/minimal/scene.py MinimalExplainer
```

Set `MANIM_TTS_PROVIDER=none` for a deterministic silent draft. Other
OpenRouter models and voices can be selected with `OPENROUTER_TTS_MODEL` and
`OPENROUTER_TTS_VOICE`.
