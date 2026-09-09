# DDTree: keep alternatives, not guesses

A self-contained, approximately 5-minute-26-second episode covering DFlash's factorized draft, all seven
best-first selections, the objective and its limits, tree attention, and a
complete target-driven verification round. The visual payoff is the same
`a` and `model` nodes leaving the tree for the output, with the unmatched
target token `runs` becoming the next anchor.

This is a new episode; the earlier samples and DDTree scenes are preserved.

## Render with MAI narration

From the repository root:

```powershell
.\examples\ddtree_full\render.ps1
```

The wrapper uses the isolated `.venv`, the repository render script, and:

| Setting | Value |
|---|---|
| Provider | OpenRouter |
| Speech model | `microsoft/mai-voice-2` |
| Voice | `en-US-Harper:MAI-Voice-2` |
| Speech speed | `0.96` |
| Video | Manim high quality, 1080p60 |

`OPENROUTER_API_KEY` must be available in the process or Windows user
environment. The wrapper loads it without printing or storing it. Missing
credentials are an error: this episode never silently substitutes gTTS or
creates an unnamed silent final.

Output:

```text
media\videos\scene\1080p60\DDTreeFullExplainer.mp4
media\videos\scene\1080p60\DDTreeFullExplainer.srt
```

For a deliberate silent rough cut:

```powershell
.\examples\ddtree_full\render.ps1 -Quality -ql -Silent
```

That writes `media\videos\scene\480p15\DDTreeFullExplainer.mp4`.
When the narration manifest exists, silent beats use the actual cached MAI
durations rather than word-count estimates.

## Reproducible speech assets

Pre-cache the entire narration independently of the renderer:

```powershell
$env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY", "User")
.\.venv\Scripts\python.exe -m examples.ddtree_full.narration
```

This uses the same Manim Voiceover cache as the final render. Audio and its
provider metadata are retained under `media\voiceovers\`; the episode manifest
at `media\review\ddtree_full\narration.json` identifies each text, audio file,
duration, model, and voice. No credentials are written to these files.
Unchanged clips are reused on subsequent renders.

## The visual argument

| Stage | What changes on screen |
|---|---|
| One path fails | The target's `a` disagrees with `the`; the rest of that draft chain cannot be reused |
| DFlash marginals | Three distributions share conditioning; there is no artificial autoregressive link between their columns |
| Tree construction | A real ranked frontier feeds seven stable branch points; visible products connect parent scores and marginals to each new score |
| Objective | Prefix masses become a sum; the draft-model expectation is explicitly distinguished from actual target acceptance |
| Flattening | The same word and marker objects move along cleared curved paths into eight slots; relative depth is distinguished from array index |
| Attention | Slot seven's ancestry generates its mask row before the other rows are completed |
| Target pass | All positions are covered by one batch; the subsequent walk reads already-computed target decisions |
| Output | The matched nodes move into the committed sequence; `runs` is emitted despite not being a proposed child and anchors the next round |

Branch points use external word labels, not long words shrunk into small
circles. Georgia words and Segoe UI annotations are intentional on the Windows
render host; substitute available fonts explicitly on other platforms.
Frontier entries are lower-priority, smaller text; all scene geometry is
checked at its final size rather than fitting the whole episode by scaling.

## Technical contract

- All displayed distributions are toy data from
  `examples/ddtree_dflash/algorithm.py`, not model measurements.
- The existing `best_first_prefixes` function determines selection order.
  The storyboard exposes its lazy sibling/child offers for the visible heap.
- Scores are products under the factorized **draft** distribution with shared
  conditioning held fixed. Rounded products use an approximation sign; later
  products keep their unrounded values.
- The seven-node budget excludes the already-emitted anchor. The target input
  therefore contains eight positions.
- A child cannot have greater draft mass than its parent. Prefix closure
  follows from best-first growth and this ordering; ties do not require
  discarding an ancestor.
- The expected matched-depth objective is under `Q`, the draft model, not an
  assertion that the target accepts according to `Q`.
- Flattening uses root plus insertion order, not a claim of breadth-first
  ordering. The animation moves nodes in a separate, collision-free order;
  their destination slots remain in insertion order. Position IDs are the
  common context offset plus tree depth.
- The matrix is a binary **visibility** mask. It is not the numerical additive
  attention mask, whose blocked entries are typically negative infinity.
- Earlier committed context is visible to every node and omitted from the
  small matrix. Nodes see their ancestors and themselves, never siblings.
- The worked target walk is greedy: `a`, then `model`, then missing `runs`.
  The sampling discussion describes drawing from the target's own
  distribution at each visited prefix, not a draft-probability acceptance
  test. Membership controls reuse of cached work; a missing target token is
  still valid output.
- This round reuses two draft tokens instead of zero. It does not assert a
  measured wall-clock speedup or claim larger budgets are always better.

## Sources

- [Accelerating Speculative Decoding with Block Diffusion
  Draft Trees](https://arxiv.org/abs/2604.12989).
- [DFlash: Block Diffusion for Flash Speculative
  Decoding](https://arxiv.org/abs/2602.06036).
- [Official DDTree implementation](https://github.com/liranringel/ddtree).

Semantics were cross-referenced with official revision
`c96427a185677bf4133ed865dd1626a5041aef9b`, especially
`ddtree.py` lines 116-158 (construction and mask), 185-223 (positions and walk),
419-432 (sampling and cache compaction), and `model/utils.py` lines 28-35
(target sampling). The target logits at a node predict its **next** token.
The new bonus has been emitted but has no target KV entry until the next
round processes it.

## Review artifacts

Each render writes its actual narration timeline to
`media\review\ddtree_full\timeline.json`. Preserve the rough-cut frame index
before a later render overwrites that timeline.

```powershell
.\.venv\Scripts\python.exe scripts\extract_narration_frames.py `
  media\videos\scene\1080p60\DDTreeFullExplainer.mp4 `
  media\review\ddtree_full\timeline.json `
  media\review\ddtree_full\final
```

The resulting index and contact sheets cover the near-start, middle, and
near-end of all 27 beats. Also inspect the continuous transitions, especially
the arithmetic-to-score arrivals, flattening, ancestry-row construction, and
the final target miss.
