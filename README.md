# Visual Research

**Teach a model the viewer can use without the animation.**

This is a small skill for making technically grounded Manim explainers, with
utilities for narration and frame inspection. There is no visual component
library, house palette, scene framework, or managed acceptance pipeline.
Use native Manim and keep helpers local to each video.

Success is not "every step was shown." It is a viewer who can predict a changed
case, explain why the mechanism behaves that way, and recognize its limits.
The skill designs toward that goal; rendering and automated checks cannot
prove that a viewer learned.

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
Use skills/technical-manim-explainer/SKILL.md to explain [mechanism], grounded
in [paper/code]. The viewer already understands [specific prerequisites].
Afterward they should be able to [predict/explain a new case].
They may wrongly believe [misconception]. Keep [implementation details] out
of scope. Choose the visual representation from the reasoning.
First connect the broader task, existing approach, and remaining problem to
this method's contribution. Then bridge into the example; do not jump into
details before the viewer knows why they matter.
Choose a familiar example whose meaning helps explain the mechanism, not
arbitrary A/B labels. Verify it, explain why each major step is needed, and give
the viewer a prediction before revealing its answer. Render a silent draft,
rehearse the script against it, and repair instructional and visual problems.
Add MAI narration only when explicitly authorized. Return the video, source,
reproduction command, and an honest account of what was reviewed.
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

The workflow is **audience and outcome → source-grounded reasoning → checked
example and changed case → words and pictures → rough-cut review → final media**.
Keep the script and visuals together. Explain why operations are appropriate;
do not merely decorate their answers. Review missing reasoning before polish.
Carry one relatable situation through the explanation. In the DDTree reference,
completing "My dog stayed outside" versus "My cat stayed inside" makes different
token histories concrete; the words are not decorative replacements for IDs.
The example follows an orientation to inference, speculative decoding, masked
diffusion, and DFlash, so the viewer knows what DDTree adds before tracing it.

The learning design is in [SKILL.md](skills/technical-manim-explainer/SKILL.md);
rendering, timing, and layout advice is in
[MANIM_GUIDE.md](skills/technical-manim-explainer/MANIM_GUIDE.md). No worksheet,
fixed narrative template, or pedagogical scoring framework is required.

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

[DDTree](examples/ddtree/README.md) is a worked reference: it motivates coverage,
derives the expected-match objective, then asks the viewer to predict selection,
trace target decisions, and distinguish coverage from correctness. Learn from
its reasoning, not its shapes. Source, narration text, and exact example checks
are included; generated audio/video stay untracked.

The teaching approach is informed by the
[IES practice guide](https://ies.ed.gov/ncee/wwc/PracticeGuide/1) on worked
examples, problem solving, concrete/abstract connections, and explanatory
questions, and [Brame's educational-video review](https://pmc.ncbi.nlm.nih.gov/articles/PMC5132380/)
on cognitive load and active learning. These support the principles, not a
universal video length, fixed pause duration, or claim that our videos improve
learning. Intended-viewer explanation and transfer tasks provide evidence that
rendering cannot.

```powershell
uv run python -m pytest -q
```

Keep the repository small: one skill, ordinary utility scripts, and
scene-specific examples. The retired library and legacy workflows remain in
Git history, not in an archive the agent might copy.
