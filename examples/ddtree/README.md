# DDTree: why a draft tree buys coverage, not authority

A roughly nine-minute native-Manim lesson. It first connects language-model
inference, speculative decoding, masked-token diffusion, DFlash, and DDTree.
Then it derives what a prefix is worth before selecting prefixes, asks the
viewer to make consequential choices, and ends with a changed case separating
draft coverage from the target's decision.
The visual style and scene-local helpers are specific to this example.

The running situation is completing a message: the drafter proposes
**"My dog stayed outside"**, while the target chooses **"My cat stayed inside"**.
This is more than a change of labels: the two occurrences of *stayed* have
different histories, so the target can prefer *outside* for the dog and *inside*
for the cat. That makes path isolation and conditional prediction concrete.
Each displayed word is one toy token; real tokenizers may split words
differently. The probabilities and toy outcomes are illustrative, not measured
claims about language or animal behavior.

## Audience and learning target

The viewer is comfortable with elementary probability and tree diagrams.
The opening introduces inference, autoregressive decoding, draft/target roles,
masked-token diffusion, and DFlash; prior knowledge of DFlash or DDTree is not
assumed. Basic attention intuition helps, but the worked mask explains which
history each node may use. This is not a transformer architecture course,
diffusion-training derivation, or complete implementation tutorial. Prefix
identity, factorization under Q, depth-based positions, and the selected/processed
token distinction are explained where they become necessary.

Afterward, the viewer should be able to:

- Explain what DFlash accelerates and what DDTree adds, without confusing the
  diffusion drafter with the autoregressive target.
- Choose between another branch and a deeper prefix using their contributions
  to expected matched length under Q, and explain why summing masses makes sense.
- Explain why packing multiple paths must not mix their attention histories.
- Predict what changes, and what does not, when different draft trees meet the
  same target choice. A high draft score does not choose the emitted token.

The central misconception is "the tree's highest score decides the answer."
The final task keeps the target's choice *cat* fixed while changing the prepared
tree: both write *cat*, but only one prepared that history for reuse.

## Reasoning and structure

| Section | Question answered | Evidence or viewer task |
|---|---|---|
| Inference | Why is generating text sequential and expensive? | Follow the target/prefix feedback loop, then introduce cheap proposals and batched checking. |
| Drafting | Why bring diffusion into this system? | Contrast dependent draft steps with masked block prediction; explain DFlash's single-pass, target-conditioned drafter. |
| Contribution | What does DDTree add to DFlash? | Map per-position alternatives to budgeted paths, then hand the slot-allocation question to the sentence example. |
| Need | Why not propose just one chain? | The target writes *cat*, not *dog*; a fixed budget can finish one phrase or prepare another beginning. |
| Objective | What does a prefix contribute? | Trace a three-match continuation, then sum the chances of reaching each selected depth. |
| Selection | Where should the next slot go? | Predict *cat* versus *dog stayed outside*; change probabilities at the same three-slot budget. |
| Verification | How can one pass evaluate separate paths? | Map words to flat inputs; decide whether the cat's *stayed* can borrow the dog's history. |
| Traversal | Who chooses the actual tokens? | Read precomputed target outputs, including an output that conflicts with draft ranking. |
| Transfer | Does changing the draft change the target decision? | Compare two prepared trees with the same target choice, then delimit the speed claim. |

The heap's lazy enumeration, log-space numerics, detailed stopping policies, and
cache memory movement remain implementation notes, not parallel teaching goals.
The source algorithm still matters: the lesson does not replace it with a
different algorithm. Highest-mass selection is the conceptual rule; the paper's
heap implements it efficiently.

The opening diagrams show dependencies and roles, not measured latency.
Masked-token diffusion can involve repeated refinement; the single-pass claim
is specific to DFlash's block drafting. Its target model remains autoregressive.
The conclusion returns to this division of work rather than ending only on the
toy calculation.

`storyboard.json` contains the learning purpose, short speech, visible anchor,
provisional minimum duration, and extra thinking time for each semantic beat.
These fields are local planning choices, not a required schema for new topics.
`scene.py` uses one semantic action group per clip, with separate question and
answer clips. Minimum holds do not claim measured reading or reasoning times.

## Render

From the repository root, choose a new media directory for each revision:

```powershell
uv sync --locked
uv run python examples\ddtree\checks.py
$env:DDTREE_NARRATED = "0"
$env:DDTREE_RECORD_DIR = "$PWD\media\ddtree-review\records"
uv run python -I -m manim -ql --media_dir media\ddtree-review examples\ddtree\scene.py DDTreeExplainer
```

Draft: `media\ddtree-review\videos\scene\480p15\DDTreeExplainer.mp4`.
Use `-qm` for a 720p30 draft or `-qh` for 1080p60 output.

The record directory contains beat/hold times, top-level frame-bound findings,
and `draft-script.srt` for read-along rehearsal with the silent draft. These
script timings are provisional, not synchronized speech or proof of readability.
The scene uses DejaVu Sans and `Text`, so no LaTeX is required. Install that font
or explicitly select an available font on another host.

For speech, provide `OPENROUTER_API_KEY` outside source and explicitly authorize
generation. The following command makes paid requests for missing clips:

```powershell
uv run python scripts\narrate.py examples\ddtree\storyboard.json --generate
$env:DDTREE_NARRATED = "1"
$env:DDTREE_RECORD_DIR = "$PWD\media\ddtree-narrated-review\records"
uv run python -I -m manim -qh --media_dir media\ddtree-narrated-review examples\ddtree\scene.py DDTreeExplainer
```

Without `--generate`, the speech tool is cache-only. The default is MAI-Voice-2 /
Harper. The scene checks that every clip matches the current storyboard.
An old-cut manifest is not valid for this revised lesson; missing or stale audio
is an error rather than a silent fallback. Existing cache files are preserved.

Narrated mode writes `narration.srt` using actual clip boundaries. This is a
whole-clip caption draft, not word-aligned finished subtitles: review line
length, phrase alignment, and placement with the final audio before delivery.
Do not use a silent draft's sidecar as final speech captions.

On macOS/Linux, set environment variables in your shell and use its path
separators. Without `DDTREE_RECORD_DIR`, records go beside the example source.
Keep generated video, audio, and review records untracked.

## Independent technical evidence

For the word pairs `(dog, cat), (stayed, slept), (outside, inside)`, use marginals
`(.6,.4), (.7,.3), (.8,.2)`. Five speculative slots select `dog`, `dog stayed`,
`cat`, `dog stayed outside`, and `cat stayed`. The carried word *My* is extra.
The chance of at least one, two, or three matches under Q is `1, .7, .336`.
Each reached depth contributes one, so their sum is `2.036` expected matches.
The distribution of exact lengths is `P(1)=.3, P(2)=.364, P(3)=.336`, providing
another way to check the same expectation. None of these is a target-confidence
or measured-latency claim.

With three slots, the dispersed example prepares *dog*, *dog stayed*, and *cat*;
the concentrated `(.9,.1), (.9,.1), (.8,.2)` example prepares the chain
*dog stayed outside*. In the main tree, the target follows *cat*, then *stayed*,
and emits the missing *inside* as the next, unprocessed bonus. The retained
processed tokens are *My cat stayed*.

The numeric checker and scene retain internal binary prefix keys (`A`, `B`,
`AA`, and so on) to keep the original arithmetic easy to compare. These are
implementation keys, not the displayed example. Tests verify every word mapping
against the independent checker and check that real words fit the token shapes.

`checks.py` independently uses exact fractions, exhaustive continuation
enumeration, and a heap implementation to check products, expectation by both
methods, ranking across budgets, ancestor closure, masks, depth positions,
target-walk edge cases, and the final same-target/different-tree comparison.
These checks establish toy-example correctness, not learner understanding.

Sources:

- Chen, Liang & Liu, [*DFlash: Block Diffusion for Flash Speculative Decoding*,
  arXiv:2602.06036v1](https://arxiv.org/html/2602.06036v1), Introduction
  (autoregressive inference/drafting and diffusion motivation); the
  [official DFlash project, Design](https://z-lab.ai/projects/dflash/#design)
  (target-feature conditioning and single-pass parallel drafting).
- Ringel & Romano, [*Accelerating Speculative Decoding with Block Diffusion
  Draft Trees*, arXiv:2604.12989v1](https://arxiv.org/html/2604.12989v1):
  section 3, equations 1-2 (conditioning); section 4.2, equations 3-8 and
  Propositions 1-2 (objective/budget); Algorithm 1 (heap); section 4.4
  (verification); Remark 1 (optimality limits).
- [Official code at c96427a185677bf4133ed865dd1626a5041aef9b](https://github.com/liranringel/ddtree/blob/c96427a185677bf4133ed865dd1626a5041aef9b/ddtree.py):
  lines 87-165 (tree), 177-233 (mask/traversal), 309-385 (root/drafting),
  416-466 (verification/compaction).

## Review and limitations

Technical checks and sampled frames are not an acceptance protocol. Review
the expectation derivation, question holds, representation changes, and target
walk as complete sequences. Inspect full motion and listen to actual speech
before claiming audiovisual review. Ordinary words fade rather than morph;
outlines emphasize filled token groups without erasing their text.

The original cut's user preference motivated this example, not a controlled
learning result. The revised lesson is designed to expose and repair missing
reasoning; no intended-viewer learning evidence is established by its source,
rendering, tests, or frame-bound report.

A useful cold-viewer review asks for a new branch/depth choice and its reason,
then a same-target/different-draft prediction without the worked answer visible.
Record the mistaken reasoning and revise the relevant explanation. Do not
replace this with "was it clear?" or a claim that one viewer proves effectiveness.
