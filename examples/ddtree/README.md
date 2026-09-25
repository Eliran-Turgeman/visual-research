# DDTree: from prefix scores to target verification

The approximately four-minute reference that motivated the native-Manim
workflow. `scene.py` holds its own visual helpers; `storyboard.json` pairs
spoken text with the intended action. Its visual style is one choice, not a
template for new videos.

## Render

From the repository root:

```powershell
uv sync --locked
uv run python examples\ddtree\checks.py
uv run python -I -m manim -ql --media_dir media\ddtree-draft examples\ddtree\scene.py DDTreeExplainer
```

For narration, provide `OPENROUTER_API_KEY` outside source, then explicitly
authorize speech generation (valid clips are reused):

```powershell
uv run python scripts\narrate.py examples\ddtree\storyboard.json --generate
$env:DDTREE_NARRATED = "1"
uv run python -I -m manim -qh --media_dir media\ddtree-final examples\ddtree\scene.py DDTreeExplainer
```

Video: `media\ddtree-final\videos\scene\1080p60\DDTreeExplainer.mp4`.
Narration: MAI-Voice-2 / Harper, speed 1.0. Without `--generate`, the speech
command is cache-only. Copying an existing matching `audio\cache` directory
beside this scene lets it rebuild the manifest without a paid request.
Missing audio is an error in narrated mode, not a silent fallback.

To return to a silent draft, set `DDTREE_NARRATED=0`. The scene writes actual
beat/action times and frame-bound findings under `examples\ddtree\records`;
`DDTREE_RECORD_DIR` selects a different directory. These are local review aids,
not an acceptance protocol. On macOS/Linux set these variables in your shell
and use that platform's path separators.

The example uses DejaVu Sans and Unicode math in `Text`, so no LaTeX is needed.
Install DejaVu Sans or explicitly choose an available font when reproducing
on another host.

## What it establishes

Given three binary marginals `(.6,.4), (.7,.3), (.8,.2)` and five speculative
slots, the highest prefix masses select `A, AA, B, AAA, BA`. The root is extra.
The expected matched length is `2.036` **under the factorized draft Q**, not a
target confidence or latency claim. A concentrated case shows the same budget
can favor a chain.

Depth-based positions and an ancestor/self mask isolate each flattened path.
A toy target walk selects B then A and emits an unmatched B as the next,
unprocessed bonus. Only the processed path remains in the target cache.
`checks.py` independently verifies products, heap selection against exhaustive
enumeration, expectation, masks, positions, and target-walk edge cases.

Sources:

- Ringel & Romano, [*Accelerating Speculative Decoding with Block Diffusion
  Draft Trees*, arXiv:2604.12989v1](https://arxiv.org/html/2604.12989v1):
  section 3, equations 1-2 (conditioning); section 4.2, equations 3-8 and
  Propositions 1-2 (objective/budget); Algorithm 1 (heap); section 4.4
  (verification); Remark 1 (limits of optimality).
- [Official code at c96427a185677bf4133ed865dd1626a5041aef9b](https://github.com/liranringel/ddtree/blob/c96427a185677bf4133ed865dd1626a5041aef9b/ddtree.py):
  lines 87-165 (tree), 177-233 (mask/traversal), 309-385 (root/drafting),
  416-466 (verification/compaction).

## Lessons from the original cut

The user preferred this result to the component-based workflow. That is useful
feedback, not a controlled learning study. Full audiovisual listening was not
available during its automated production review.

Two imperfections remain in the reference's animation: ordinary `Text`
transforms can briefly scramble glyphs, and `Indicate` on filled groups can
temporarily hide token letters. The skill now calls these out explicitly.
Its three-action beat scheduler is also a local simplification, not a required
timing pattern: new scenes should synchronize the particular operation to
the spoken phrase, rather than always dividing a clip into equal slots.

Generated video/audio and the original experiment workspace are not tracked
or overwritten by this migration.
