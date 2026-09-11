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
-> records a compact teaching contract and exact source claims
-> designs the final visual discovery
-> sketches opening, mechanism, and payoff
-> storyboards cause and effect
-> writes rough Manim
-> renders a rough silent animation
-> refines the picture and synchronizes narration
-> renders production with an explicit provider
-> reviews the actual video, audio, and transition frames
-> repairs and validates within a bounded budget
-> records review against the run manifest and artifact hashes
-> returns MP4 + source + reproducible evidence, with acceptance status
```

The architecture stays deliberately small:

- `skills/technical-manim-explainer/SKILL.md` defines the end-to-end method and
  quality bar.
- `skills/technical-manim-explainer/MANIM_GUIDE.md` contains Manim-specific
  house rules; stage-specific references are loaded only when needed.
- `manim_lib/` provides reusable semantic visual components.
- `examples/` shows how a scene combines those pieces.
- `scripts/render.*` is the rendering workflow.

Local contracts, manifests, review records, and reports support the agent;
they do not turn this repository into an autonomous LLM API framework.

## Requirements

- Git and **Python 3.12 recommended** (`.python-version`); Python 3.11-3.13
  remain supported. Install Python with [uv](https://docs.astral.sh/uv/getting-started/installation/)
  or [python.org](https://www.python.org/downloads/).
- [uv](https://docs.astral.sh/uv/) is the recommended installer: it uses the
  committed `uv.lock`. It is optional; ordinary pip installation also works.
- Manim's native libraries/build tools where needed, as listed below.
- FFmpeg for video/audio assembly is supplied by the direct `imageio-ffmpeg`
  dependency on platforms with a bundled wheel. A system `ffmpeg` on `PATH`
  takes precedence; install one yourself if no bundled binary is available.
- **LaTeX is optional**, only for scenes using `MathTex` or `Tex`. Those scenes
  need a LaTeX distribution and `dvisvgm`; follow
  [Manim's LaTeX instructions](https://docs.manim.community/en/v0.19.0/installation/uv.html#step-2-optional-installing-latex).

The quick start uses `Text`, not LaTeX. **No API keys, narration service, or
environment activation are required to install or render it.**

## Installation

### Quick start

Clone the repository and enter it (all following commands run from this root):

```bash
git clone https://github.com/Eliran-Turgeman/visual-research.git
cd visual-research
```

First install native prerequisites for your platform:

- **Windows:** use a supported 64-bit Python installation. The standard
  Windows wheels supply Manim's Cairo/Pango dependencies; no separate native
  installation is normally needed.
- **Ubuntu/Debian:** install a compiler, Python development headers, Cairo,
  Pango, and `pkg-config`:

  ```bash
  sudo apt update
  sudo apt install -y build-essential python3-dev libcairo2-dev libpango1.0-dev pkg-config
  ```

  If your Python comes from the distribution, also install its matching
  `venv` package (for example `python3-venv`) for the pip route.
- **macOS:** install [Homebrew](https://brew.sh/) and Xcode Command Line Tools
  (run `xcode-select --install` if they are absent), then:

  ```bash
  brew install cairo pango pkg-config
  ```

These recommendations come from the version-matched
[Manim installation guide](https://docs.manim.community/en/v0.19.0/installation/uv.html),
[Pycairo](https://pycairo.readthedocs.io/en/latest/getting_started.html), and
[ManimPango build instructions](https://github.com/ManimCommunity/ManimPango#building).
Source builds need a C compiler and headers matching the selected Python.
Other distributions/architectures may need their equivalent native packages.

**Windows PowerShell — one setup command, then a silent managed render:**

```powershell
.\scripts\setup.ps1
.\scripts\render.ps1 examples\minimal\scene.py MinimalExplainer `
  --profile draft --provider none --output-dir media\runs --run-id minimal-draft-01
```

**macOS/Linux — one setup command, then the same render:**

```bash
./scripts/setup.sh
./scripts/render.sh examples/minimal/scene.py MinimalExplainer \
  --profile draft --provider none --output-dir media/runs --run-id minimal-draft-01
```

Setup creates/reuses `.venv`, installs the editable package, and runs the local
doctor without checking credentials. The render wrappers select `.venv`
automatically; no activation is needed. Expect these files:

```text
media/runs/minimal-draft-01/video.mp4
media/runs/minimal-draft-01/timeline.json
media/runs/minimal-draft-01/manifest.json
```

The manifest should say `"status": "rendered"` and both JSON files should
identify `minimal-draft-01`. Use a **fresh run ID** for each later render.
This verifies installation and artifact generation, not production acceptance.

### Installer and Python selection

Both setup wrappers accept the same options:

| Option | Behavior |
|---|---|
| `--installer auto` (default) | Use uv if installed, otherwise pip. |
| `--installer uv` | Use the committed lock with uv; install uv first. |
| `--installer pip` | Use ordinary editable pip installation; does not consume `uv.lock`. |
| `--python PYTHON` | Select a supported Python version/executable, e.g. `3.12`; use an installed executable for pip. |
| `--provider none` (default) | Request the base silent-render dependencies, without a TTS extra. |
| `--dev` | Also install the test dependencies. |

For example, explicitly select pip with `.\scripts\setup.ps1 --installer pip`
or `./scripts/setup.sh --installer pip`. Use `--help` for the complete CLI.
Python 3.12 is the default for new environments; use `--python` to select
3.11 or 3.13 deliberately. Setup does not install OS packages.

For a manual uv workflow, `uv sync --locked` installs the minimal environment
from the lock; `uv lock --check` verifies that it still matches `pyproject.toml`.
Use `uv lock` to regenerate it only when deliberately changing dependencies,
and commit the updated lock with the manifest change.

Manual pip remains supported if you prefer to manage the environment yourself:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts\doctor.py
```

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python scripts/doctor.py
```

### Check installation or narration readiness

The doctor uses the standard library, makes no network requests, and defaults
to silent mode. Run it with the interpreter you want to check; even an
incomplete environment can report missing dependencies:

```powershell
.\.venv\Scripts\python.exe scripts\doctor.py --scene examples\minimal\scene.py
.\.venv\Scripts\python.exe scripts\doctor.py --provider openrouter
```

```bash
.venv/bin/python scripts/doctor.py --scene examples/minimal/scene.py
.venv/bin/python scripts/doctor.py --provider openrouter
```

`--json` produces machine-readable diagnostics. `--require-tex` checks LaTeX
even when a helper hides its use from scene inspection. `--skip-credentials`
checks installed tooling without requiring service keys; setup always uses
this mode for its selected provider. Without that flag, readiness for a chosen
keyed provider requires its environment variables, but does not validate them
against the remote service. No keys are required for installation itself.

### Optional development and TTS dependencies

Keep development dependencies separate from the minimal installation:

```powershell
.\scripts\setup.ps1 --dev
.\.venv\Scripts\python.exe -m pytest
```

```bash
./scripts/setup.sh --dev
.venv/bin/python -m pytest
```

To add narration dependencies, rerun setup with **one explicitly chosen**
provider: `none`, `openrouter`, `gtts`, `external-gtts`, `openai`, or `azure`.
For example, `.\scripts\setup.ps1 --provider openrouter` or
`./scripts/setup.sh --provider openrouter`. Add `--dev` when setting up an
environment that should also run tests. Setup preserves unrelated installed
packages in an existing compatible `.venv`; use a fresh environment to verify
a base-only installation.

The `voiceover-openai` and `voiceover-openrouter` extras require incompatible
OpenAI SDK major versions; choose one per environment rather than
`--all-extras`. gTTS and Azure do not share that restriction.

Manual pip users can install `-e ".[dev]"`, `-e ".[voiceover-openrouter]"`,
`-e ".[voiceover-gtts]"` (also for `external-gtts`),
`-e ".[voiceover-openai]"`, or `-e ".[voiceover-azure]"` with their `.venv`
interpreter. Configure credentials only when you choose narration; setup
never prompts for or writes keys. Selecting extras does not itself enable TTS.

### Clean-install CI

[Installation CI](.github/workflows/installation.yml) starts from a fresh
checkout/environment on Windows, macOS, and Linux for **both uv and pip** with
Python 3.12. Additional Linux uv runs cover Python 3.11 and 3.13. It checks
lock consistency, executes the actual setup/render wrappers and doctor, and
verifies a tiny silent, no-LaTeX MP4 against its rendered manifest and timeline.
A separate job runs focused offline installation tests with the dev extra.
Neither installation smoke tests nor the doctor call paid TTS services.

## Narration and TTS

Scenes use
[manim-voiceover](https://voiceover.manim.community/) directly rather than a
repository-specific TTS abstraction. Narration is split into short blocks;
animations inside each block use the returned tracker's duration.

`MANIM_TTS_PROVIDER` selects the provider:

| Value | Setup |
|---|---|
| `none` | Silent deterministic draft; no service or credentials. |
| `openrouter` | Explicit OpenRouter selection; requires `OPENROUTER_API_KEY`. Defaults to MAI-Voice-2 / Harper. |
| `gtts` | Explicit networked speech; no API key. Useful for speech drafts. |
| `external-gtts` | Explicit networked gTTS with external audio assembly; uses the `voiceover-gtts` extra, no API key. |
| `openai` | Set `OPENAI_API_KEY`; managed defaults are `tts-1-hd`, voice `alloy`, speed `1`. |
| `azure` | Set `AZURE_SUBSCRIPTION_KEY` and `AZURE_SERVICE_REGION`. |

Keep credentials outside source and artifacts. Provider/model capabilities
depend on the installed `manim-voiceover` service and selected provider.
Audition difficult terms before full synthesis, keep a pronunciation glossary,
and reuse valid unchanged speech clips. OpenAI TTS deliveries must clearly
disclose that the voice is AI-generated.

See [narration controls and cache recovery](skills/technical-manim-explainer/references/narration.md)
for supported configuration, retries, delivery stability, and final listening.
Silent mode preserves narration blocks and approximate pacing; it is not
equivalent to reviewing final speech.

## Render a managed episode

The generic wrappers forward options to `scripts/render.py`. Start with the
compact timeline example, which emits the required narration timeline.

```bash
./scripts/render.sh examples/speculative_decoding_timeline/scene.py \
  SpeculativeDecodingTimeline --profile draft --provider none \
  --output-dir media/runs --run-id timeline-draft-01
```

On PowerShell:

```powershell
.\scripts\render.ps1 examples\speculative_decoding_timeline\scene.py `
  SpeculativeDecodingTimeline --profile draft --provider none `
  --output-dir media\runs --run-id timeline-draft-01
```

| Profile | Default quality | Narration and completion |
|---|---|---|
| `draft` (default) | `-ql`, 480p15 | Silent unless a provider is explicitly selected by option/environment; keys alone never opt in |
| `production` | `-qh`, 1080p60 | Requires an explicit non-silent provider; fully decodes and checks expected video/audio/timeline before marking the run `rendered` |

For production, configure the provider credentials in the process first.
This example explicitly selects OpenRouter's MAI-Voice-2 / Harper defaults:

```powershell
.\scripts\render.ps1 examples\speculative_decoding_timeline\scene.py `
  SpeculativeDecodingTimeline --profile production --provider openrouter `
  --output-dir media\runs --run-id timeline-production-01
```

Use a fresh run ID each time. For these explicit output directories, the
run-specific files are:

```text
media\runs\timeline-production-01\manifest.json
media\runs\timeline-production-01\timeline.json
media\runs\timeline-production-01\video.mp4
```

The run also contains `media`, `audio`, and `work` directories. Do not mix a
video from one run with another run's timeline. Reusable speech is separate
from those run artifacts: by default the cache is
`media\voiceovers\<provider>\`, shared across runs in this worktree.
`--cache-dir CACHE_ROOT` overrides `MANIM_TTS_CACHE_ROOT`, which overrides the
repository default; the effective cache always adds the provider subdirectory.
An explicit common root can share valid speech across worktrees.

Consumed audio is copied by hash into each run's `audio` directory before
Manim reads it, so later cache changes do not mutate the retained run assets.
The manifest records the effective cache location and actual audio references,
not invented hit/request counts or savings. See
[cache controls and recovery](skills/technical-manim-explainer/references/narration.md#cache-reuse-and-recovery).

The manifest also records source
revision/fingerprints, effective non-secret settings, environment versions,
verified media metadata and hashes, and elapsed render/validation time—not
human acceptance, inferred API cost, or a promise of bit-identical speech.
Declare external or untracked source inputs with repeatable `--source-file`.
Source drift during rendering fails finalization.

`--quality` overrides `MANIM_QUALITY`, which overrides the profile default.
Use an equals sign for dash-prefixed quality values, for example
`--quality=-ql`. Explicit `--provider` overrides `MANIM_TTS_PROVIDER`; clear
that environment variable or use `--provider none` for a guaranteed silent
draft. Provider `--model`, `--voice`, `--speed`, `--style`, and `--style-degree`
options override corresponding supported environment controls; unsupported
combinations fail rather than being silently ignored.

The wrappers use `MANIM_PYTHON` when set, otherwise the local `.venv` interpreter
when available, then `python`. Inspect the complete interface without rendering:

```powershell
.\scripts\render.ps1 --help
python scripts\render.py --help
```

Managed scenes subclass `NarratedScene` or emit its explicit timeline protocol.
`narrate(..., beat_id=...)` and `record_visual_event(...)` can connect actual
rendered times to teaching beats and transitions. The wrapper preflights direct
`Tex`/`MathTex`; use `--require-tex` for helper-mediated LaTeX use.

## Direct Manim: minimal escape hatch

The minimal example also supports the managed workflow through `NarratedScene`,
including beat IDs and actual visual-event timestamps:

```powershell
.\scripts\render.ps1 examples\minimal\scene.py MinimalExplainer `
  --profile draft --provider none --output-dir media\runs --run-id minimal-draft-01
```

For a direct render without a managed run manifest, use Manim itself:

```powershell
$env:MANIM_TTS_PROVIDER = "none"
.\.venv\Scripts\python.exe -m manim -ql examples\minimal\scene.py MinimalExplainer
```

```bash
MANIM_TTS_PROVIDER=none .venv/bin/python -m manim -ql examples/minimal/scene.py MinimalExplainer
```

The output is `media/videos/scene/480p15/MinimalExplainer.mp4`. Direct Manim
remains available for stills, experiments, and unsupported scene protocols;
it does not automatically provide profiles, run manifests, or acceptance.
The minimal scene uses `Text`, so this escape hatch does not require LaTeX.

## Examples

Names describe the subject or the component being demonstrated.

| Example | What it demonstrates |
|---|---|
| [`minimal`](examples/minimal/) | A minimal narrated scene |
| [`continuity`](examples/continuity/) | Object identity across visual transformations |
| [`visual_components`](examples/visual_components/) | Token states, probability bars, trees, and matrices in one reference frame |
| [`speculative_decoding_flow`](examples/speculative_decoding_flow/) | Model and token flow for block drafting and batched verification |
| [`speculative_decoding_timeline`](examples/speculative_decoding_timeline/) | Canonical compact example: sequential drafting overhead and batched verification on a shared time scale |
| [`dflash_visual`](examples/dflash_visual/) | DFlash block-diffusion drafting |
| [`ddtree_visual`](examples/ddtree_visual/) | DDTree construction and verification |
| [`ddtree_dflash`](examples/ddtree_dflash/) | DFlash and DDTree with worked algorithm examples |
| [`ddtree_full`](examples/ddtree_full/) | Canonical complete episode: source-backed DDTree with worked computations and MAI narration |

## Use the skill from an agent

Tell the agent explicitly to read the skill and apply it to the source material:

```text
Use skills/technical-manim-explainer/SKILL.md to create a narrated explainer
of DDTree tree construction. Assume I understand standard speculative
decoding. Use two worked examples and ground the explanation in the paper and
implementation. Record a compact teaching contract with source versions and
one or two transfer questions and expected answers. Follow the Manim guide;
draft silently, choose production narration explicitly, then review, repair,
and validate against the actual audiovisual artifact within a bounded budget.
Return the MP4, source, reproduction command, manifest, and honest review status.
```

The skill treats storyboard, narration design, rendering, inspection, and
revision as implicit parts of the request.

## Production acceptance and evidence

A rendered MP4 is not automatically accepted. Keep three judgments separate:

| Judgment | Evidence |
|---|---|
| Technical correctness | Exact source claims, assumptions, verified worked values, semantic tests |
| Production quality | Readable frames, transition inspection, complete final audiovisual playback |
| Teaching and learner understanding | Objective/misconception review, transfer questions and expected answers; actual learner responses if collected |

Use a bounded **review → repair → validate** loop: timestamp each finding,
repair its root cause, rerun affected checks, and refresh evidence for the
new artifact. Tie the review record to the run manifest and video/timeline
hashes. Do not use agent confidence, still-frame sampling, or file existence
as an acceptance shortcut. If full listening/playback was not possible, report
**rendered, acceptance pending** rather than inventing approval.

Read the [production review procedure](skills/technical-manim-explainer/references/production-review.md)
at that stage, and the [teaching contract reference](skills/technical-manim-explainer/references/teaching-contract.md)
when planning. Teaching review is not measured evidence of learning gains.

## Measure the accepted result

Track failed and repaired attempts as well as accepted videos. Report known
cost per accepted result, unknown costs explicitly, and human correction time
separately from render/API time. Cache reuse and silent drafts avoid unnecessary
work; do not invent TTS, subscription, or local-render savings from unrelated
API pricing features.

Comparing cheap/strong models is an **optional experiment**, not an implemented
autonomous router. Hold acceptance criteria and tasks fixed and compare cost
per accepted result rather than token price alone. See
[measurement and verified engineering references](skills/technical-manim-explainer/references/measurement.md).
Vendor workflow advice is not evidence of improved learner outcomes.

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
Use its [documented reproduction commands](examples/ddtree_full/README.md);
select production narration deliberately rather than relying on key presence.

Render `examples/visual_components/scene.py` as a still whenever the shared visual
language changes. It puts the core object families in one frame so hierarchy,
contrast, spacing, and semantic color can be reviewed together. It is a
component reference, not the layout template for every explainer.

The goal is not to copy another creator's assets. It is to apply the strongest
ideas behind visual-first mathematical explanation: preserve object identity,
construct ideas progressively, let color carry meaning, and give every motion
a teaching purpose.
