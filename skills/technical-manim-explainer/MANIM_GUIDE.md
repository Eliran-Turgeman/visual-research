# Native Manim notes

Consult the [official docs](https://docs.manim.community/) for the installed
version. These are implementation notes, not a visual style guide or a substitute
for the learning design in `SKILL.md`.

## Design and layout

Choose the representation from the mechanism. Geometry, plots, text, matrices,
paths, and custom `VMobject` shapes are all available. Boxes and arrows are
not the default answer; neither is any previous scene's design.

Use `VGroup` for related objects and explicit keys for continuing entities.
Prefer relative placement when it expresses the relationship. Coordinates
are appropriate for meaningful geometry, shared scales, and stable anchors.
Build at the final intended scale and check real labels, including the longest
word or largest value. Test intermediate states as well as endpoints.

Keep the current question and its evidence close enough to compare. During a
prediction pause, retain the relevant inputs but withhold the answer. A new
representation needs a visible correspondence: trace one node into its array
entry or matrix row before revealing the whole mapping.

Use a small persistent summary only when the next inference needs it. Remove
finished scaffolding at a conceptual boundary; visual continuity does not mean
permanent clutter. Check captions, labels, and diagrams together at delivery
resolution. Pair semantic colors with words, symbols, or shapes.

Use `Text` for labels and `MathTex` for mathematics when LaTeX is available.
Keep equations exact even when using a different text renderer.
Keep helpers local to the scene; don't build a reusable visual framework.

## Motion without visual glitches

- Transform continuing entities, not unrelated sentences. For ordinary text
  replacement, a brief fade-out/fade-in is often clearer than glyph morphing.
  For equations, match shared terms and animate the changed operation.
- Use `TransformFromCopy` when a source contributes while remaining present.
  Show operands before results and let the result settle long enough to read.
  A moving number does not explain why the operation is appropriate: supply
  the meaning through a concrete quantity, comparison, or spoken reason.
- Highlight with an outline, pointer, or controlled stroke change. Applying
  `Indicate` to a whole filled group can turn text and background the same
  color and briefly erase the label.
- Coordinate related changes; don't make unrelated objects move together.
  Use camera motion only when it explains scale, position, or focus.
- Keep connectors attached and behind labels. Use updaters only for
  relationships that actually need continuous recomputation.

For trees, preserve growth direction and established node positions. For a
derived matrix or mask, visibly connect cells to the structure that produces
them. For comparisons, share a scale and show the relevant overhead.

## Narration

Write the words and actions together. A clip and its animation starting at
the same time is not sufficient: the operation must happen when the narrator
explains it. Split a long clip or adjust action offsets; don't distribute
unrelated animations into equal time slots by habit.

Split speech at a question/answer boundary so a silent reasoning pause can sit
between clips. Measure speech duration, but choose the pause from the task:
comparing two numbers is not the same as tracing a new attention mask. Show the
question and its evidence before starting the pause; reveal the answer after
it. Do not stretch a decorative animation to fill thinking time.

For a rough cut, use explicit scene-local minimum holds and rehearse the words.
These are provisional timings, not a simulated listening test. For final
speech, use actual clip timings and inspect phrase alignment. If captions are
provided, derive their times from the same speech schedule and check their text
against the audio; caption presence alone does not establish accessibility.

Default: OpenRouter `microsoft/mai-voice-2`, voice
`en-US-Harper:MAI-Voice-2`, speed `1.0`. Audition difficult technical names,
keep short semantic clips, and reuse unchanged speech.

When the repo utilities are available:

```powershell
uv run python scripts\narrate.py storyboard.json --beat intro --generate
uv run python scripts\narrate.py storyboard.json --generate
```

`storyboard.json` is a list of objects with unique `id` and `narration` strings.
Other planning fields are optional. Without `--generate`, the command is
cache-only. `--output` selects the audio directory; by default it is `audio`
beside the storyboard. The manifest contains `beats[id].wav` (relative to that
directory), actual `duration`, and the request settings/text.

Use WAVs with native `Scene.add_sound` and those durations for timing. Keep
scene-specific synchronization in the scene, not a shared narration base class.
An installed copy of this skill need not have the utilities: use the documented
[speech API](https://openrouter.ai/docs/guides/overview/multimodal/tts) directly
or supplied audio. Never store keys or silently switch provider on failure.

## Render and inspect

Use a project-local environment. Native commands are sufficient:

```powershell
uv run python -I -m manim -ql --media_dir media\draft scene.py YourScene
uv run python -I -m manim -qh --media_dir media\final scene.py YourScene
uv run python scripts\frames.py media\final\videos\scene\1080p60\YourScene.mp4 --at 12.5 28 --output review
```

`-ql` is 480p15; `-qh` is 1080p60. Use distinct output directories for revisions
you want to compare. Record actual beat/transition times if useful for review.
The frame tool samples endpoints plus requested times (or eight evenly spaced
frames by default). Pick before/during/after important transitions yourself.
Contact sheets supplement, not replace, complete playback and listening.

Sample instructional moments too: the frame that contains a prediction's
evidence, the reveal, and the transition into the next representation. Inspect
at normal viewing size, not only enlarged stills. A geometry report cannot
detect a missing reason, a premature answer, or an unreadably short hold.
