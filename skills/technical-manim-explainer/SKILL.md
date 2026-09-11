---
name: technical-manim-explainer
description: Plan, implement, narrate, render, inspect, and improve technically correct Manim explainers.
---

# Technical Manim Explainer

Use this skill for technical explainers, visualizations, and narrated Manim
videos. Research, storyboard, implementation, narration, rendering, inspection,
and revision are implicit parts of the request. The coding agent directs the
work; this repository is a small toolkit, not an autonomous generation service.

## Load only the current stage

Read [MANIM_GUIDE.md](MANIM_GUIDE.md) before implementing a scene. Load the
following references when their stage begins, rather than adding every source,
transcript, and tool output to every prompt:

| Stage | Reference |
|---|---|
| Research and teaching design | [Teaching contract](references/teaching-contract.md) |
| Speech preparation and recovery | [Narration](references/narration.md) |
| Render, review, repair, and acceptance | [Production review](references/production-review.md) |
| Cost reporting or workflow comparisons | [Measurement](references/measurement.md) |

Use [DDTree full](../../examples/ddtree_full/README.md) as the complete episode
reference and [speculative decoding timeline](../../examples/speculative_decoding_timeline/README.md)
as the compact shared-scale reference. They demonstrate approaches, not a
mandatory scene template or evidence of learner improvement.

## Required workflow

1. **Ground the explanation.** Read the relevant paper, code, documentation,
   and user constraints. Record source versions and exact claim locations.
   Resolve disagreements or disclose them; never invent simpler behavior.
2. **Write a compact teaching contract.** State the audience, prerequisites,
   one mechanism-level objective, likely misconception, source-backed claims,
   and a small fully worked example. Add one or two transfer questions with
   expected answers. Keep technical, production, and learner criteria separate.
3. **Design backward from a visible discovery.** Sketch opening, mechanism,
   and payoff. Specify what shape, position, color, and motion mean. The final
   relationship must be apparent before its caption names it.
4. **Storyboard cause and effect with narration.** Give each short beat a
   stable ID, teaching purpose, visible cause and state change, continuing
   objects, spoken text, and duration budget. Link it to the contract's claims.
5. **Implement and render a silent draft.** Use semantic Manim objects where
   they fit, preserve identity, and show operands before results. Select draft
   mode explicitly; credentials alone must not trigger paid speech in wrappers.
   Check geometry and inspect transitions before spending on narration.
6. **Prepare speech deliberately.** Audition difficult terms with the chosen
   provider, maintain a pronunciation glossary, then reuse a stable supported
   model/voice/delivery. Keep blocks short and synchronize to actual durations.
   Preserve valid cached clips. Disclose AI-generated voice for OpenAI TTS.
7. **Render production explicitly.** Select a non-silent provider and intended
   quality. Preserve the run manifest, video, timeline, source revision, and
   speech configuration. A successful render is only **rendered**, not accepted.
8. **Review → repair → validate, within a budget.** Inspect the actual artifact:
   narration-block samples, frames around transitions, and complete playback
   with audio. Record timestamped findings; fix the highest-impact cause;
   rerun relevant checks and render when necessary. Use the bounded procedure
   in the review reference, not an unbounded self-critique loop.
9. **Accept only with evidence.** Bind review to the current manifest and
   artifact hashes. Require technical and production checks plus explicit
   audiovisual and teaching review. Agent confidence, passing tests, contact
   sheets, and the existence of an MP4 are insufficient on their own.
   If full review or learner evidence is unavailable, report that limitation;
   do not fabricate approval or learning gains.

Proceed without routine approval pauses. Stop at an actual permission boundary,
exhausted repair budget, or unresolved source conflict; report the remaining
blocker instead of silently weakening the acceptance criteria.

## Explanation rules

- Prefer a complete small mechanism to a broad survey. Establish only missing
  prerequisites; start with the mechanism or the problem it solves.
- Use exact terminology, equations, assumptions, and independently verified
  intermediate values. Label toy values and conditional outcomes explicitly.
- Make causes precede effects and keep conceptual entities spatially stable.
  A flash followed by a disconnected answer is not a computation.
- Keep one primary visual idea in focus. Introduce structure before detail;
  use honest common scales and include overhead in comparisons.
- Let narration explain meaning while readable labels anchor exact values.
  Avoid filler, text walls, decorative motion, and reading every label aloud.
- Leave a short rest after dense state changes; never stretch a trivial fade
  or a static slide merely to occupy the voiceover.
- Preserve the mechanism's size and continuity. Remove excess content rather
  than shrinking the entire picture. Use new scene-local representations when
  existing components do not express the concept.
- End once the promised relationship is established, without a generic recap.

## Deliverables

Provide scene source, compact teaching contract and provenance, reproducible
render/provider settings, final video, required speech/cache assets, run
manifest and timeline, review evidence bound to that run, and one reproduction
command. Distinguish **draft**, **rendered**, **reviewed**, and **accepted** in the
handoff. State unresolved findings, unknown costs, untested learner outcomes,
and environment-specific requirements.

## Public names

Use subject/component `snake_case` directories and descriptive `PascalCase`
scene names. A mechanism suffix can distinguish representations, such as
`speculative_decoding_flow` and `speculative_decoding_timeline`. Keep tests,
review paths, and commands consistent; avoid self-praise and internal slogans.
