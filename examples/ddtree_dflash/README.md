# DFlash + DDTree explainer

This scene explains one complete speculative-decoding round:

- DFlash predicts per-position token distributions in one parallel pass.
- DDTree scores prefixes under the resulting factorized distribution.
- A best-first heap selects the highest-mass prefix-closed tree.
- Tree attention verifies every node in one target-model pass.
- The target-model walk commits a matching path and carries the first
  unmatched target token into the next round.

The numerical distributions are a labeled toy example, not benchmark data.
The algorithm and terminology follow:

- Chen, Liang, and Liu, *DFlash: Block Diffusion for Flash Speculative
  Decoding*, arXiv:2602.06036.
- Ringel and Romano, *Accelerating Speculative Decoding with Block Diffusion
  Draft Trees*, arXiv:2604.12989.
- The official `liranringel/ddtree` implementation.

Render the narrated version from the repository root:

```powershell
$env:OPENROUTER_API_KEY = "<your key>"
$env:MANIM_TTS_PROVIDER = "openrouter"
$env:MANIM_QUALITY = "-qh"
.\scripts\render.ps1 examples\ddtree_dflash\scene.py DDTreeDFlashExplainer
```

OpenRouter uses `microsoft/mai-voice-2` with the Harper voice by default. For a
fast silent draft, use `MANIM_TTS_PROVIDER=none` and `MANIM_QUALITY=-ql`.

On memory-constrained systems, render narration without Manim's in-memory
audio mixer, then mux the timed tracks:

```powershell
$env:MANIM_TTS_PROVIDER = "external-gtts"
.\.venv\Scripts\python.exe -m manim --disable_caching -ql examples\ddtree_dflash\scene.py DDTreeDFlashExplainer
.\.venv\Scripts\python.exe examples\ddtree_dflash\mux_audio.py media\videos\scene\480p15\DDTreeDFlashExplainer.mp4 media\videos\scene\480p15\DDTreeDFlashExplainer-narrated.mp4
```

## Reviewing narration timing

Every render (any `MANIM_TTS_PROVIDER`, including `none`) writes a
provider-independent narration timeline to
`media/review/ddtree_dflash/timeline.json` after a successful `construct()`,
recording each block's actual rendered start/end timestamps and narration
text. Use the general-purpose extraction script to pull start/middle/end
review frames and contact sheets for every block, for example right after a
fast silent draft:

```powershell
$env:MANIM_TTS_PROVIDER = "none"
.\.venv\Scripts\python.exe -m manim -ql examples\ddtree_dflash\scene.py DDTreeDFlashExplainer
.\.venv\Scripts\python.exe scripts\extract_narration_frames.py `
  media\videos\scene\480p15\DDTreeDFlashExplainer.mp4 `
  media\review\ddtree_dflash\timeline.json `
  media\review\ddtree_dflash\frames
```

This is a required review step, not an optional one: see "Draft review must
sample the start, middle, and end of every narration block" in
`skills\technical-manim-explainer\MANIM_GUIDE.md`.

## Implementation notes

`algorithm.py` holds the toy `Q1`/`Q2`/`Q3` marginals and the best-first
prefix search (`best_first_prefixes`) as plain Python, independent of Manim.
`scene.py` imports it as the single source of truth for the best-first
pop order, keys, and prefix masses shown in the tree-construction section, so
the displayed numbers can't silently drift from the algorithm. The same
module is covered directly by `tests\test_ddtree_algorithm.py`; run it (or the
full suite) before re-rendering after any change to the toy marginals or
search logic:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ddtree_algorithm.py -q
```
