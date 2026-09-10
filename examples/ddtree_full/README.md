# DDTree: keep alternatives, not guesses

A self-contained, approximately 5-minute-26-second episode covering DFlash's factorized draft, all seven
best-first selections, the objective and its limits, tree attention, and a
complete target-driven verification round. The visual payoff is the same
`a` and `model` nodes leaving the tree for the output, with the unmatched
target token `runs` becoming the next anchor.

This is the canonical complete-episode workflow reference; the smaller examples
demonstrate individual mechanisms and representations.

## Render with MAI narration

From the repository root:

```powershell
.\examples\ddtree_full\render.ps1 -Profile production -Provider openrouter `
  -OutputDir media\runs -RunId ddtree-production-01
```

The wrapper uses the isolated `.venv`, the repository render script, and:

| Setting | Value |
|---|---|
| Provider | OpenRouter |
| Speech model | `microsoft/mai-voice-2` |
| Voice | `en-US-Harper:MAI-Voice-2` |
| Speech speed | `0.96` |
| Video | Manim high quality, 1080p60 |

`OPENROUTER_API_KEY` must be available in the process. The wrapper no longer
loads user-level credentials automatically. Production requires an explicitly
selected provider and fails on missing credentials; it never silently
substitutes gTTS or creates an unnamed silent final. With no arguments the
wrapper now defaults to a silent low-quality **draft**, not paid production.
An explicit `MANIM_TTS_PROVIDER` can select narration, so use `-Provider none`
when a silent draft is required regardless of the environment.

Output:

```text
media\runs\ddtree-production-01\video.mp4
media\runs\ddtree-production-01\timeline.json
media\runs\ddtree-production-01\manifest.json
```

For a deliberate silent rough cut:

```powershell
.\examples\ddtree_full\render.ps1 -Profile draft -Provider none -Quality -ql `
  -OutputDir media\runs -RunId ddtree-draft-01
```

That writes `media\runs\ddtree-draft-01\video.mp4`. Choose a fresh run ID for
each render. `-Silent` remains a draft compatibility option and is rejected
with production. See [managed workflow options](../../README.md#render-a-managed-episode).
When the narration manifest exists, silent beats use the actual cached MAI
durations rather than word-count estimates.

## Reproducible speech assets

Managed renders reuse valid speech from `media\voiceovers\openrouter` by
default, independent of their fresh run ID. Use `-CacheDir CACHE_ROOT` to choose
another root; the wrapper appends the provider name. Retained audio snapshots
live in each run's `audio` directory and do not change when the shared cache
changes. See the [cache settings](../../skills/technical-manim-explainer/references/narration.md#cache-reuse-and-recovery)
for environment precedence and cross-worktree reuse.

The standalone legacy helper can pre-cache narration independently of the
renderer:

```powershell
.\.venv\Scripts\python.exe -m examples.ddtree_full.narration
```

This is an explicit speech-generation action and requires the process's
OpenRouter key; authorize provider use before running it. Audio and its
provider metadata are retained under `media\voiceovers\`; the episode manifest
at `media\review\ddtree_full\narration.json` identifies each text, audio file,
duration, model, and voice. No credentials are written to these files.
This helper's legacy cache path is not the managed provider-scoped cache;
do not assume invoking it prepopulates `media\voiceovers\openrouter`.
Unchanged valid clips can be reused only with their matching cache location
and provider configuration.
Managed runs retain their own audio artifacts; inspect the run's paths rather
than assuming a mutable global narration manifest is its review evidence.
See [audition and recovery guidance](../../skills/technical-manim-explainer/references/narration.md).

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

## Teaching review

The primary transfer check changes the target outcome: **if the target chooses
a token absent from the current node's children, is the token invalid?**
Expected answer: no; it is emitted as valid target output, the current round
stops reusing that branch's precomputed work, and the token becomes the next
anchor. A second check asks whether a larger draft-mass sum guarantees a
wall-clock speedup. Expected answer: no; the objective is under the draft
distribution and does not account for every target/hardware cost.

Keep technical correctness, production review, and actual learner responses
separate. These checks define what the explanation should enable; no learner
study or measured learning improvement is claimed. See the
[compact contract guidance](../../skills/technical-manim-explainer/references/teaching-contract.md).

## Review artifacts

Managed renders preserve a run-specific video and actual narration timeline.
Inspect the production run above:

```powershell
python scripts\review_production.py inspect `
  media\runs\ddtree-production-01\manifest.json `
  --output media\runs\ddtree-production-01\review.json `
  --frames-dir media\runs\ddtree-production-01\frames
python scripts\validate_teaching.py examples\ddtree_full\teaching.json `
  --timeline media\runs\ddtree-production-01\timeline.json --check-sources `
  --output media\runs\ddtree-production-01\teaching-validation.json
```

The resulting index and contact sheets cover the near-start, middle, and
near-end of all 27 beats, video endpoints, block boundaries, and declared
visual events. Also inspect the continuous transitions, especially
the arithmetic-to-score arrivals, flattening, ancestry-row construction, and
the final target miss. Watch and listen to the complete final video; then
follow the [explicit acceptance procedure](../../skills/technical-manim-explainer/references/production-review.md#reproducible-local-review-commands).
Technical inspection and teaching validation alone do not accept a run.

Direct Manim remains available and writes the legacy
`media\review\ddtree_full\timeline.json`; preserve it immediately with its
matching video if using that escape hatch. Managed commands above avoid
accidentally pairing artifacts from different runs.
