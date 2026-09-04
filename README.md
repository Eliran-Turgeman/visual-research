# Visual Research

This repository is not an autonomous video-generation system.

It provides reusable instructions, conventions, and Manim primitives that
allow a capable coding agent to consistently produce narrated technical
explainers. The agent supplies research, reasoning, implementation, rendering,
and revision; this repository supplies the method and a small visual vocabulary.

## Mental model

```text
User:
"Create a narrated explainer of DDTree tree construction.
Assume I already understand standard speculative decoding.
Use two worked examples and ground the explanation in the paper
and implementation in this repository."

Agent:
-> reads the technical explainer skill
-> consults the Manim guide
-> reads source material
-> storyboards
-> writes Manim + narration
-> renders
-> inspects
-> fixes
-> returns final MP4 + source
```

The architecture stays deliberately small:

- `skills/technical-manim-explainer/SKILL.md` defines the end-to-end method and
  quality bar.
- `MANIM_GUIDE.md` contains Manim-specific house rules.
- `manim_lib/` provides reusable semantic visual components.
- `examples/` shows how a scene combines those pieces.
- `scripts/render.*` is the rendering workflow.

## Requirements

- Python 3.11-3.13
- [Manim Community](https://docs.manim.community/) native dependencies
- FFmpeg for video and audio assembly
- A LaTeX distribution when a scene uses `MathTex` or `Tex`

Manim's installation guide documents platform-specific native dependencies.
The minimal example uses `Text`, so it does not require LaTeX.

## Installation

Create an isolated environment and install the package:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,voiceover-gtts]"
```

PowerShell activation:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,voiceover-gtts]"
```

Install `.[voiceover-openai]` or `.[voiceover-azure]` instead when using those
services.

## Narration and TTS

Scenes use
[manim-voiceover](https://voiceover.manim.community/) directly rather than a
repository-specific TTS abstraction. Narration is split into short blocks;
animations inside each block use the returned tracker's duration.

`MANIM_TTS_PROVIDER` selects the provider:

| Value | Setup |
|---|---|
| `none` | Default. Silent deterministic draft; no service or credentials. |
| `gtts` | Recommended simple narrated provider; network access, no API key. |
| `openai` | Set `OPENAI_API_KEY`; optional `OPENAI_TTS_VOICE` defaults to `alloy`. |
| `azure` | Set `AZURE_SUBSCRIPTION_KEY` and `AZURE_SERVICE_REGION`. |

No credentials are stored in the repository. Provider SDK behavior and
supported voices are controlled by the installed `manim-voiceover` version.

```bash
export MANIM_TTS_PROVIDER=gtts
```

```powershell
$env:MANIM_TTS_PROVIDER = "gtts"
```

If optional voiceover dependencies are unavailable, leave the provider as
`none`. The example preserves narration blocks and approximate pacing but
produces a silent development render.

## Render the minimal example

```bash
./scripts/render.sh examples/minimal/scene.py MinimalExplainer
```

On PowerShell:

```powershell
.\scripts\render.ps1 examples\minimal\scene.py MinimalExplainer
```

The scripts use Manim's high-quality preset (`-qh`). Override it while
iterating:

```bash
MANIM_QUALITY=-ql ./scripts/render.sh examples/minimal/scene.py MinimalExplainer
```

```powershell
$env:MANIM_QUALITY = "-ql"
.\scripts\render.ps1 examples\minimal\scene.py MinimalExplainer
```

Manim writes output below `media/videos/`.

## Use the skill from an agent

Tell the agent explicitly to read the skill and apply it to the source material:

```text
Use skills/technical-manim-explainer/SKILL.md to create a narrated explainer
of DDTree tree construction. Assume I understand standard speculative
decoding. Use two worked examples and ground the explanation in the paper and
implementation. Follow MANIM_GUIDE.md, render, inspect, and revise the result.
Return the final MP4, scene source, and reproduction command.
```

The skill treats storyboard, narration design, rendering, inspection, and
revision as implicit parts of the request.

## Add reusable components

Start visuals inside a scene. Promote one into `manim_lib` only after its
semantics and API recur across explainers. Keep promoted components small:

- represent a recognizable technical object or state;
- expose stable semantic operations such as `set_state` or `highlight_path`;
- avoid topic-specific orchestration;
- include a concise docstring and focused test;
- preserve Manim objects so scenes can animate them directly.

Do not turn `manim_lib` into a generic graph, slide, or agent framework.
