# Working here

Use `skills/technical-manim-explainer/SKILL.md` for video work. The default is
native Manim with scene-local helpers, not a shared visual library or style.
Do not reintroduce the retired component, narration-base-class, or managed
acceptance frameworks. Examples are evidence, not templates for new topics.

Use `uv sync --locked` and `uv run python -m pytest -q`. Keep shared code limited
to small nonvisual utilities. Speech generation needs explicit `--generate`;
never commit credentials or generated audio/video. Preserve existing media.

Prefer clear explanations, verified intermediate computations, useful review,
and a simple reproduction command over extra abstraction or paperwork.

Define what the intended viewer can predict and explain afterward. Build the
reasoning before the animation: motivate each idea, explain why operations
work, and include a changed case with thinking time before the answer.
Review instructional gaps before visual polish. Separate technical checks,
presentation inspection, and actual learner evidence; never claim learning
from a successful render.

Prefer coherent, relatable examples whose meaning helps explain the mechanism.
Use anonymous A/B labels only when abstraction helps, not just to simplify
layout. Make the picture fit meaningful words and state toy assumptions.

Before the worked example, connect the subject to its broader task, bottleneck,
and related approaches. Explain what it adds and leaves unchanged. Avoid generic
introductions, not useful context; bridge into the example and back to the payoff.
