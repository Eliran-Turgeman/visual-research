# Visual Research

**Teach the mechanism. Let the model design the picture.**

This is a small skill for making technically grounded Manim explainers, with
utilities for narration and frame inspection. There is no visual component
library, house palette, scene framework, or managed acceptance pipeline.
Use native Manim and keep helpers local to each video.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```powershell
uv sync --locked
```

Python 3.12 is recommended (3.11-3.13 supported). On Windows, normal wheels
provide Cairo/Pango. Linux needs Cairo/Pango development packages and a
compiler; macOS needs Cairo, Pango and pkg-config. See
[Manim's installation guide](https://docs.manim.community/en/stable/installation.html).
FFmpeg is bundled through `imageio-ffmpeg`. LaTeX is optional unless a scene
uses `Tex` or `MathTex`.

This is a non-package uv project: nothing installs a visual-research library.
All commands use a local `.venv`; no activation, API key, or TTS dependency is
needed for silent work.

## Make a video

Give an agent the [skill](skills/technical-manim-explainer/SKILL.md), a topic,
an audience, and technical sources:

```text
Use skills/technical-manim-explainer/SKILL.md to explain [mechanism] to
[audience], grounded in [paper/code]. Choose your own visual representation.
Render a silent draft, inspect and repair it, then add MAI narration.
Return the video, source, and a reproduction command.
```

For a fresh context without old visual examples:

```powershell
python scripts\new_project.py ..\my-video --brief my-brief.md
Set-Location ..\my-video
uv sync --locked --no-dev
```

Open a new agent session there. The exported `AGENTS.md` points to the same
skill. Only instructions, utilities, and dependency files are copied, not an
example scene or a style. Check global instructions/memories for conflicting
old component mandates; a fresh directory is not a sandbox.

The workflow is simple: **source → worked example → storyboard → rough render
→ inspect → narration → final render**. Keep the script and visuals together.
Show intermediate operations; don't just decorate their answers.

## Narration and inspection

The optional speech utility takes a JSON list with `id` and `narration` fields
(additional storyboard fields are fine):

```json
[{"id": "intro", "narration": "The target still chooses the tokens."}]
```

```powershell
uv run python scripts\narrate.py storyboard.json --generate
uv run python scripts\frames.py media\video.mp4 --at 0 12.5 28 --output review
```

`--generate` explicitly permits missing speech requests; without it, narration
is cache-only. Configure `OPENROUTER_API_KEY` outside source. The default is
**MAI-Voice-2 / Harper**, normal speed. Existing valid clips are reused.
`audio\manifest.json` maps beat IDs to measured WAV durations and paths
relative to the audio directory. Use those files with native `Scene.add_sound`.
No provider is silently substituted.

Frame extraction produces labeled contact sheets, not approval. Inspect
transitions and watch/listen to the complete result when possible. State what
you could not review; a file that renders is not proof that it teaches well.

## Reference and development

[DDTree](examples/ddtree/README.md) is the worked reference that motivated this
direction. Learn from its reasoning, not its shapes. Its source, narration,
and exact example checks are included; generated audio/video stay untracked.

```powershell
uv run python -m pytest -q
```

Keep the repository small: one skill, ordinary utility scripts, and
scene-specific examples. The retired library and legacy workflows remain in
Git history, not in an archive the agent might copy.
