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
.\scripts\render.ps1 examples\ddtree_dflash\scene.py DDTreeDFlashExplainer `
  --profile production --provider openrouter --quality=-qh `
  --output-dir media\runs --run-id ddtree-dflash-production-01
```

Configure the OpenRouter key in the process first. The selected service uses
`microsoft/mai-voice-2` with the Harper voice by default. For a fast silent
managed draft, use `--profile draft --provider none --quality=-ql` and a fresh
run ID. The run's `video.mp4`, `timeline.json`, and `manifest.json` are preserved
under `media\runs\<run-id>\`. Follow the
[managed review workflow](../../skills/technical-manim-explainer/references/production-review.md)
before calling a narrated result accepted.

Managed `--provider external-gtts` already embeds its narration; it needs **no
separate mux step**. For the legacy direct-Manim external-audio escape hatch,
render without Manim's in-memory audio mixer, then pair the timed tracks
explicitly:

```powershell
$env:MANIM_TTS_PROVIDER = "external-gtts"
.\.venv\Scripts\python.exe -m manim --disable_caching -ql examples\ddtree_dflash\scene.py DDTreeDFlashExplainer
.\.venv\Scripts\python.exe examples\ddtree_dflash\mux_audio.py `
  media\videos\scene\480p15\DDTreeDFlashExplainer.mp4 `
  media\videos\scene\480p15\DDTreeDFlashExplainer-narrated.mp4 `
  --manifest media\voiceovers\ddtree_external\manifest.json `
  --timeline media\review\ddtree_dflash\timeline.json
```

This is an explicit legacy external-gTTS path, not managed production
acceptance. gTTS synthesis requires network access; the mux command itself
generates no speech. The output must not already exist, and the input must be
silent. Preserve the matching legacy manifest and timeline from this render;
the muxer rejects missing, mismatched, overlapping, or stale tracks and writes
an adjacent `.mp4.mux.json` receipt after validating the complete output.
Legacy pairing checks are not cryptographic provenance. Prefer a versioned
hash-bound manifest when supplying externally assembled audio, and review the
entire resulting audiovisual artifact before acceptance.

## Reviewing narration timing

Every managed render preserves its run-specific provider-independent
timeline. Direct Manim (any `MANIM_TTS_PROVIDER`, including `none`) instead writes
its legacy narration timeline to
`media/review/ddtree_dflash/timeline.json` after a successful `construct()`,
recording each block's actual rendered start/end timestamps and narration
text. Use the general-purpose extraction script to pull start/middle/end
review frames and contact sheets for every block, for example right after a
fast direct-Manim silent draft into a new empty frames directory:

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
