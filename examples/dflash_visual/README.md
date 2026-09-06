# DFlash Visual Explainer

A focused standalone episode explaining **DFlash** (block-parallel speculative
drafting) to engineers with rusty math. One evolving picture, no slides.

## What the viewer learns

1. Why autoregressive decoding is sequential and slow.
2. How a standard drafter fills slots one-by-one.
3. How DFlash predicts a masked future block in **one parallel pass**.
4. How target hidden features condition the small draft model (K/V injection).
5. Why the output is *marginals* (independent per-position), not conditionals.
6. How the target model verifies proposals in one pass.
7. Why speculative decoding is lossless (bonus-token guarantee).
8. Brief bridge to DDTree as the next episode.

## References

- Chen, Liang, and Liu, *DFlash: Block Diffusion for Flash Speculative
  Decoding*, arXiv:2602.06036.
- Ringel and Romano, *Accelerating Speculative Decoding with Block Diffusion
  Draft Trees*, arXiv:2604.12989.

## Quick render (silent draft)

```powershell
cd <repo-root>
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

Every render writes a provider-independent timeline to
`media/review/dflash_visual/timeline.json`. Extract contact sheets:

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

## Storyboard

`storyboard.py` is the single source of truth for narration text, beat
structure, and toy numerical data. The scene imports every beat's narration
from there; numbers displayed in probability distributions are derived from
the same `Q1`, `Q2`, `Q3` marginals used in the combined example.

## Continuity with DDTree episode

This episode ends with a brief bridge mentioning DDTree. The DDTree episode
should pick up from the committed ribbon and bonus token shown here.
Shared references:
- Toy marginals `Q1`, `Q2`, `Q3` (same values as `examples/ddtree_dflash/algorithm.py`)
- Bonus-token semantics and verification behavior
- Color scheme: committed = success green, speculative = primary blue,
  target = accent orange, bonus = yellow
