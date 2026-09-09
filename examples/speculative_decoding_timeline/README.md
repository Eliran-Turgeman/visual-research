# Speculative decoding: latency timeline

A narrated comparison of autoregressive and speculative decoding on a shared
time scale. It shows why a prefix can become available sooner even after
including sequential drafting overhead.

## Visual argument

The last image is the design target: both lanes start at the same horizontal
position, but the same accepted prefix finishes earlier in the lower lane.
The completion guides and bracket establish the difference before "Less
waiting" appears. No percentage or measured speedup is claimed.

| Beat | Visible cause and effect | Approximate presentation time |
|---|---|---|
| Opening | A close-up progress boundary finishes before the first token appears | 0-5 s |
| Dependency | The same objects contract into a larger picture; two more dependent passes each release one token | 5-10 s |
| Draft | On the same clock, three short sequential steps produce outlined markers, then those same markers spread into token-position rows | 10-16 s |
| Uncertainty | The markers remain outlined; earlier drafts wait for the common target pass | 16-18 s |
| Verification | One boundary spans all rows simultaneously | 18-23 s |
| Discovery | The same markers become solid at the common completion point; a bracket reveals saved waiting before the caption | 23-30 s |

Durations are targets, not hard cuts. The scene uses actual speech durations,
short fixed transitions, and a matching silent pacing fallback.

## Semantics and assumptions

- A target pass costs 1 illustrative time unit; three passes cost 3.
- Each draft step costs 0.2 units; three sequential steps cost 0.6.
- The batched target pass costs 1 unit, so completion is at 1.6 including drafting.
- Horizontal distance uses this same scale in both lanes. Zooming the opening
  is a presentation change, not a latency claim.
- Circle outlines mean tentative tokens; solid circles mean accepted tokens.
- The vertically separated verification rows are token positions, not separate
  sequential target passes. A shared progress boundary evaluates them together.
- All three candidates happen to be accepted. Rejection, correction sampling,
  and any additional target token are outside this small example; only the
  availability of the three-token prefix is compared.
- This is standard sequential speculative drafting, not DFlash block drafting.

Mechanism reference: [Leviathan et al., Fast Inference from Transformers via
Speculative Decoding](https://arxiv.org/abs/2211.17192). These toy timings and
visuals are original, not measurements or figures from the paper.

## Render

From the repository root in PowerShell, use the isolated environment:

```powershell
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
$env:MANIM_TTS_PROVIDER = "gtts"
$env:MANIM_QUALITY = "-qh"
.\scripts\render.ps1 examples\speculative_decoding_timeline\scene.py SpeculativeDecodingTimeline
```

The result is `media\videos\scene\1080p60\SpeculativeDecodingTimeline.mp4`. gTTS requires
network access; generated speech is cached under `media\voiceovers\`.
Use `MANIM_TTS_PROVIDER=openrouter` with the configured key for the production
MAI-Voice-2 / Harper voice. The sample uses gTTS when that key is unavailable;
this does not change the repository's preferred production provider.

For the rough silent cut, set `MANIM_TTS_PROVIDER=none` and `MANIM_QUALITY=-ql`.
Output then goes to `media\videos\scene\480p15\SpeculativeDecodingTimeline.mp4`.
Keep the rough-cut frame index before rendering again: the scene overwrites its
review timeline on each run.

The sample intentionally pairs Georgia token words with Segoe UI annotations.
Both are present on the rendering Windows host; install these fonts or choose
an available equivalent explicitly when reproducing on another platform.
The three text roles use optically adjusted scene-local sizes: 18-22 for
context, 28 for token words, and 32-34 for the opening and payoff. The opening
close-up scales its continuing mechanism together, not individual labels.

## Review

```powershell
.\.venv\Scripts\python.exe scripts\extract_narration_frames.py `
  media\videos\scene\1080p60\SpeculativeDecodingTimeline.mp4 `
  media\review\speculative_decoding_timeline\timeline.json `
  media\review\speculative_decoding_timeline\final
```

This produces near-start/middle/near-end frames for every narration block.
Review the continuous motion as well: the first pass must finish before its
token appears, draft steps must remain sequential, and the verification
boundary must span all rows at once. The rough cut should convey the
relationship without its soundtrack. `tests\test_speculative_decoding_timeline.py` uses the
scene's real objects to guard the shared scale, identity, and layouts.
