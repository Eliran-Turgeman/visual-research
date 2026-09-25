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
