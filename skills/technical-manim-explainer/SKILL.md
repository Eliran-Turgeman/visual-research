---
name: technical-manim-explainer
description: Research, design, narrate, render, and improve technical explainers with native Manim. Use for technical videos and visualizations.
---

# Technical Manim Explainer

Build a useful mental model, not an animated slide deck. Use **native Manim**
and small scene-local helpers. There is no required palette, background,
component vocabulary, layout, or scene base class. Do not revive the retired
`manim_lib` or turn a successful example into a template for every topic.

Read `MANIM_GUIDE.md` before implementing. Research, storyboarding, rendering,
narration when requested, inspection, and repair are part of the task.

## Workflow

1. **Ground the explanation.** Read the paper/code. Identify the audience,
   one mechanism-level objective, a likely misconception, and the source
   locations that settle the semantics. Resolve contradictions or state them.
2. **Work a small example completely.** Independently check the inputs,
   operations, intermediate values, and final state. Add a contrasting case
   only when it reveals something the first cannot.
3. **Design the discovery before the objects.** Sketch the opening, mechanism,
   and payoff. What relationship should become visible without its caption?
   Choose a representation for that relationship, not from a component catalog.
4. **Storyboard narration and action together.** For each short beat, record
   its purpose, spoken text, visible cause/change, continuing objects, and
   approximate duration. A compact table or JSON is enough.
5. **Render a rough silent cut.** Prototype the difficult transformation
   before polishing surfaces. Inspect transitions, label fit, frame bounds,
   and collisions. Remove excess content instead of shrinking everything.
6. **Add speech deliberately.** When narration is requested, default to
   MAI-Voice-2 / Harper via OpenRouter unless the user chooses otherwise.
   Prepare short clips, reuse unchanged audio, and synchronize actions to
   actual speech durations. Never deliver a silent substitute for requested
   narration or let credentials alone trigger paid calls.
7. **Review and repair.** Inspect the first/final frames and before/during/after
   important transitions. Watch the full motion and listen to the final audio
   when possible. Fix concrete, timestamped problems; start with two focused
   repair rounds rather than an endless rewrite loop.
8. **Deliver simply.** Return the MP4, source, narration/cache needed to
   reproduce it, one render command, and short notes on sources and remaining
   issues. Keep records proportional to the task; no mandatory manifest stack,
   acceptance schema, or claim of measured learner improvement.

## What makes the explanation work

- Start at the mechanism or problem, not a generic introduction. Establish
  only the prerequisites the viewer is missing.
- Show causes before effects. Animate the operands and operation, not a flash
  followed by a disconnected result.
- Preserve identity and the viewer's mental map. Let an existing picture
  evolve; don't clear and rebuild it to avoid a difficult transition.
- Introduce structure progressively and keep one primary idea in focus.
  Use motion to explain change, not to fill narration time.
- Give each color, shape, and spatial distinction a stable meaning. Visual
  freedom is not permission for inconsistent semantics.
- A branch, transfer, deletion, replacement, or acceptance must mean that
  operation in the actual algorithm.
- Distinguish draft/model estimates from target truth or deterministic policy.
  Valid output shape and confidence do not establish correctness.
- Show concurrency only when operations are independent. Use honest common
  scales, include overhead, and never imply animation duration is measured
  system latency.
- Keep equations and terminology exact. Label toy values, conditional cases,
  and measurements. Do not invent a simpler algorithm to fit the picture.
- Let speech explain meaning while labels anchor exact values. Use natural,
  short sentences; don't read the screen aloud. Pause after dense operations,
  not after decorative fades.
- End when the promised relationship is established.

## Review honestly

Check both settled layouts and transient motion. Readable final frames do not
excuse scrambling words during a transform or hiding labels during a highlight.
Verify requested audio is present and aligned with the actual operations.

Stills, metadata, and geometry checks cannot establish intelligibility or
complete audiovisual quality. Say exactly what was inspected and what was not.
Do not invent playback, listening, human approval, or learning evidence.
