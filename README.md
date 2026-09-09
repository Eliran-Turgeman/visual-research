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
-> designs the final visual discovery
-> sketches opening, mechanism, and payoff
-> storyboards cause and effect
-> writes rough Manim
-> renders a rough silent animation
-> refines the picture and synchronizes narration
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
python -m pip install -e ".[dev,voiceover-openrouter]"
```

PowerShell activation:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,voiceover-openrouter]"
```

Install `.[voiceover-gtts]`, `.[voiceover-openai]`, or
`.[voiceover-azure]` instead when using those services.

## Narration and TTS

Scenes use
[manim-voiceover](https://voiceover.manim.community/) directly rather than a
repository-specific TTS abstraction. Narration is split into short blocks;
animations inside each block use the returned tracker's duration.

`MANIM_TTS_PROVIDER` selects the provider:

| Value | Setup |
|---|---|
| `none` | Silent deterministic draft; no service or credentials. |
| `openrouter` | Production default when `OPENROUTER_API_KEY` exists. Uses MAI-Voice-2 with the Harper voice. |
| `gtts` | Free draft provider; network access, no API key. |
| `openai` | Set `OPENAI_API_KEY`; optional `OPENAI_TTS_VOICE` defaults to `alloy`. |
| `azure` | Set `AZURE_SUBSCRIPTION_KEY` and `AZURE_SERVICE_REGION`. |

No credentials are stored in the repository. Provider SDK behavior and
supported voices are controlled by the installed `manim-voiceover` version.

OpenRouter narration uses these environment variables:

```text
OPENROUTER_API_KEY                 required
OPENROUTER_TTS_MODEL               default: microsoft/mai-voice-2
OPENROUTER_TTS_VOICE               default: en-US-Harper:MAI-Voice-2
OPENROUTER_TTS_SPEED               default: 0.96
OPENROUTER_TTS_STYLE               optional Azure style
OPENROUTER_TTS_STYLE_DEGREE        optional style strength
```

When `OPENROUTER_API_KEY` exists, the example selects OpenRouter automatically.
Override it with `MANIM_TTS_PROVIDER=none` for a silent draft or
`MANIM_TTS_PROVIDER=gtts` for free TTS. Silent mode preserves narration blocks
and approximate pacing.

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

## Examples

Names describe the subject or the component being demonstrated.

| Example | What it demonstrates |
|---|---|
| [`minimal`](examples/minimal/) | A minimal narrated scene |
| [`continuity`](examples/continuity/) | Object identity across visual transformations |
| [`visual_components`](examples/visual_components/) | Token states, probability bars, trees, and matrices in one reference frame |
| [`speculative_decoding_flow`](examples/speculative_decoding_flow/) | Model and token flow for block drafting and batched verification |
| [`speculative_decoding_timeline`](examples/speculative_decoding_timeline/) | Sequential drafting overhead and batched verification on a shared time scale |
| [`dflash_visual`](examples/dflash_visual/) | DFlash block-diffusion drafting |
| [`ddtree_visual`](examples/ddtree_visual/) | DDTree construction and verification |
| [`ddtree_dflash`](examples/ddtree_dflash/) | DFlash and DDTree with worked algorithm examples |
| [`ddtree_full`](examples/ddtree_full/) | The complete MAI-narrated DDTree episode |

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

## Visual language

Start with the picture that explains the mechanism, not the component library.
The final relationship should be visible before a caption names it. Define
what each shape, position, color, and motion means; then reuse `TokenBox`,
`TreeNode`, `LabeledMatrix`, or `ProbabilityDistribution` where their semantics
fit. Keep new representations scene-local until they recur.

The shared palette and typography provide cohesion without forcing every
concept into a rounded box. Shadows, inner borders, and halos are optional,
not a substitute for scale, meaningful geometry, and causal motion.

`examples/speculative_decoding_timeline/` demonstrates the approach with a
shared-clock comparison: three serial target passes versus drafting plus one
verification pass. A completion bracket reveals the difference in elapsed time.
`examples/speculative_decoding_flow/` uses model blocks and token flow instead.

For a complete mechanism-first episode with MAI narration, see
`examples/ddtree_full/`: DFlash marginals, seven best-first tree selections,
flattening, ancestor-only attention, and a target-driven output walk.
Run `.\examples\ddtree_full\render.ps1` in PowerShell; it loads the configured
OpenRouter key from the process or Windows user environment without printing
it and selects MAI-Voice-2 / Harper explicitly.

Render `examples/visual_components/scene.py` as a still whenever the shared visual
language changes. It puts the core object families in one frame so hierarchy,
contrast, spacing, and semantic color can be reviewed together. It is a
component reference, not the layout template for every explainer.

The goal is not to copy another creator's assets. It is to apply the strongest
ideas behind visual-first mathematical explanation: preserve object identity,
construct ideas progressively, let color carry meaning, and give every motion
a teaching purpose.
