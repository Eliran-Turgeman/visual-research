"""Narrated explainer for DFlash drafting and DDTree verification."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from manim import (
    BLUE,
    DARK_GRAY,
    DOWN,
    FadeIn,
    FadeOut,
    GREEN,
    GREY_B,
    Group,
    LaggedStart,
    LEFT,
    Line,
    MathTex,
    ORANGE,
    RED,
    RIGHT,
    RoundedRectangle,
    Scene,
    SurroundingRectangle,
    Text,
    Transform,
    UP,
    VGroup,
    WHITE,
    Write,
    YELLOW,
)

from algorithm import Q1, Q2, Q3, best_first_prefixes
from manim_lib import (
    Computation,
    EquationSteps,
    LabeledMatrix,
    Operand,
    StableTree,
    TokenBox,
    TokenSequence,
    TokenState,
    TreeNode,
)

try:
    from manim_voiceover import VoiceoverScene
except ImportError:
    VoiceoverScene = Scene


BG = "#10141C"
PANEL = "#1B2330"
MUTED = "#AAB4C3"
PURPLE = "#B38CFF"
CYAN = "#55DDE0"

# Universal narration review timeline: written after every successful
# construct(), regardless of TTS provider, so the frame-extraction tooling in
# scripts/extract_narration_frames.py has actual rendered start/end
# timestamps for every narration block to sample. Direct renders use this
# gitignored default; managed renders override it with MANIM_TIMELINE_PATH.
REVIEW_TIMELINE_PATH = Path("media/review/ddtree_dflash/timeline.json")

# Exposed at module scope (rather than kept local to best_first_example) so
# an integration layout test can build the exact same 7-node tree geometry
# the scene renders and check it for collisions, instead of duplicating
# these numbers and silently drifting from the real scene.
BEST_FIRST_RADIUS = 0.40
BEST_FIRST_POSITIONS = {
    "root": (0.0, 0.80, 0),
    "the": (-1.9, -0.35, 0),
    "a": (1.9, -0.35, 0),
    "the-model": (-2.3, -1.50, 0),
    "the-system": (-0.7, -1.50, 0),
    "a-model": (1.9, -1.50, 0),
    "the-model-works": (-2.3, -2.65, 0),
    "a-model-works": (1.9, -2.65, 0),
}
BEST_FIRST_SCORE_STYLE = {"direction": DOWN, "buff": 0.06, "font_size": 14}


class DDTreeDFlashExplainer(VoiceoverScene):
    """Explain how DFlash and DDTree cooperate in one decoding round."""

    def setup(self):
        super().setup()
        self.camera.background_color = BG
        self._voiceover_enabled = False
        self._external_voiceover = False
        self._external_tracks = []
        # Universal, provider-independent record of every narration block's
        # actual rendered start/end timestamps. Populated once, in narrate()'s
        # finally clause, no matter which TTS branch ran.
        self._review_blocks = []
        self._review_events = []
        self._review_run_id = os.getenv("MANIM_RUN_ID")
        self._review_timeline_path = Path(
            os.getenv("MANIM_TIMELINE_PATH") or REVIEW_TIMELINE_PATH
        )
        default_provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "none"
        provider = os.getenv("MANIM_TTS_PROVIDER", default_provider).lower()
        if provider == "openrouter":
            from manim_lib.openrouter_voiceover import (
                DEFAULT_OPENROUTER_TTS_MODEL,
                DEFAULT_OPENROUTER_TTS_VOICE,
                OpenRouterSpeechService,
            )

            style_degree = os.getenv("OPENROUTER_TTS_STYLE_DEGREE")
            self.set_speech_service(
                OpenRouterSpeechService(
                    model=os.getenv(
                        "OPENROUTER_TTS_MODEL", DEFAULT_OPENROUTER_TTS_MODEL
                    ),
                    voice=os.getenv(
                        "OPENROUTER_TTS_VOICE", DEFAULT_OPENROUTER_TTS_VOICE
                    ),
                    speed=float(os.getenv("OPENROUTER_TTS_SPEED", "0.96")),
                    style=os.getenv("OPENROUTER_TTS_STYLE"),
                    style_degree=(
                        float(style_degree) if style_degree is not None else None
                    ),
                )
            )
            self._voiceover_enabled = True
        elif provider == "gtts":
            from manim_voiceover.services.gtts import GTTSService

            self.set_speech_service(GTTSService(lang="en", tld="com"))
            self._voiceover_enabled = True
        elif provider == "openai":
            from manim_voiceover.services.openai import OpenAIService

            self.set_speech_service(
                OpenAIService(voice=os.getenv("OPENAI_TTS_VOICE", "alloy"))
            )
            self._voiceover_enabled = True
        elif provider == "azure":
            from manim_voiceover.services.azure import AzureService

            self.set_speech_service(AzureService())
            self._voiceover_enabled = True
        elif provider == "external-gtts":
            self._external_voiceover = True
            self._external_dir = Path("media/voiceovers/ddtree_external").resolve()
            self._external_dir.mkdir(parents=True, exist_ok=True)
        elif provider != "none":
            raise ValueError(
                "MANIM_TTS_PROVIDER must be none, openrouter, gtts, "
                "external-gtts, openai, or azure"
            )

    @contextmanager
    def narrate(self, text: str, *, beat_id: str | None = None):
        """Provider-agnostic narration block.

        Every branch below yields a tracker to the caller's ``with`` body, but
        the actual scene-clock start/end bookkeeping lives in exactly one
        place: the outer ``finally``. That keeps the four providers (voiceover
        services, external gTTS, and silent) from each re-implementing their
        own copy of the same recording logic, and guarantees a block is
        recorded (with whatever start/end it reached) even if the caller's
        body raises, instead of leaving ``_review_blocks`` silently short.
        The nested ``with self.voiceover(...)`` still runs its own cleanup
        (including its synchronization wait) via the normal context-manager
        protocol before our ``finally`` observes ``self.time``.
        """
        index = len(self._review_blocks)
        start = self.time
        try:
            if self._voiceover_enabled:
                with self.voiceover(text=text) as tracker:
                    yield tracker
            elif self._external_voiceover:
                from gtts import gTTS
                from mutagen.mp3 import MP3

                digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
                audio_path = self._external_dir / f"{digest}.mp3"
                if not audio_path.exists():
                    gTTS(text=text, lang="en", tld="com").save(str(audio_path))
                duration = MP3(audio_path).info.length
                track_start = start
                tracker = SimpleNamespace(duration=duration)
                yield tracker
                remaining = duration - (self.time - track_start)
                if remaining > 0:
                    self.wait(remaining)
                self._external_tracks.append(
                    {
                        "start": track_start,
                        "duration": duration,
                        "file": str(audio_path),
                        "text": text,
                    }
                )
            else:
                yield SimpleNamespace(duration=max(1.8, len(text.split()) / 2.65))
        finally:
            end = self.time
            block = {
                "index": index,
                "start": start,
                "end": end,
                "duration": end - start,
                "text": text,
            }
            if beat_id is not None:
                block["beat_id"] = beat_id
            self._review_blocks.append(block)

    def paced(self, tracker, *animations, fraction=0.58, minimum=0.7, maximum=4.5):
        run_time = min(maximum, max(minimum, tracker.duration * fraction))
        self.play(*animations, run_time=run_time)

    def heading(self, text: str, color=WHITE):
        heading = Text(text, font_size=38, weight="BOLD", color=color)
        if heading.width > 12.2:
            heading.scale_to_fit_width(12.2)
        return heading.to_edge(UP)

    def label(self, text: str, size=24, color=WHITE):
        return Text(text, font_size=size, color=color)

    def panel(self, width: float, height: float):
        return RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.12,
            stroke_color=GREY_B,
            stroke_width=1.5,
            fill_color=PANEL,
            fill_opacity=0.75,
        )

    def clear_stage(self, *keep):
        keep_ids = {id(mob) for mob in keep}
        removable = [mob for mob in self.mobjects if id(mob) not in keep_ids]
        if removable:
            self.play(FadeOut(Group(*removable)), run_time=0.55)

    def construct(self):
        self.opening()
        self.dflash_mechanism()
        self.marginals_not_conditionals()
        self.why_a_tree()
        self.tree_objective()
        self.best_first_example()
        self.tree_verification()
        self.lossless_commit()
        self.system_tradeoff()
        if self._external_voiceover:
            manifest = {
                "scene_duration": self.time,
                "tracks": self._external_tracks,
            }
            (self._external_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )
        self._write_review_timeline()

    def _write_review_timeline(self):
        """Write the universal, provider-independent narration review timeline.

        Only reached once construct() has run every section without raising,
        so failed construction publishes nothing. Managed renders select a
        run-specific destination with MANIM_TIMELINE_PATH and provenance with
        MANIM_RUN_ID; direct renders retain the historical default path.
        """
        timeline = {
            "schema_version": 1,
            "scene_duration": self.time,
            "blocks": self._review_blocks,
            "events": self._review_events,
        }
        if self._review_run_id is not None:
            timeline["run_id"] = self._review_run_id
        path = self._review_timeline_path
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_name(
            f".{path.name}.{uuid4().hex}.writing"
        )
        try:
            pending.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)

    def opening(self):
        title = self.heading("DFlash + DDTree", color=CYAN)
        subtitle = self.label(
            "Parallel draft distributions -> one tree -> one exact target step",
            size=25,
            color=MUTED,
        ).next_to(title, DOWN, buff=0.3)

        ar_panel = self.panel(5.4, 2.0).shift(LEFT * 3.1 + DOWN * 0.5)
        tree_panel = self.panel(5.4, 2.0).shift(RIGHT * 3.1 + DOWN * 0.5)
        ar_label = self.label("Autoregressive target", 24).next_to(
            ar_panel.get_top(), DOWN, buff=0.25
        )
        tree_label = self.label("DFlash + DDTree round", 24, CYAN).next_to(
            tree_panel.get_top(), DOWN, buff=0.25
        )

        ar_steps = VGroup(
            *[
                RoundedRectangle(
                    width=0.85,
                    height=0.65,
                    corner_radius=0.08,
                    stroke_color=ORANGE,
                    fill_color=ORANGE,
                    fill_opacity=0.16,
                )
                for _ in range(4)
            ]
        ).arrange(RIGHT, buff=0.25)
        ar_steps.move_to(ar_panel).shift(DOWN * 0.2)
        for index, box in enumerate(ar_steps):
            box.add(self.label(f"T{index + 1}", 19, ORANGE).move_to(box))

        draft_box = RoundedRectangle(
            width=1.7,
            height=0.7,
            corner_radius=0.08,
            stroke_color=BLUE,
            fill_color=BLUE,
            fill_opacity=0.18,
        )
        draft_box.add(self.label("draft", 21, BLUE).move_to(draft_box))
        verify_box = RoundedRectangle(
            width=2.2,
            height=0.7,
            corner_radius=0.08,
            stroke_color=GREEN,
            fill_color=GREEN,
            fill_opacity=0.18,
        )
        verify_box.add(self.label("tree verify", 21, GREEN).move_to(verify_box))
        round_steps = VGroup(draft_box, verify_box).arrange(RIGHT, buff=0.35)
        round_steps.move_to(tree_panel).shift(DOWN * 0.2)

        with self.narrate(
            "The expensive target model normally advances one token per decode pass. "
            "Speculative decoding wins only when one target pass commits several tokens."
        ) as tracker:
            self.paced(tracker, Write(title), FadeIn(subtitle), fraction=0.32)
            self.paced(
                tracker,
                FadeIn(ar_panel),
                FadeIn(ar_label),
                FadeIn(ar_steps),
                fraction=0.48,
            )

        with self.narrate(
            "DFlash makes drafting cheap by predicting a whole block in parallel. "
            "DDTree then spends the verifier budget on several likely continuations, "
            "instead of betting everything on one path."
        ) as tracker:
            self.paced(
                tracker,
                FadeIn(tree_panel),
                FadeIn(tree_label),
                FadeIn(round_steps),
                fraction=0.55,
            )
            self.play(tree_panel.animate.set_stroke(CYAN, width=3), run_time=0.8)

        self.clear_stage()

    def dflash_mechanism(self):
        title = self.heading("1. DFlash produces a block in parallel", color=BLUE)
        context = VGroup(
            TokenBox("the"),
            TokenBox("model"),
            TokenBox("can"),
            TokenBox("b", state=TokenState.ACTIVE),
        ).arrange(RIGHT, buff=0.12)
        context.scale(0.82).shift(UP * 1.75 + LEFT * 2.8)
        context_label = self.label("committed context + bonus token", 20, MUTED)
        context_label.next_to(context, UP, buff=0.18)
        masks = VGroup(
            *[
                TokenBox("[MASK]", state=TokenState.SPECULATIVE, width=1.45)
                for _ in range(3)
            ]
        ).arrange(RIGHT, buff=0.14)
        masks.scale(0.8).next_to(context, RIGHT, buff=0.3)

        target_box = self.panel(3.1, 1.15).shift(LEFT * 4.2 + DOWN * 0.15)
        target_text = self.label("target hidden states", 23, ORANGE).move_to(target_box)
        fusion = self.panel(2.15, 0.8).shift(LEFT * 0.9 + DOWN * 0.15)
        fusion_text = self.label("fuse + project", 21, PURPLE).move_to(fusion)
        draft_layers = VGroup(
            *[
                RoundedRectangle(
                    width=1.45,
                    height=0.8,
                    corner_radius=0.08,
                    stroke_color=BLUE,
                    fill_color=BLUE,
                    fill_opacity=0.15,
                )
                for _ in range(3)
            ]
        ).arrange(RIGHT, buff=0.25)
        draft_layers.shift(RIGHT * 3.25 + DOWN * 0.15)
        for index, layer in enumerate(draft_layers):
            layer.add(self.label(f"draft L{index + 1}", 18, BLUE).move_to(layer))

        arrows = VGroup(
            Line(target_box.get_right(), fusion.get_left(), color=PURPLE),
            Line(fusion.get_right(), draft_layers[0].get_left(), color=PURPLE),
        )
        kv_label = self.label("injected as K/V at every layer", 20, PURPLE)
        kv_label.next_to(draft_layers, DOWN, buff=0.24)
        mask_arrow = Line(masks.get_bottom(), draft_layers.get_top(), color=BLUE)

        with self.narrate(
            "Each round starts with a bonus token, shown in yellow. The target selected "
            "it previously, but has not yet processed it. DFlash appends masked future "
            "positions after that token."
        ) as tracker:
            self.paced(tracker, Write(title), FadeIn(context_label), FadeIn(context))
            self.paced(tracker, FadeIn(masks), fraction=0.35)

        with self.narrate(
            "The previous target pass exposes hidden states from several layers. "
            "DFlash concatenates and projects them, then injects the result as keys and "
            "values into every small draft layer. The drafter therefore reuses the "
            "target's rich context instead of reasoning from scratch."
        ) as tracker:
            self.paced(
                tracker,
                FadeIn(target_box),
                FadeIn(target_text),
                FadeIn(fusion),
                FadeIn(fusion_text),
                FadeIn(arrows),
                fraction=0.48,
            )
            self.paced(
                tracker,
                FadeIn(draft_layers),
                FadeIn(kv_label),
                FadeIn(mask_arrow),
                fraction=0.38,
            )

        distributions = VGroup(
            self.label("q1: the .55 | a .35 | this .10", 22),
            self.label("q2: model .60 | system .30 | code .10", 22),
            self.label("q3: works .52 | runs .28 | fails .20", 22),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.18)
        distributions.to_edge(DOWN, buff=0.4)
        output_arrow = Line(draft_layers.get_bottom(), distributions.get_top(), color=BLUE)

        with self.narrate(
            "One non-causal draft pass predicts all masked positions simultaneously. "
            "Our toy pass returns these three probability distributions. These values "
            "are invented for the example, but every later calculation uses them exactly."
        ) as tracker:
            self.paced(
                tracker,
                FadeIn(output_arrow),
                FadeIn(distributions, shift=UP * 0.15),
                fraction=0.62,
            )

        self.clear_stage()

    def marginals_not_conditionals(self):
        title = self.heading("The crucial limitation: marginals, not a path model")
        target_panel = self.panel(5.7, 3.7).shift(LEFT * 3.25 + DOWN * 0.25)
        draft_panel = self.panel(5.7, 3.7).shift(RIGHT * 3.25 + DOWN * 0.25)
        target_head = self.label("Target: autoregressive", 27, ORANGE).next_to(
            target_panel.get_top(), DOWN, buff=0.3
        )
        draft_head = self.label("DFlash: one parallel pass", 27, BLUE).next_to(
            draft_panel.get_top(), DOWN, buff=0.3
        )

        p_lines = VGroup(
            self.label("p(y1 | context, b)", 23),
            self.label("p(y2 | context, b, y1)", 23),
            self.label("p(y3 | context, b, y1, y2)", 23),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        p_lines.move_to(target_panel).shift(DOWN * 0.15)
        q_lines = VGroup(
            self.label("q1(y1 | context, b)", 23),
            self.label("q2(y2 | context, b)", 23),
            self.label("q3(y3 | context, b)", 23),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.35)
        q_lines.move_to(draft_panel).shift(DOWN * 0.15)
        target_note = self.label("later choices change later logits", 18, MUTED)
        target_note.next_to(p_lines, DOWN, buff=0.35)
        draft_note = self.label("no chosen y1 or y2 inside this pass", 18, MUTED)
        draft_note.next_to(q_lines, DOWN, buff=0.35)

        with self.narrate(
            "The target distribution is path-conditioned. Its distribution for position "
            "three depends on the actual tokens chosen at positions one and two."
        ) as tracker:
            self.paced(
                tracker,
                Write(title),
                FadeIn(target_panel),
                FadeIn(target_head),
                FadeIn(p_lines),
                FadeIn(target_note),
                fraction=0.66,
            )

        with self.narrate(
            "A single DFlash pass cannot provide those conditionals. It provides one "
            "marginal per position, all conditioned on the same earlier context and bonus "
            "token. DDTree deliberately uses the factorized approximation Q: multiply "
            "the appropriate marginal at each depth."
        ) as tracker:
            self.paced(
                tracker,
                FadeIn(draft_panel),
                FadeIn(draft_head),
                FadeIn(q_lines),
                FadeIn(draft_note),
                fraction=0.54,
            )
            formula_steps = EquationSteps(
                r"Q(y_1) = q_1(y_1)",
                r"Q(y_1,y_2) = q_1(y_1)\,q_2(y_2)",
                r"Q(y_1,y_2,y_3) = q_1(y_1)\,q_2(y_2)\,q_3(y_3)",
                font_size=30,
            )
            for equation in formula_steps.equations:
                equation.set_color(CYAN)
            formula_steps.first.to_edge(DOWN, buff=0.35)
            self.paced(tracker, FadeIn(formula_steps.first), fraction=0.1)
            self.paced(tracker, formula_steps.transform(0), fraction=0.08)
            self.paced(tracker, formula_steps.transform(1), fraction=0.07)

        self.clear_stage()

    def why_a_tree(self):
        title = self.heading("2. A single path throws useful probabilities away")
        distributions = VGroup(
            self.label("q1", 23, BLUE),
            self.label("the .55", 21),
            self.label("a .35", 21),
            self.label("this .10", 21),
            self.label("q2", 23, BLUE),
            self.label("model .60", 21),
            self.label("system .30", 21),
            self.label("code .10", 21),
            self.label("q3", 23, BLUE),
            self.label("works .52", 21),
            self.label("runs .28", 21),
            self.label("fails .20", 21),
        ).arrange_in_grid(rows=3, cols=4, buff=(0.45, 0.24))
        distributions.shift(UP * 0.9)

        path = VGroup(
            TokenBox("b", state=TokenState.ACTIVE),
            TokenBox("the", state=TokenState.SPECULATIVE),
            TokenBox("model", state=TokenState.SPECULATIVE),
            TokenBox("works", state=TokenState.SPECULATIVE),
        ).arrange(RIGHT, buff=0.12)
        path.scale(0.85).shift(DOWN * 1.1)
        path_label = self.label("vanilla DFlash: argmax at each position", 22, MUTED)
        path_label.next_to(path, DOWN, buff=0.25)

        with self.narrate(
            "Vanilla DFlash collapses each column to one token. Here that creates the "
            "single proposal: the, model, works."
        ) as tracker:
            self.paced(tracker, Write(title), FadeIn(distributions), fraction=0.48)
            self.paced(tracker, FadeIn(path), FadeIn(path_label), fraction=0.35)

        bad_choice = self.label(
            "target chooses 'a' first -> zero speculative tokens match",
            25,
            RED,
        ).to_edge(DOWN, buff=0.3)
        rejected = path[1].copy().set_state(TokenState.REJECTED)
        rejected.move_to(path[1])

        with self.narrate(
            "If the target chooses a at the first position, verification stops "
            "immediately, even though the drafter assigned a substantial thirty-five "
            "percent mass. DDTree keeps alternatives when they are worth the node budget."
        ) as tracker:
            self.paced(
                tracker,
                Transform(path[1], rejected),
                FadeIn(bad_choice),
                fraction=0.5,
            )

        self.clear_stage()

    def tree_objective(self):
        title = self.heading("Which prefixes deserve the budget?")
        alpha = self.label(
            "acceptance length = number of consecutive tree nodes matched",
            27,
            CYAN,
        ).shift(UP * 1.8)
        indicators = VGroup(
            self.label("P(match depth >= 1)", 23),
            self.label("+ P(match depth >= 2)", 23),
            self.label("+ P(match depth >= 3)", 23),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.28)
        indicators.shift(LEFT * 2.6 + DOWN * 0.15)
        equality = self.label("=", 35).next_to(indicators, RIGHT, buff=0.5)
        masses = VGroup(
            self.label("sum of depth-1 node masses", 22, BLUE),
            self.label("+ sum of depth-2 node masses", 22, BLUE),
            self.label("+ sum of depth-3 node masses", 22, BLUE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        masses.next_to(equality, RIGHT, buff=0.5)
        result = self.label(
            "Expected matched depth under Q = sum of q(prefix) over tree nodes",
            25,
            GREEN,
        ).to_edge(DOWN, buff=0.55)

        with self.narrate(
            "The objective is expected matched depth. A useful identity avoids heavy "
            "math: for any nonnegative integer length, its expectation is the chance of "
            "reaching depth one, plus the chance of reaching depth two, and so on."
        ) as tracker:
            self.paced(tracker, Write(title), FadeIn(alpha), fraction=0.4)
            self.paced(
                tracker,
                LaggedStart(*(FadeIn(line) for line in indicators), lag_ratio=0.6),
                fraction=0.5,
            )

        with self.narrate(
            "In a prefix-closed tree, reaching a particular depth means matching one node "
            "at that depth. Under the factorized draft distribution, each node contributes "
            "exactly its prefix probability. So the objective is simply the sum of all "
            "node masses."
        ) as tracker:
            self.paced(tracker, FadeIn(equality), fraction=0.12)
            self.paced(
                tracker,
                LaggedStart(*(FadeIn(line) for line in masses), lag_ratio=0.6),
                fraction=0.48,
            )
            self.paced(tracker, FadeIn(result), fraction=0.3)

        closure = self.label(
            "Child mass <= parent mass, so the top-B prefixes are automatically prefix-closed",
            22,
            YELLOW,
        ).next_to(result, UP, buff=0.34)
        with self.narrate(
            "Every child multiplies its parent mass by a probability below one. Therefore "
            "a child can never outrank its parent. Taking the B highest-mass prefixes "
            "automatically includes every required ancestor."
        ) as tracker:
            self.paced(tracker, FadeIn(closure), fraction=0.52)

        self.clear_stage()

    def best_first_example(self):
        title = self.heading("3. Best-first tree construction: B = 7", color=YELLOW)

        def toy(value: float, digits: int) -> str:
            """Format a toy probability the way this scene displays it: no
            leading zero, matching earlier panels such as "the .55"."""
            text = f"{value:.{digits}f}"
            return text[1:] if text.startswith("0.") else text

        marginal_depth = {"model": 2, "system": 2, "code": 2, "works": 3, "runs": 3, "fails": 3}
        marginal_value = {**Q2, **Q3}

        table_panel = self.panel(6.6, 1.3).to_corner(UP + LEFT, buff=0.3).shift(DOWN * 0.8)
        computation_panel = (
            self.panel(6.6, 1.3).to_corner(UP + RIGHT, buff=0.3).shift(DOWN * 0.8)
        )
        computation_heading = self.label(
            "prefix mass = parent mass x marginal", 15, MUTED
        ).next_to(computation_panel.get_top(), DOWN, buff=0.08)

        depth_rows = {}
        depth_order = {}
        for depth, marginals in ((1, Q1), (2, Q2), (3, Q3)):
            ranked = sorted(marginals.items(), key=lambda item: -item[1])
            depth_order[depth] = [token for token, _ in ranked]
            cells = [self.label(f"depth {depth}", 17, BLUE)]
            cells += [self.label(f"{token} {toy(value, 2)}", 17) for token, value in ranked]
            depth_rows[depth] = VGroup(*cells).arrange(RIGHT, buff=0.3)
        table = VGroup(depth_rows[1], depth_rows[2], depth_rows[3]).arrange(
            DOWN, aligned_edge=LEFT, buff=0.14
        )
        table.move_to(table_panel)

        def marginal_cell(token: str):
            depth = marginal_depth[token]
            return depth_rows[depth][1 + depth_order[depth].index(token)]

        radius = BEST_FIRST_RADIUS
        positions = BEST_FIRST_POSITIONS
        tree = StableTree()
        root = tree.add_node("root", TreeNode("b", radius=radius), positions["root"])
        root.highlight(YELLOW)
        root_note = self.label("root: bonus token", 15, MUTED).next_to(
            root, UP, buff=0.08
        )

        rank_box = self.panel(6.6, 0.6).to_edge(DOWN, buff=0.1)
        rank_text = self.label("pop highest prefix mass from the heap", 19, MUTED)
        rank_text.move_to(rank_box)

        with self.narrate(
            "Now build the tree without enumerating the vocabulary cubed. A max-heap "
            "starts with the best depth-one token. Each pop inserts that prefix into the "
            "tree, then offers at most two new candidates: its next sibling, and its best "
            "child."
        ) as tracker:
            self.paced(
                tracker,
                Write(title),
                FadeIn(table_panel),
                FadeIn(computation_panel),
                FadeIn(table),
                FadeIn(computation_heading),
                fraction=0.42,
            )
            self.paced(tracker, FadeIn(root), FadeIn(root_note), fraction=0.24)
            self.paced(tracker, FadeIn(rank_box), FadeIn(rank_text), fraction=0.2)

        prefixes = best_first_prefixes([Q1, Q2, Q3], budget=7)
        node_mass = {"root": 1.0}
        pop_labels = []
        score_style = BEST_FIRST_SCORE_STYLE
        narration = {
            1: (
                "First comes the with mass point five five. The heap now contains its "
                "next sibling, a, and its best child, the-model."
            ),
            2: (
                "Next is a at point three five. Notice that it beats the-model at "
                "point three three, so breadth can be more valuable than depth."
            ),
            3: (
                "Then the-model: point five five times point six equals point three "
                "three. Products are the path scores."
            ),
            4: (
                "Then a-model at point two one. This branch is retained because its "
                "joint mass still exceeds the remaining alternatives."
            ),
            5: (
                "The best depth-three prefix is the-model-works: point three three "
                "times point five two, or about point one seven two."
            ),
            6: (
                "The-system follows at point one six five. It is slightly below the "
                "deeper works prefix, so the heap ordering decides their insertion."
            ),
            7: (
                "Finally a-model-works enters at point one zero nine. Seven pops fill "
                "the budget. The selected prefixes are globally the seven largest "
                "under Q."
            ),
        }

        for index, prefix in enumerate(prefixes, start=1):
            node_mass[prefix.key] = prefix.mass
            score_text = toy(prefix.mass, 3)
            pop = self.label(f"{index}. {prefix.token}: {score_text}", 19, YELLOW)
            pop_labels.append(pop)
            pop.move_to(rank_box if index == 1 else pop_labels[index - 2])

            if prefix.depth == 1:
                # A marginal selection: its mass is a table value directly, with
                # no product to visualize. Its heap-order meaning (the current
                # frontier's largest mass) still comes through via rank_text.
                node = TreeNode(
                    prefix.token,
                    score=score_text,
                    radius=radius,
                    score_direction=score_style["direction"],
                    score_buff=score_style["buff"],
                    score_font_size=score_style["font_size"],
                )
                tree.add_node(prefix.key, node, positions[prefix.key])
                edge = tree.connect(prefix.parent, prefix.key)
                with self.narrate(narration[index]) as tracker:
                    self.paced(
                        tracker,
                        FadeIn(edge),
                        FadeIn(node, shift=UP * 0.08),
                        Transform(rank_text, pop),
                        fraction=0.52,
                    )
                continue

            # A genuine product: parent mass x this depth's marginal. Show the
            # operands, the equation, and the result before connecting it to
            # the newly inserted node, instead of only revealing a final
            # number.
            parent_node = tree.nodes[prefix.parent]
            parent_mass = node_mass[prefix.parent]
            marginal = marginal_value[prefix.token]
            computation = Computation(
                Operand(prefix.parent, parent_mass, tex=toy(parent_mass, 3)),
                Operand(prefix.token, marginal, tex=toy(marginal, 2)),
                exact_result=prefix.mass,
                leading_zero=False,
                interpretation=f"prefix mass for {prefix.key.replace('-', ' -> ')}",
            )
            equation = computation.build_equation(font_size=26, result_color=YELLOW)
            equation.move_to(computation_panel).shift(UP * 0.22)
            interpretation = computation.build_interpretation(font_size=13, color=MUTED)
            interpretation.next_to(equation, DOWN, buff=0.16)

            parent_highlight = SurroundingRectangle(
                parent_node.score_label, color=ORANGE, buff=0.05
            )
            marginal_highlight = SurroundingRectangle(
                marginal_cell(prefix.token), color=BLUE, buff=0.05
            )

            node = TreeNode(prefix.token, radius=radius)
            tree.add_node(prefix.key, node, positions[prefix.key])
            edge = tree.connect(prefix.parent, prefix.key)

            with self.narrate(narration[index]) as tracker:
                self.paced(tracker, FadeIn(edge), FadeIn(node, shift=UP * 0.08), fraction=0.16)
                self.paced(
                    tracker,
                    FadeIn(parent_highlight),
                    FadeIn(marginal_highlight),
                    fraction=0.16,
                )
                self.paced(tracker, Write(equation), fraction=0.2)
                # Animate an explicit traveling copy of the equation's result
                # into the node's score position, then adopt that copy as the
                # node's official score label. This keeps the score from
                # popping into view before the animation (it starts looking
                # exactly like the still-visible equation result) and keeps
                # it from leaving a duplicate behind (the label is only ever
                # added to the node once, after the animation settles).
                target_score = node.prepare_score(score_text, **score_style)
                traveling_result = computation.result_term(equation).copy()
                self.add(traveling_result)
                self.paced(
                    tracker,
                    Transform(traveling_result, target_score),
                    FadeOut(parent_highlight),
                    FadeOut(marginal_highlight),
                    Transform(rank_text, pop),
                    fraction=0.28,
                )
                self.remove(traveling_result)
                node.attach_score(traveling_result)
                self.paced(tracker, FadeIn(interpretation), fraction=0.1)
                self.paced(tracker, FadeOut(equation), FadeOut(interpretation), fraction=0.1)

        note = self.label(
            "Optimal for DFlash's factorized Q - not claimed optimal for target p",
            21,
            ORANGE,
        ).to_edge(DOWN, buff=0.16)
        with self.narrate(
            "This optimality is precise but limited. The tree is optimal for the "
            "factorized DFlash surrogate Q. It is not claimed to be optimal for the "
            "target's unavailable path-conditioned distribution p."
        ) as tracker:
            self.paced(tracker, FadeOut(rank_box), Transform(rank_text, note), fraction=0.5)

        self.clear_stage()

    def tree_verification(self):
        title = self.heading("4. Flatten the tree, preserve ancestry", color=GREEN)
        flat_tokens = VGroup(
            *[
                TokenBox(token, state=TokenState.SPECULATIVE, width=1.05)
                for token in ["b", "the", "a", "model", "model", "works", "system", "works"]
            ]
        ).arrange(RIGHT, buff=0.08)
        flat_tokens.scale(0.73).shift(UP * 1.8)
        indices = VGroup(
            *[self.label(str(i), 16, MUTED).next_to(tok, UP, buff=0.08) for i, tok in enumerate(flat_tokens)]
        )
        depths = self.label("position ids: start + [0, 1, 1, 2, 2, 3, 2, 3]", 22, CYAN)
        depths.next_to(flat_tokens, DOWN, buff=0.24)

        mask_values = [
            [1, 0, 0, 0, 0, 0, 0, 0],
            [1, 1, 0, 0, 0, 0, 0, 0],
            [1, 0, 1, 0, 0, 0, 0, 0],
            [1, 1, 0, 1, 0, 0, 0, 0],
            [1, 0, 1, 0, 1, 0, 0, 0],
            [1, 1, 0, 1, 0, 1, 0, 0],
            [1, 1, 0, 0, 0, 0, 1, 0],
            [1, 0, 1, 0, 1, 0, 0, 1],
        ]
        mask = LabeledMatrix(
            mask_values,
            row_labels=[str(i) for i in range(8)],
            column_labels=[str(i) for i in range(8)],
            cell_width=0.42,
            cell_height=0.34,
        )
        mask.scale(0.9).shift(DOWN * 0.85 + LEFT * 2.0)
        mask_label = self.label("tree visibility mask", 22, GREEN).next_to(
            mask, LEFT, buff=0.45
        )
        legend = VGroup(
            self.label("1 = may attend", 19, GREEN),
            self.label("0 = hidden branch", 19, MUTED),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.18)
        legend.next_to(mask, RIGHT, buff=0.5)

        with self.narrate(
            "The target model receives a flat token array, not a pointer-based tree. "
            "Duplicate token labels remain distinct nodes because they have different "
            "parents. Position IDs come from tree depth, not flat array index."
        ) as tracker:
            self.paced(
                tracker,
                Write(title),
                FadeIn(flat_tokens),
                FadeIn(indices),
                FadeIn(depths),
                fraction=0.62,
            )

        with self.narrate(
            "Tree attention restores the semantics. Every node may attend to the committed "
            "context, its ancestors, and itself, but never to a sibling or another branch. "
            "For example, node five, works, sees root b, the, model, and itself."
        ) as tracker:
            self.paced(
                tracker,
                FadeIn(VGroup(*mask.row_label_mobjects, *mask.column_label_mobjects)),
                FadeIn(mask_label),
                FadeIn(legend),
                fraction=0.22,
            )
            row_reveal = LaggedStart(
                *(FadeIn(mask.row_group(row)) for row in range(len(mask.cells))),
                lag_ratio=0.7,
            )
            self.paced(tracker, row_reveal, fraction=0.54)
            highlight = mask.highlight_row(5, color=GREEN, opacity=0.35)
            self.paced(tracker, FadeIn(highlight), fraction=0.24)

        one_pass = self.label(
            "All node logits computed in one target forward pass",
            25,
            GREEN,
        ).to_edge(DOWN, buff=0.25)
        with self.narrate(
            "That mask lets one causal target-model forward pass compute the correct next "
            "token distribution after every candidate prefix in parallel."
        ) as tracker:
            self.paced(tracker, FadeIn(one_pass), fraction=0.5)

        self.clear_stage()

    def lossless_commit(self):
        title = self.heading("5. Follow only the target model's choices", color=GREEN)
        tree = StableTree()
        positions = {
            "root": (0.0, 2.0, 0),
            "the": (-3.1, 0.8, 0),
            "a": (0.0, 0.8, 0),
            "the-model": (-3.6, -0.5, 0),
            "the-system": (-1.7, -0.5, 0),
            "a-model": (0.0, -0.5, 0),
            "the-model-works": (-3.6, -1.8, 0),
            "a-model-works": (0.0, -1.8, 0),
        }
        specs = [
            ("root", "b", "root", None),
            ("the", "the", ".550", "root"),
            ("a", "a", ".350", "root"),
            ("the-model", "model", ".330", "the"),
            ("the-system", "system", ".165", "the"),
            ("a-model", "model", ".210", "a"),
            ("the-model-works", "works", ".172", "the-model"),
            ("a-model-works", "works", ".109", "a-model"),
        ]
        for key, token, score, parent in specs:
            tree.add_node(key, TreeNode(token, radius=0.46), positions[key])
            if parent:
                tree.connect(parent, key)
        tree.nodes["root"].highlight(YELLOW)

        def decision_near(node_key: str, text: str, color=ORANGE):
            """Anchor the decision label next to whichever node is currently
            being resolved, instead of a fixed absolute position, so the
            annotation always sits beside the relevant node."""
            return self.label(text, 25, color).next_to(
                tree.nodes[node_key].circle, RIGHT, buff=0.35
            )

        decision = decision_near("root", "target next token: ?")

        committed = TokenSequence("b", buff=0.12)
        committed.token_boxes[0].set_state(TokenState.ACCEPTED)
        committed.scale(0.78).to_edge(DOWN, buff=0.25).shift(RIGHT * 2.6)
        commit_label = self.label(
            "committed so far", 19, MUTED
        ).next_to(committed, UP, buff=0.16)

        with self.narrate(
            "Verification starts at the bonus-token root. The target applies its own "
            "decoding rule there. In this example it chooses a, so the walk takes the a "
            "edge. The drafter's probabilities do not make this decision."
        ) as tracker:
            self.paced(
                tracker,
                Write(title),
                FadeIn(tree),
                FadeIn(decision),
                FadeIn(committed),
                FadeIn(commit_label),
                fraction=0.42,
            )
            decision_a = decision_near("a", "target next token: a")
            self.paced(
                tracker,
                Transform(decision, decision_a),
                tree.nodes["a"].circle.animate.set_stroke(GREEN, width=5),
                tree.edges[("root", "a")].animate.set_color(GREEN).set_stroke(width=5),
                fraction=0.24,
            )
            new_box = committed.append_token("a", state=TokenState.ACCEPTED)
            self.paced(tracker, FadeIn(new_box, shift=UP * 0.1), fraction=0.18)

        with self.narrate(
            "At node a, the already-computed target logits choose model. That child "
            "exists, so the second speculative token is accepted too."
        ) as tracker:
            decision_model = decision_near("a-model", "target next token: model")
            self.paced(
                tracker,
                Transform(decision, decision_model),
                tree.nodes["a-model"].circle.animate.set_stroke(GREEN, width=5),
                tree.edges[("a", "a-model")].animate.set_color(GREEN).set_stroke(width=5),
                fraction=0.36,
            )
            new_box = committed.append_token("model", state=TokenState.ACCEPTED)
            self.paced(tracker, FadeIn(new_box, shift=UP * 0.1), fraction=0.16)

        with self.narrate(
            "At a-model, the target chooses runs. That child was not in our seven-node "
            "tree, so the walk stops. The matched nodes a and model are committed. Runs "
            "is also committed as the next bonus token, ready for the following round."
        ) as tracker:
            decision_runs = decision_near(
                "a-model", "target next token: runs (no child)", color=RED
            )
            self.paced(tracker, Transform(decision, decision_runs), fraction=0.3)
            new_box = committed.append_token("runs", state=TokenState.ACTIVE)
            new_label = self.label(
                "commit matched path + carry unmatched target token", 19, MUTED
            ).next_to(committed, UP, buff=0.16)
            self.paced(
                tracker,
                FadeIn(new_box, shift=UP * 0.12),
                Transform(commit_label, new_label),
                fraction=0.48,
            )

        self.clear_stage()

    def system_tradeoff(self):
        title = self.heading("What DDTree changes - and what it does not")
        formula = self.label(
            "time per output token = (draft + tree build + verify) / committed tokens",
            27,
            CYAN,
        ).shift(UP * 1.65)
        levers = VGroup(
            self.panel(3.5, 2.05),
            self.panel(3.5, 2.05),
            self.panel(3.5, 2.05),
        ).arrange(RIGHT, buff=0.35)
        levers.shift(DOWN * 0.15)
        left_text = VGroup(
            self.label("DFlash", 27, BLUE),
            self.label("one parallel draft pass", 18),
            self.label("cheap per-position marginals", 16, MUTED),
        ).arrange(DOWN, buff=0.25).move_to(levers[0])
        mid_text = VGroup(
            self.label("DDTree", 27, YELLOW),
            self.label("spend B nodes on alternatives", 18),
            self.label("maximize sum of prefix mass", 16, MUTED),
        ).arrange(DOWN, buff=0.25).move_to(levers[1])
        right_text = VGroup(
            self.label("Target", 27, GREEN),
            self.label("one tree-attention pass", 18),
            self.label("alone decides committed tokens", 16, MUTED),
        ).arrange(DOWN, buff=0.25).move_to(levers[2])

        with self.narrate(
            "The system trade-off is now clear. DFlash avoids token-by-token draft "
            "latency by predicting the block in parallel. DDTree uses extra verifier "
            "width, controlled by B, to raise the expected number of committed tokens."
        ) as tracker:
            self.paced(tracker, Write(title), FadeIn(formula), fraction=0.42)
            self.paced(
                tracker,
                FadeIn(levers),
                FadeIn(left_text),
                FadeIn(mid_text),
                fraction=0.45,
            )

        with self.narrate(
            "A larger tree is not free: tree construction, attention, and cache compaction "
            "grow with the budget. The useful operating point is where extra accepted "
            "tokens still outweigh that wider verification pass."
        ) as tracker:
            self.paced(tracker, FadeIn(right_text), fraction=0.35)
            budget = self.label(
                "B trades verifier width for expected acceptance length",
                23,
                ORANGE,
            ).to_edge(DOWN, buff=0.38)
            self.paced(tracker, FadeIn(budget), fraction=0.35)

        guarantee = self.label(
            "Speed comes from proposals. Correctness still comes from the target.",
            27,
            GREEN,
        ).scale_to_fit_width(11.5)
        source_note = self.label(
            "DFlash (Chen et al., 2026) | DDTree (Ringel and Romano, 2026)",
            18,
            MUTED,
        ).next_to(guarantee, DOWN, buff=0.3)
        with self.narrate(
            "Most importantly, DDTree changes where the target looks, not what the target "
            "chooses. Every committed token is selected by the target model's own decoding "
            "rule. The tree only increases the chance that several of those choices were "
            "already waiting in the same verification pass."
        ) as tracker:
            self.paced(
                tracker,
                FadeOut(formula),
                FadeOut(levers),
                FadeOut(left_text),
                FadeOut(mid_text),
                FadeOut(right_text),
                FadeOut(budget),
                FadeOut(title),
                FadeIn(guarantee),
                FadeIn(source_note),
                fraction=0.62,
            )
            self.wait(min(1.2, tracker.duration * 0.12))
