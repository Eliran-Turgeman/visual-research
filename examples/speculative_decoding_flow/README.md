# Speculative decoding: model and token flow

A short flow-diagram example using model blocks, token states, and a target-call
counter to contrast serial generation with batched verification.

This schematic assumes a block-parallel drafter and an all-accepted batch.
For standard sequential drafting and explicit drafting overhead, see
[`speculative_decoding_timeline`](../speculative_decoding_timeline/README.md).

```powershell
$env:MANIM_TTS_PROVIDER = "gtts"
.\.venv\Scripts\python.exe -m manim render -qm `
  examples\speculative_decoding_flow\scene.py SpeculativeDecodingFlow
```

Use `MANIM_TTS_PROVIDER=none` for a silent draft.

This command writes
`media\videos\scene\720p30\SpeculativeDecodingFlow.mp4`.
