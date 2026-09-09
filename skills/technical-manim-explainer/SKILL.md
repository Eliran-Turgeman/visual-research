---
name: technical-manim-explainer
description: Plan, implement, narrate, render, inspect, and improve technically correct Manim explainers.
---

# Technical Manim Explainer

Use this skill whenever the user asks for a technical explainer, visualization,
or narrated Manim video. The user does not need to request a storyboard,
narration plan, rendering, or review separately. Read `MANIM_GUIDE.md` before
implementing a scene.

## Goal

Produce a technically correct explanation that helps an engineering audience
build a useful mental model. Optimize for comprehension, not entertainment.
Prefer a complete small example to a broad but shallow survey.

## Public example names

Name example directories after the technical subject or demonstrated component,
using `snake_case`, with matching descriptive `PascalCase` scene classes.
Use a mechanism or representation suffix to distinguish examples of the same
subject, such as `speculative_decoding_flow` and `speculative_decoding_timeline`.
Keep test names, review paths, and render instructions consistent. Avoid
self-praise, internal demo labels, and slogans as public example identifiers.

## Required workflow

1. **Inspect the evidence.** Read the relevant paper, code, documentation,
   notes, and user description. Locate definitions, assumptions, equations,
   state transitions, and implementation details that affect semantics.
2. **Find the teaching target.** State internally, in one or two sentences,
   what the viewer should understand by the end. Separate the central mechanism
   from motivation, prerequisites, implementation details, and results.
3. **Infer prerequisites.** Use the request and context to decide what the
   viewer already knows. Briefly establish missing prerequisites; do not repeat
   background the viewer is assumed to know.
4. **Choose worked examples.** For an algorithm, mathematical procedure,
   optimization, or systems mechanism, use at least one small input that can be
   worked through completely. When useful, use two:
   - a minimal example that establishes the mechanism;
   - an example showing the advantage, edge case, or non-obvious behavior.
5. **Design backward from a visible discovery.** State the relationship the
   final picture must make obvious without a headline. Sketch three key
   compositions: opening, mechanism, and payoff. Choose a visual metaphor
   grounded in the mechanism, such as distance for time or area for probability.
   Reject a plan whose conclusion exists only in narration or a caption.
6. **Choose representations by meaning.** Specify what shape, position, color,
   and motion mean for each object. Different concepts need distinguishable
   forms, not a box for every noun. Reuse `manim_lib` when its semantics fit;
   keep a justified new representation scene-local until it recurs.
7. **Storyboard cause and effect with narration.** For each short beat, record
   the viewer's question, visible cause, resulting state change, focal region,
   continuing objects, narration, and duration budget. Remove redundant prose
   and any motion that merely announces an operation instead of showing it.
8. **Build and render a rough silent animation first.** Establish composition,
   dependency order, identity, pacing, and the discovery before polishing
   surfaces. Use the repository render script at draft quality. The mechanism
   must occupy the frame, and the comparison must use honest common scales.
9. **Add final styling and synchronized voiceover.** Keep useful structural
   contrast, not mandatory shadows or halos. Use short narration blocks and
   actual speech durations to budget meaningful actions and pauses. Do not
   stretch a fade or leave long static gaps to fill a voiceover block.
10. **Render the deliverable.** Use the repository script at the requested or
    production quality. Preserve the rough cut for comparison.
11. **Inspect the output.** Inspect representative frames and, when possible,
    watch the complete video with audio. A successfully encoded MP4 is not a
    completed explainer.
12. **Revise and render again.** Fix obvious correctness, layout, timing,
    narration, and rendering problems before completion.

Do not pause for approval between these steps unless the request is genuinely
ambiguous in a way that changes the technical explanation.

## Explanation rules

- Start with the mechanism or the problem it solves. Avoid generic openings.
- Use concrete examples before or alongside abstraction.
- Show algorithms changing state rather than describing changes over static
  slides.
- Make cause precede effect: a dependency must visibly resolve before its
  dependent operation begins. A flash followed by an unrelated result is not
  a demonstration of computation.
- Use toy values small enough to verify on screen.
- Introduce equations, labels, and structures progressively.
- Compare against a baseline when it explains why the technique exists.
- Preserve the viewer's mental map: update stable objects instead of rebuilding
  or moving the whole layout.
- Keep one primary visual idea on screen at a time.
- Let the mechanism, not a persistent heading, dominate the composition.
- Preserve shared scales and show overhead when comparing cost or latency.
- Prefer emphasis, transformation, and state changes over walls of text.
- Let narration carry prose; keep on-screen text to short visual anchors.
- Introduce structure before detail and leave a brief visual rest after dense
  state changes.
- End when the promised idea is established; do not add a generic recap.

## Correctness contract

Correctness outranks visual elegance.

- Treat provided source material as authoritative.
- Do not simplify by inventing different algorithm behavior.
- Preserve assumptions and preconditions that affect the result.
- Use exact equations and established terminology.
- Distinguish toy/example values from measured or reported values.
- When prose is ambiguous, use paper equations, tests, and source code to
  disambiguate behavior.
- Compute worked examples independently and verify every displayed intermediate
  value.
- Make visual semantics faithful: an animation that looks like replacement,
  acceptance, branching, movement, or deletion must mean that operation.
- If sources disagree, resolve or disclose the discrepancy instead of silently
  choosing the easier version.

## Narration rules

Narration is part of the design, not a post-production layer. Write it in the
voice of a technically strong engineer explaining an idea to another engineer.

- Use short sentences and short voiceover blocks.
- Let narration explain meaning while labels provide anchors and exact values.
- Do not read all visible text verbatim.
- Avoid "Let's dive in", "In this exciting video", "As you can see", and other
  generic filler.
- Avoid long summaries and unsupported claims.
- Define unfamiliar terms immediately before they matter.
- Leave short pauses after dense state changes, not after decorative motion.

## Review checklist

Before completion, check:

- no overlap, clipping, tiny text, or poor contrast;
- important objects stay in frame and do not move unexpectedly;
- transitions are slow enough to understand and fast enough to stay relevant;
- narration and visual actions refer to the same state at the same time;
- no long interval lacks a relevant visual change or emphasis;
- equations, labels, examples, and terminology match the source;
- transforms, removals, highlights, and branches communicate true semantics;
- no unexplained color, shape, or positional distinction;
- no unnecessary object, paragraph, camera move, or decorative animation;
- the mechanism remains legible and visually dominant at the intended viewing
  size; nothing was globally shrunk just to fit too much content;
- object forms have explicit meanings, and continuity survives changes in
  representation; borders, shadows, and halos earn their place;
- with sound muted and the headline hidden, the visible cause, effect, and
  final relationship can still be identified;
- the key visual discovery occurs before its concluding caption or narration;
- audio is present, intelligible, and not cut off when narration was requested.

Inspect frames near every major transition, plus the first and final frame.
If frame extraction is available, create a contact sheet. Watch the full result
when audio timing or transient motion cannot be judged from stills.

## Normal deliverables

- Manim scene source;
- reproducible narration/provider configuration;
- rendered narrated MP4;
- generated audio/cache assets required to reproduce it;
- one simple documented render command.

Report assumptions or environment-specific requirements that materially affect
reproduction.
