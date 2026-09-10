# DFlash Visual Explainer

A focused standalone episode explaining **DFlash** (block-parallel speculative
drafting) to engineers with rusty math. One evolving picture, no slides.

## What the viewer learns

1. Why autoregressive decoding is sequential and slow.
2. How a standard drafter fills slots one-by-one.
3. How DFlash predicts a masked future block in **one parallel pass**.
4. How target hidden features condition the small draft model (K/V injection).
5. Why per-position marginals share context, but not earlier draft choices.
6. How the target model verifies proposals in one pass.
7. Why a mismatch discards the entire suffix, even a later matching token.
8. Why target-driven decisions preserve **greedy output**, while the target
   bonus separately guarantees progress.
9. Brief bridge to DDTree as the next episode.

## Decoding regime and worked example

This episode demonstrates **greedy decoding (temperature = 0)**, not a
stochastic acceptance/rejection algorithm. Draft tokens and target decisions
are argmax choices. All probabilities are **toy values**, not measurements,
acceptance rates, or reported DFlash performance.

With committed context `We see`, the draft proposes `the model works`.
One causal target pass computes the following choices:

| Position | Draft | Target argmax | Target's conditioning suffix | Action |
|---|---|---|---|---|
| 1 | the | the | empty | Accept |
| 2 | model | system | the | First miss; take target's system |
| 3 | works | works | the model | Discard despite the apparent match |
| 4 | — | well | the model works | Unused; this is after the wrong prefix |

The accepted prefix has length **k = 1**, not two independent matches.
Commit `the`, then the target token at the first miss, `system`. The ribbon
becomes **`We see the system`**. Neither `model` nor `works` is committed.
The next iteration must use this corrected prefix.

For `n` proposals, verification supplies `n + 1` target choices:
`k` is the number of consecutive matches from the start, and the committed
extension is `proposals[:k] + (target_choices[k],)`. If the very first proposal
misses, `k = 0` and the target still supplies one token. If all proposals
match, `k = n` and the target bonus follows the entire block. EOS and length
limits still terminate generation normally; the scene omits cache management
and treats the last verified token as part of the displayed context.

**Correctness is not a progress argument.** Inductively, each accepted token
equals the target's greedy choice on the actual committed prefix. At the
first miss, the target choice is still conditioned on that correct prefix;
later predictions are not. The same target model, causal context, logits
processing, and deterministic tie-breaking therefore give the same tokens as
target-only greedy decoding (assuming equivalent numerical decisions).
Adding a token merely guarantees progress. This worked example does **not**
establish distributional equivalence for nonzero-temperature sampling.

## References

- Chen, Liang, and Liu, [*DFlash: Block Diffusion for Flash Speculative
  Decoding*](https://arxiv.org/abs/2602.06036), arXiv:2602.06036.
- [Official DFlash project explanation](https://z-lab.ai/projects/dflash/):
  target-feature fusion, per-layer K/V injection, and single-pass drafting.
- [Official implementation, pinned before DFlash 2](https://github.com/z-lab/dflash/blob/44947fbf71114e241c96de194f4b382b5dd330d0/dflash/model.py):
  `sample` selects argmax at temperature zero; `dflash_generate` uses
  cumulative-product prefix acceptance and `posterior[acceptance_length]`
  for the next target token. It also supports target sampling at nonzero
  temperature; this episode deliberately limits its demonstration and
  equivalence claim to the greedy branch.
- Ringel and Romano, *Accelerating Speculative Decoding with Block Diffusion
  Draft Trees*, arXiv:2604.12989.

## Quick render (silent draft)

```powershell
# From the repository root
$env:MANIM_TTS_PROVIDER = "none"
.\.venv\Scripts\python.exe -m manim -ql examples\dflash_visual\scene.py DFlashVisualExplainer
```

## Narrated render (OpenRouter)

```powershell
$env:OPENROUTER_API_KEY = "<your key>"
$env:MANIM_TTS_PROVIDER = "openrouter"
.\.venv\Scripts\python.exe -m manim -qh examples\dflash_visual\scene.py DFlashVisualExplainer
```

## Review narration timing

The direct-Manim commands write a provider-independent timeline to
`media/review/dflash_visual/timeline.json`. Extract contact sheets into a new
empty frames directory:

```powershell
$env:MANIM_TTS_PROVIDER = "none"
.\.venv\Scripts\python.exe -m manim -ql examples\dflash_visual\scene.py DFlashVisualExplainer
.\.venv\Scripts\python.exe scripts\extract_narration_frames.py `
  media\videos\scene\480p15\DFlashVisualExplainer.mp4 `
  media\review\dflash_visual\timeline.json `
  media\review\dflash_visual\frames
```

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_dflash_visual.py -q
```

## Production render (1080p60, narrated)

```powershell
$env:OPENROUTER_API_KEY = (Get-ItemProperty HKCU:\Environment).OPENROUTER_API_KEY
$env:MANIM_TTS_PROVIDER = "openrouter"
.\.venv\Scripts\python.exe -m manim -qh examples\dflash_visual\scene.py DFlashVisualExplainer
```

Final output: `media\videos\scene\1080p60\DFlashVisualExplainer.mp4`
(`-qh` is 1920×1080 at 60 fps; `-qk` would request 4K instead).

## Managed production and acceptance

The commands above remain the direct-Manim escape hatch. To retain a unique
run manifest, matching timeline, and video, use the
[managed workflow](../../README.md#render-a-managed-episode):

```powershell
.\scripts\render.ps1 examples\dflash_visual\scene.py DFlashVisualExplainer `
  --profile draft --provider none --output-dir media\runs --run-id dflash-draft-01
.\scripts\render.ps1 examples\dflash_visual\scene.py DFlashVisualExplainer `
  --profile production --provider openrouter --quality=-qh `
  --output-dir media\runs --run-id dflash-production-01
```

Configure the OpenRouter key in the process before the production command.
Credentials alone do not select paid narration in wrappers. Use a fresh run
ID each time; these runs preserve `manifest.json`, `timeline.json`, and
`video.mp4` under `media\runs\<run-id>\` instead of the mutable legacy paths.
Managed `external-gtts` embeds its own speech and does not require a separate
mux step.

The [review procedure](../../skills/technical-manim-explainer/references/production-review.md)
requires transition frames, complete final audiovisual playback, explicit
teaching review, and manifest/hash-bound acceptance. Use this episode's
`teaching.json` when attaching contract validation. Neither the render nor
complete beat mapping proves human understanding or extends this episode's
greedy-only correctness scope.

## Storyboard

`storyboard.py` is the single source of truth for narration text, beat
structure, toy draft marginals, and prefix-keyed target conditionals. The
scene constructs bars and value labels directly from `DRAFT_MARGINALS`
(`Q1`, `Q2`, `Q3`), and target labels and commit positions from the computed
greedy verification result. A separate target-only walk supplies the visible
baseline, rather than copying the committed tuple.

Tests enumerate all toy paths with exact rational probabilities and compare
every match pattern through length four against an independent cumulative-
product oracle. They also execute the scene silently, inspect displayed
values, target labels, token states and geometry, and construct first-miss,
last-miss, and all-accepted cases. These tests establish the teaching example's
logic, not numerical equivalence of real model kernels.

## Continuity with DDTree episode

This episode ends with a brief bridge mentioning DDTree. The DDTree episode
can pick up from the prefix-acceptance and target-bonus concepts shown here;
this episode ends with a rejection case, not a full-block acceptance.
Shared references:
- Toy marginals `Q1`, `Q2`, `Q3` (same values as `examples/ddtree_dflash/algorithm.py`)
- Bonus-token semantics and verification behavior
- Color scheme: committed = success green, speculative = primary blue,
  target = accent orange, bonus = yellow
