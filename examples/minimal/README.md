# Minimal example

`MinimalExplainer` shows three speculative token proposals becoming accepted
tokens. It demonstrates progressive construction, semantic token components,
an in-place state transformation, and narration blocks synchronized with their
visual actions.

From the repository root, make the draft settings explicit:

```bash
MANIM_TTS_PROVIDER=none python -m manim -ql examples/minimal/scene.py MinimalExplainer
```

On PowerShell:

```powershell
$env:MANIM_TTS_PROVIDER = "none"
python -m manim -ql examples\minimal\scene.py MinimalExplainer
```

Credentials alone must not select paid narration in managed wrappers.
This scene's legacy narrator does not emit the managed timeline protocol, so
these commands deliberately use the direct-Manim escape hatch.
For a managed narrated production example, follow the
[root production workflow](../../README.md#render-a-managed-episode).
OpenRouter's selected service defaults to `microsoft/mai-voice-2` /
`en-US-Harper:MAI-Voice-2`; model and voice overrides are
`OPENROUTER_TTS_MODEL` and `OPENROUTER_TTS_VOICE`.

This is a component/narration example, not a complete treatment of speculative
decoding. Use [the timeline example](../speculative_decoding_timeline/README.md)
for drafting overhead and conditional acceptance. Rendering alone does not
establish technical, audiovisual, or teaching acceptance.
