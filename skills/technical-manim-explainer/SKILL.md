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
5. **Write a concise internal storyboard.** For every beat, record its teaching
   purpose, narration, visible objects, state change, and approximate duration.
   Remove beats that do not advance understanding.
6. **Write narration and visuals together.** Divide narration into short
   semantic segments. Each segment should introduce one idea, show one state
   transition, explain one operation, or make one comparison.
7. **Implement with semantic Manim objects.** Reuse `manim_lib` where it fits.
   Keep conceptual entities spatially stable and animate their changing state.
8. **Add synchronized voiceover.** Select a configured provider, place related
   animation inside short voiceover blocks, and use tracker duration when
   timing animations or waits. Keep silent fallback support where practical.
9. **Render with the repository script.** Use a draft quality while iterating,
   then the requested or production quality for the deliverable.
10. **Inspect the output.** Inspect representative frames and, when possible,
    watch the complete video with audio. A successfully encoded MP4 is not a
    completed explainer.
11. **Revise and render again.** Fix obvious correctness, layout, timing,
    narration, and rendering problems before completion.

Do not pause for approval between these steps unless the request is genuinely
ambiguous in a way that changes the technical explanation.

## Explanation rules

- Start with the mechanism or the problem it solves. Avoid generic openings.
- Use concrete examples before or alongside abstraction.
- Show algorithms changing state rather than describing changes over static
  slides.
- Use toy values small enough to verify on screen.
- Introduce equations, labels, and structures progressively.
- Compare against a baseline when it explains why the technique exists.
- Preserve the viewer's mental map: update stable objects instead of rebuilding
  or moving the whole layout.
- Keep one primary visual idea on screen at a time.
- Prefer emphasis, transformation, and state changes over walls of text.
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
