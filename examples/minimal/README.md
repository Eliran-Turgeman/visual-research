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

The default `MANIM_TTS_PROVIDER=none` creates a deterministic silent draft.
For narration, install a voiceover extra and set the provider:

```bash
MANIM_TTS_PROVIDER=gtts ./scripts/render.sh examples/minimal/scene.py MinimalExplainer
```
