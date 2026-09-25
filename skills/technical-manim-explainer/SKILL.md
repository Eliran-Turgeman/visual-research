---
name: technical-manim-explainer
description: Research, design, narrate, render, and improve technical explainers with native Manim. Use for technical videos and visualizations.
---

# Technical Manim Explainer

Teach a model the viewer can **use without the animation**. A correct sequence
of operations is not yet an explanation. Optimize for the viewer's ability to
predict, explain why, and recognize where the idea stops applying.

Use **native Manim** and small scene-local helpers. There is no required
palette, layout, component vocabulary, or scene base class. Do not revive the
retired `manim_lib` or turn one successful example into a template.
Read `MANIM_GUIDE.md` before implementing.

## 1. Define the learning target

Read the technical sources before designing the lesson. In a few sentences,
establish:

- **Starting knowledge:** specific concepts the viewer already understands,
  not merely a job title. Name missing prerequisites and teach them just in
  time. If unspecified, state a reasonable audience assumption.
- **Bigger picture:** the broader task, the relevant bottleneck, and where this
  mechanism sits among the approaches the viewer may have heard of. Knowing
  individual terms does not mean knowing how they connect.
- **New capability:** what the viewer should be able to predict or explain on
  an unfamiliar example. "Understand X" is not a usable target.
- **Likely wrong model:** a plausible misconception the explanation must
  displace, and a question that would expose it.
- **Scope:** what must be taught, what prevents a false conclusion, and what
  implementation detail can remain in notes. Fit scope to available time;
  never fit it by speaking faster or shrinking the picture.

Locate sources for the mechanism, assumptions, and boundaries. Resolve source
contradictions or disclose them. Do not promise mastery of an entire topic in
one short video. A brief or the example README is enough; no form is required.

## 2. Build the reasoning before the storyboard

Choose the final application question first. Then work backward: what must
the viewer understand to answer it, and what establishes each prerequisite?

Orient before zooming into the worked example. Briefly connect the broader
problem, the existing approach, its remaining limitation, and this method's
contribution. Define unfamiliar names through their role in that chain, not as
an isolated glossary. Explain what the method changes and what it leaves alone.
For DDTree, that means inference, speculative decoding, masked block diffusion,
DFlash's parallel drafting, then budgeted tree construction.

Skipping a generic introduction is not permission to skip context. Use enough
orientation that the viewer can say why the upcoming example matters. An
already-oriented audience may need one bridging sentence; others need a short
visual explanation. Do not add a history lecture or impose a fixed intro length.
Explicitly hand off from the broader question to the concrete example, and
return to that question when explaining the payoff and limitations.

Connect the main sections through questions the viewer has a reason to ask:
**problem -> needed idea -> mechanism -> consequence -> changed case** is a
useful starting point, not a mandatory narrative template. A paper's section
order and a program's execution order are not automatically teaching orders.

For every important claim, supply the missing "because." Explain the objective
before optimizing it, the need for a representation before introducing it, and
the relevant assumption before relying on it. A preview may orient the viewer;
do not require them to understand all the internals at once.

Design the visual discovery before choosing primitives. Sketch the opening,
the decisive explanation, and the payoff. What relationship should become
visible? An attractive transformation cannot rescue a missing argument.

## 3. Work and challenge a small example

Independently verify inputs, intermediate values, operations, and final state.
The author checks the whole example; the viewer sees the parts needed to
reason. Do not animate every verified detail just because it is available.

Prefer an example the viewer can picture and care about within the topic:
complete a short message, route a delivery, or query a small familiar dataset.
Its meaning should help explain a decision, not merely rename A and B. Carry
one coherent situation through the mechanism rather than switching stories.
Use anonymous symbols when abstraction is the point or concrete details would
mislead; do not default to them because they fit inside a circle. Label toy
assumptions, and change the layout to fit meaningful names rather than hiding
them behind unexplained IDs. An analogy must preserve the relevant mechanism
and state where it stops matching.

Choose values that expose the mechanism and the likely wrong model. Explain
what a quantity measures, why an operation represents the intended relationship,
and which assumptions permit it. Spend more time on a difficult inference than
on familiar arithmetic. Show unfamiliar operands and operations explicitly,
then compress repetitions once the pattern is established.

Use a changed case or counterexample to test the rule. Hold irrelevant factors
fixed where possible; explain any simultaneous changes. Show what survives from
the toy example at real scale and what was simplified. A numerical example is
not a proof of a general claim.

## 4. Give the viewer some of the reasoning

At a few consequential moments, ask the viewer to predict, compare, explain a
failure, or complete a step **before** revealing the answer. First provide
enough knowledge to reason; do not turn prerequisites into guessing games.

Leave actual thinking time with the needed evidence visible. Then show the
reason, not just "correct." Address a tempting wrong answer when it exposes the
misconception. Gradually reduce help: worked step, supported prediction, changed
case. Do not interrupt every beat with a quiz or require an interactive player.

End by applying or reconstructing the central idea, including its boundary.
A memorable closing sentence can follow; it cannot substitute for that work.

## 5. Storyboard words, evidence, and thinking time together

For each meaningful beat, note the viewer's question or new understanding, the
spoken text, and the visible evidence/change. Record a pause or a continuing
object when it matters. Plain prose, a table, or JSON is fine; extra fields are
not an acceptance schema.

- Keep one primary inference in focus. Local clarity must serve the overall
  chain of reasoning, not produce a collection of unrelated clear scenes.
- Show causes before effects. Use motion for change and spatial arrangement
  for relationships. A branch, deletion, replacement, or acceptance must mean
  that operation in the actual mechanism.
- Preserve meaningful identity. When changing representation, show which
  entities correspond and what stays true. Deliberate section changes are
  allowed; neither arbitrary resets nor keeping everything forever helps.
- Keep evidence available while it is being used. Re-establish an earlier fact
  when needed rather than relying on the viewer's memory of a vanished frame.
- Introduce symbols through their meaning and a concrete case. Let equations
  summarize reasoning, not replace it. Define notation at first use.
- Let speech explain meaning and labels anchor exact values. Do not make the
  viewer read a competing paragraph. Captions are an accessibility aid, not
  prohibited "redundancy"; keep them clear of the explanatory picture.
- Use stable visual meanings, readable contrast, and labels or shapes alongside
  color. Do not encode an essential distinction in color alone.
- Budget time for locating, comparing, tracing, and thinking, not just for
  speaking. Briefly consolidate at conceptual boundaries. Avoid fixed beat
  lengths, equal action slots, or a universal words-per-minute target.

Keep quantities and terminology exact. Label toy values and conditional cases.
Distinguish estimates from target decisions and measurements. Show concurrent
execution only when dependencies allow it. Use honest common scales, include
relevant overhead, and never present animation time as measured latency.

## 6. Prototype, then review the explanation

Render a rough silent cut of the important reasoning before polishing. Also
rehearse the words against the picture, aloud or with available scratch audio.
The silent cut checks visual reasoning; it cannot establish audiovisual pacing.
Scratch work does not authorize paid speech.

Review in this order:

1. **Reasoning:** Are prerequisites available? Does each major claim have a
   visible or spoken reason? Can the viewer answer the final changed case from
   what was taught? Look for an accurate walkthrough with a missing "why."
   Before the example, is it clear what broader problem this method addresses,
   how the named approaches relate, and what this method adds?
2. **Attention and memory:** What must the viewer locate, retain, and infer at
   once? Are representation changes explained? Is evidence still visible during
   questions? Are pauses long enough to attempt the task?
3. **Technical truth:** Recheck computations, assumptions, source semantics,
   edge cases relevant to the claim, and the boundary of generalization.
4. **Presentation:** Inspect settled frames and before/during/after important
   transitions, real label fit, collisions, contrast, and frame bounds. Inspect
   full motion and listen to final audio when available. Remove excess content
   rather than shrinking it.

Repair specific problems, starting with the highest-impact misunderstanding.
Reinspect the affected sequence; count neither repair rounds nor rendered
frames as evidence of learning. Avoid endless polish without a diagnosed issue.

When feasible, ask an intended viewer to explain or predict after watching,
without the worked answer visible. Ask where their reasoning broke, not just
"was it clear?" One viewer can expose a problem, not establish general learning
effectiveness. AI review is useful criticism, not a substitute learner.

## 7. Finish and report honestly

When narration is requested, default to MAI-Voice-2 / Harper via OpenRouter
unless the user chooses otherwise. Use short semantic clips, reuse unchanged
speech, and synchronize each operation to its actual phrase. Add thinking time
outside speech duration. Never let credentials alone authorize paid calls or
deliver silence as a substitute for requested narration.

Deliver the MP4, source, reproduction command, and narration/cache or caption
files needed for the requested result. Keep source notes and remaining issues
short. No mandatory manifest stack, visual framework, or managed acceptance
pipeline is needed.

Separate **technical verification**, **presentation inspection**, and **learner
evidence**. Stills and geometry cannot establish intelligibility; playback alone
cannot establish transfer. State what was and was not inspected. Never invent
listening, human approval, measured improvement, or guaranteed understanding.
