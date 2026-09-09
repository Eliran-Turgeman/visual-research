"""Full DDTree episode: probability becomes a tree, then target-chosen output."""

from contextlib import contextmanager
import json
import os
from pathlib import Path

from manim import (
    DOWN, LEFT, PI, RIGHT, UP,
    Arrow, Circle, Create, CubicBezier, DashedLine,
    FadeIn, FadeOut, Indicate, LaggedStart, Line, MathTex,
    Succession, SurroundingRectangle, Text, TransformFromCopy, VGroup, Write,
)

from examples.ddtree_full.storyboard import (
    ACCEPTED, ANCHOR, BEATS, BONUS, BUDGET, BY_KEY, DEPTHS, INDEX,
    MARGINALS, MASK, ORDER, PARENTS, PREFIXES, SELECTIONS, TARGET_CHOICES,
    VANILLA, WORDS, ancestry,
)
from manim_lib import (
    ACCENT, DANGER, NEUTRAL, PRIMARY, SUCCESS,
    TEXT_PRIMARY, TEXT_SECONDARY,
    Computation, LabeledMatrix, NarratedScene, Operand, ProbabilityDistribution,
    map_ancestry_to_mask,
)


TREE_POSITIONS = {
    "root": (-1.8, 2.25, 0),
    "the": (-4.6, 1.05, 0),
    "a": (-0.7, 1.05, 0),
    "the-model": (-5.5, -0.40, 0),
    "the-system": (-3.1, -0.40, 0),
    "a-model": (0.0, -0.40, 0),
    "the-model-works": (-5.5, -1.85, 0),
    "a-model-works": (0.0, -1.85, 0),
}
FLAT_POSITIONS = {key: (-5.25 + INDEX[key] * 1.5, 2.2, 0) for key in ORDER}
FLATTEN_MOVE_ORDER = tuple(sorted(
    ORDER, key=lambda key: (DEPTHS[key], -TREE_POSITIONS[key][0]),
))


def text(value, size=22, color=TEXT_SECONDARY, *, serif=False):
    return Text(
        value, font="Georgia" if serif else "Segoe UI",
        font_size=size, color=color,
    )


def anchor_annotation(word):
    label = text("next round's anchor", 21, ACCENT.light).move_to((3.1, -0.90, 0))
    arrow = Arrow(
        word.get_bottom() + DOWN * 0.08, label.get_top() + UP * 0.08,
        buff=0, color=ACCENT.dim, stroke_width=2,
    )
    return label, arrow


class PrefixNode(VGroup):
    """A branch point with an external word: no tiny words inside circles."""

    def __init__(self, key):
        self.key = key
        self.token = WORDS[key]
        self.dot = Circle(
            radius=0.11, stroke_width=2, stroke_color=PRIMARY.light,
            fill_color=PRIMARY.base, fill_opacity=0.2,
        )
        self.word = text(self.token, 26, TEXT_PRIMARY, serif=True)
        value = BY_KEY[key].mass if key != "root" else 1.0
        self.mass = text(f"{value:.3f}", 20)
        super().__init__(self.dot, self.word)
        self.to_tree()
        self.set_z_index(3)

    def to_tree(self):
        self.dot.move_to(TREE_POSITIONS[self.key])
        self.word.next_to(self.dot, RIGHT, buff=0.15)
        self.mass.next_to(self.word, DOWN, buff=0.09).align_to(self.word, LEFT)
        self.mass.set_opacity(1)
        return self

    def attach_mass(self):
        self.add(self.mass)
        return self

    def to_flat(self):
        self.dot.move_to(FLAT_POSITIONS[self.key])
        self.word.next_to(self.dot, DOWN, buff=0.18)
        self.mass.next_to(self.word, DOWN, buff=0.1).set_opacity(0)
        return self

    def match(self):
        self.dot.set_fill(SUCCESS.light, opacity=1).set_stroke(SUCCESS.light)
        self.word.set_color(SUCCESS.light)
        return self

    def output_at(self, x):
        self.dot.move_to((x, 0.55, 0))
        self.word.next_to(self.dot, DOWN, buff=0.18)
        self.mass.set_opacity(0)
        if self.key == "root":
            self.dot.set_fill(ACCENT.base, opacity=1).set_stroke(ACCENT.light)
            self.word.set_color(TEXT_SECONDARY)
            return self
        return self.match()


class FrontierView(VGroup):
    """A fixed-position view of the top three actual lazy-heap candidates."""

    def __init__(self, items, selected):
        super().__init__()
        self.items = items
        self.rows = {}
        self.add(
            text(f"Selected {selected} / {BUDGET}", 24, ACCENT.light).move_to((4.4, 2.65, 0)),
            text("Max-heap frontier", 20).move_to((4.4, 2.08, 0)),
        )
        for index, item in enumerate(items[:3]):
            y = 1.45 - index * 0.67
            path = text(" / ".join(item.path), 18, TEXT_PRIMARY)
            path.move_to((2.65, y, 0), aligned_edge=LEFT)
            mass = text(f"{item.mass:.3f}", 20, ACCENT.light if index == 0 else TEXT_SECONDARY)
            mass.move_to((6.25, y, 0), aligned_edge=RIGHT)
            self.rows[item.key] = VGroup(path, mass)
            self.add(self.rows[item.key])
        if items:
            self.add(Line((2.65, 1.18, 0), (6.25, 1.18, 0), color=ACCENT.dim, stroke_width=1))
        if len(items) > 3:
            self.add(text(f"+ {len(items) - 3} more", 18).move_to((4.4, -0.70, 0)))


class DDTreePicture:
    """Build final geometry first; the scene controls when each object exists."""

    def __init__(self):
        self.nodes = {key: PrefixNode(key) for key in ORDER}
        self.nodes["root"].dot.set_fill(ACCENT.base, opacity=1).set_stroke(ACCENT.light)
        self.edges = {}
        for prefix in PREFIXES:
            start = self.nodes[prefix.parent].dot.get_bottom()
            end = self.nodes[prefix.key].dot.get_top()
            self.edges[prefix.key] = CubicBezier(
                start, start + DOWN * 0.60, end + UP * 0.48, end,
                color=NEUTRAL.base, stroke_width=1.6,
            ).set_z_index(-1)
        self.tree = VGroup(*self.edges.values(), *self.nodes.values())
        self.distributions = []
        self.distribution_titles = []
        for index, marginal in enumerate(MARGINALS):
            distribution = ProbabilityDistribution(
                {word: (word, value) for word, value in marginal.items()},
                max_bar_width=1.25, bar_height=0.22, font_size=22, entry_buff=0.25,
            )
            # A common baseline inside each distribution makes bar length honest.
            left = max(entry.token_label.get_right()[0] for entry in distribution.entries.values()) + 0.25
            for entry in distribution.entries.values():
                entry.track.shift(RIGHT * (left - entry.track.get_left()[0]))
                entry.bar.move_to(entry.track).align_to(entry.track, LEFT)
                entry.value_label.next_to(entry.track, RIGHT, buff=0.12)
            distribution.move_to((-4.15 + index * 4.15, 0.70, 0))
            title = text(f"Position {index + 1}", 22, PRIMARY.light)
            title.next_to(distribution, UP, buff=0.40)
            self.distributions.append(distribution)
            self.distribution_titles.append(title)
        self.dist_group = VGroup(*self.distributions, *self.distribution_titles)
        self.matrix = LabeledMatrix(
            [list(row) for row in MASK],
            row_labels=[str(i) for i in range(len(ORDER))],
            column_labels=[str(i) for i in range(len(ORDER))],
            cell_width=0.48, cell_height=0.37,
        ).move_to((2.50, -1.05, 0))
        self.slot_ids = VGroup(*[
            text(str(INDEX[key]), 20).move_to((FLAT_POSITIONS[key][0], 2.70, 0))
            for key in ORDER
        ])
        self.position_ids = VGroup(*[
            text(str(DEPTHS[key]), 22, ACCENT.light).move_to((FLAT_POSITIONS[key][0], 1.12, 0))
            for key in ORDER
        ])

    def final_frontier(self, selected):
        return FrontierView(SELECTIONS[selected - 1].after, selected)

    def relayout(self, *, flat):
        # Clear shallower nodes first; only motion order changes, not array order.
        keys = FLATTEN_MOVE_ORDER if flat else reversed(FLATTEN_MOVE_ORDER)
        return Succession(*[
            self.nodes[key].animate(path_arc=PI / 3).to_flat()
            if flat else self.nodes[key].animate(path_arc=-PI / 3).to_tree()
            for key in keys
        ])


class DDTreeFullExplainer(NarratedScene):
    review_timeline_path = Path("media/review/ddtree_full/timeline.json")
    external_voiceover_subdir = "ddtree_full_external"

    def setup(self):
        provider = os.getenv("MANIM_TTS_PROVIDER", "openrouter").lower()
        if provider not in ("openrouter", "none"):
            raise ValueError("This episode uses MAI narration; only openrouter or explicit none is supported")
        if provider == "openrouter" and not os.getenv("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY is required; use render.ps1 or explicit silent draft mode")
        super().setup()
        self.chapter = None
        self.chapter_name = None
        manifest = Path("media/review/ddtree_full/narration.json")
        self.draft_durations = {}
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.draft_durations = {track["text"]: track["duration"] for track in data["tracks"]}

    @contextmanager
    def beat(self, index):
        beat = BEATS[index]
        with self.narrate(beat.narration) as tracker:
            start = self.time
            if not self._voiceover_enabled and beat.narration in self.draft_durations:
                tracker.duration = self.draft_durations[beat.narration]
            self.beat_start, self.beat_duration = start, tracker.duration
            if beat.chapter != self.chapter_name:
                heading = text(beat.chapter, 22, PRIMARY.light)
                heading.move_to((-6.10, 3.40, 0), aligned_edge=LEFT)
                if self.chapter is None:
                    self.add(heading)
                else:
                    self.play(FadeOut(self.chapter), FadeIn(heading), run_time=0.3)
                self.chapter, self.chapter_name = heading, beat.chapter
            yield tracker
            remaining = tracker.duration - (self.time - start)
            if remaining > 0:
                self.wait(remaining)

    def hold_until(self, fraction):
        """Place the next causal action at its phrase within this short block."""
        remaining = self.beat_start + self.beat_duration * fraction - self.time
        if remaining > 0:
            self.wait(remaining)

    def construct(self):
        self.picture = DDTreePicture()
        self.opening()
        self.draft_distribution()
        self.build_tree()
        self.explain_objective()
        self.flatten_and_mask()
        self.target_walk()
        self._finalize()

    def opening(self):
        self.chain = VGroup(*[
            text(word, 42, TEXT_PRIMARY, serif=True) for word in VANILLA
        ]).arrange(RIGHT, buff=1.05).move_to((0.0, 0.65, 0))
        self.chain_links = VGroup(*[
            Arrow(a.get_right(), b.get_left(), buff=0.2, stroke_width=2, color=PRIMARY.dim)
            for a, b in zip(self.chain, self.chain[1:])
        ])
        self.chain_label = text("One draft path", 22, PRIMARY.light).next_to(self.chain, UP, buff=0.60)
        self.greedy_note = text("Toy probabilities / greedy target example", 18).move_to((0, -3.30, 0))
        with self.beat(0):
            self.play(
                LaggedStart(*(FadeIn(word) for word in self.chain), lag_ratio=0.2),
                Create(self.chain_links), FadeIn(self.chain_label),
                FadeIn(self.greedy_note), run_time=1.7,
            )
        self.target_first = text("a", 48, ACCENT.light, serif=True).move_to((-2.8, -1.10, 0))
        self.target_label = text("Target chooses", 22).next_to(self.target_first, LEFT, buff=0.35)
        self.mismatch = VGroup(
            Line((-3.0, -0.15, 0), (-2.65, 0.18, 0), color=DANGER.base, stroke_width=3),
            Line((-2.65, -0.15, 0), (-3.0, 0.18, 0), color=DANGER.base, stroke_width=3),
        )
        with self.beat(1):
            for word in self.chain:
                self.play(word.animate.set_color(PRIMARY.light), run_time=0.4)
            self.hold_until(0.35)
            self.play(FadeIn(self.target_label), FadeIn(self.target_first), run_time=0.6)
            self.hold_until(0.57)
            self.play(Create(self.mismatch), self.chain.animate.set_color(DANGER.light), run_time=0.6)
            self.failure = text("No matching first token", 28, DANGER.light).move_to((0, -2.30, 0))
            self.hold_until(0.78)
            self.play(FadeIn(self.failure), run_time=0.5)

    def draft_distribution(self):
        p = self.picture
        self.context = VGroup(
            text("committed context   ...", 28, TEXT_PRIMARY, serif=True),
            text(ANCHOR, 28, TEXT_PRIMARY, serif=True),
        ).arrange(RIGHT, buff=0.25)
        self.context.move_to((0, 2.45, 0))
        self.condition = text("target features + anchor", 22, ACCENT.light).move_to((0, 1.50, 0))
        self.slots = VGroup(*[
            Circle(radius=0.16, stroke_color=PRIMARY.light, fill_opacity=0).move_to((x, 0.15, 0))
            for x in (-3.0, 0.0, 3.0)
        ])
        self.condition_links = VGroup(*[
            Line(self.condition.get_bottom(), slot.get_top(), color=PRIMARY.dim, stroke_width=1.5)
            for slot in self.slots
        ])
        with self.beat(2):
            self.play(
                FadeOut(VGroup(self.chain, self.chain_links, self.chain_label, self.target_label,
                               self.target_first, self.mismatch, self.failure)),
                FadeIn(self.context), FadeIn(self.condition), run_time=0.7,
            )
            self.hold_until(0.45)
            self.play(Create(self.condition_links), run_time=0.8)
            self.hold_until(0.72)
            self.play(FadeIn(self.slots), run_time=0.5)
        with self.beat(3):
            self.play(FadeOut(self.condition_links), FadeOut(self.condition), run_time=0.35)
            self.play(
                *[
                    TransformFromCopy(slot, dist)
                    for slot, dist in zip(self.slots, p.distributions)
                ],
                *(FadeIn(title) for title in p.distribution_titles),
                FadeOut(self.slots), run_time=1.5,
            )
            for distribution in p.distributions:
                entry = next(iter(distribution.entries.values()))
                self.play(entry.bar.animate.set_fill(PRIMARY.light, opacity=0.9), run_time=0.3)
            self.hold_until(0.50)
            self.play(
                p.distributions[1].entries["model"].animate.highlight(ACCENT.base),
                p.distributions[1].entries["system"].animate.highlight(ACCENT.base),
                run_time=0.6,
            )
            self.hold_until(0.78)
            self.play(p.distribution_titles[1].animate.set_color(ACCENT.light), run_time=0.4)
        self.factorization = MathTex(
            r"Q(x_1,x_2,x_3)", "=", r"q_1(x_1)", r"q_2(x_2)", r"q_3(x_3)",
            font_size=36, color=TEXT_PRIMARY,
        ).move_to((0, -1.50, 0))
        self.factor_note = text("fixed shared conditioning", 22).next_to(
            self.factorization, DOWN, buff=0.28
        )
        with self.beat(4):
            self.play(Write(self.factorization[:2]), run_time=0.6)
            self.hold_until(0.30)
            self.play(
                LaggedStart(*[
                    TransformFromCopy(title, self.factorization[i + 2])
                    for i, title in enumerate(p.distribution_titles)
                ], lag_ratio=0.25),
                FadeIn(self.factor_note), run_time=1.8,
            )
            self.hold_until(0.73)
            self.play(self.factorization[2:].animate.set_color(PRIMARY.light), run_time=0.5)
        with self.beat(5):
            entry = p.distributions[0].entries["a"]
            self.play(entry.animate.highlight(ACCENT.base), run_time=0.5)
            self.alternative = text("Keep the alternative.", 34, ACCENT.light, serif=True)
            self.alternative.move_to((0, -2.50, 0))
            self.hold_until(0.65)
            self.play(FadeIn(self.alternative), run_time=0.5)

    def build_tree(self):
        p = self.picture
        root = p.nodes["root"]
        self.queue = FrontierView(SELECTIONS[0].before, 0)
        with self.beat(6):
            context_prefix, context_anchor = self.context
            self.play(FadeOut(context_prefix), run_time=0.25)
            self.context.remove(context_prefix)
            self.play(
                TransformFromCopy(context_anchor, root.word), FadeIn(root.dot),
                FadeOut(VGroup(p.dist_group, self.factorization, self.factor_note, self.alternative,
                               self.context, self.greedy_note)), run_time=1.0,
            )
            self.remove(root.word, root.dot)
            self.add(root)
            self.root_note = text("anchor", 18, ACCENT.light).next_to(root.word, UP, buff=0.12)
            self.play(FadeIn(self.root_note), run_time=0.4)
            self.hold_until(0.45)
            self.play(FadeIn(self.queue), run_time=0.6)
        for index, step in enumerate(SELECTIONS):
            with self.beat(7 + index) as tracker:
                self.select_prefix(index, tracker)

    def select_prefix(self, index, tracker):
        p = self.picture
        step = SELECTIONS[index]
        prefix = step.chosen
        node = p.nodes[prefix.key]
        row = self.queue.rows[prefix.key]
        if index == 1:
            comparison = MathTex("0.350", ">", "0.330", font_size=38, color=TEXT_PRIMARY)
            comparison.move_to((-1.2, -3.05, 0))
            self.play(
                TransformFromCopy(row[1], comparison[0]),
                TransformFromCopy(self.queue.rows["the-model"][1], comparison[2]),
                run_time=0.7,
            )
            self.play(Write(comparison[1]), run_time=0.4)
            self.play(FadeOut(comparison), run_time=0.3)
        if prefix.depth == 1:
            self.hold_until(0.20)
            self.play(Create(p.edges[prefix.key]), FadeIn(node.dot),
                      TransformFromCopy(row[0], node.word), run_time=0.9)
            self.hold_until(0.46)
            self.play(TransformFromCopy(row[1], node.mass), run_time=0.6)
        else:
            parent = BY_KEY[prefix.parent]
            marginal = MARGINALS[prefix.depth - 1][prefix.token]
            computation = Computation(
                Operand("parent prefix", parent.mass),
                Operand("next marginal", marginal),
                interpretation="joint draft probability of this prefix",
            )
            equation = computation.build_equation(font_size=36).move_to((-0.8, -3.05, 0))
            lookup = MathTex(
                rf"q_{{{prefix.depth}}}(\mathrm{{{prefix.token}}})", "=", f"{marginal:.2f}",
                font_size=28, color=TEXT_PRIMARY,
            ).move_to((4.4, -1.65, 0))
            lookup[2].set_color(PRIMARY.light)
            self.play(FadeIn(lookup), run_time=0.4)
            self.hold_until(0.17)
            operand_duration = min(1.5, max(0.7, tracker.duration * 0.15))
            self.play(TransformFromCopy(p.nodes[prefix.parent].mass, equation[0]),
                      run_time=operand_duration)
            self.hold_until(0.35)
            self.play(Write(equation[1]), TransformFromCopy(lookup[2], equation[2]),
                      run_time=operand_duration)
            self.hold_until(0.58)
            self.play(Write(equation[3:]), run_time=0.8)
            self.hold_until(0.72)
            self.play(Create(p.edges[prefix.key]), FadeIn(node.dot),
                      FadeIn(node.word), run_time=0.7)
            self.play(TransformFromCopy(computation.result_term(equation), node.mass),
                      run_time=0.7)
            self.play(FadeOut(equation), FadeOut(lookup), run_time=0.3)
        self.remove(node.dot, node.word, node.mass)
        node.attach_mass()
        self.add(node)
        self.hold_until(0.86)
        next_queue = p.final_frontier(index + 1)
        self.play(FadeOut(self.queue), FadeIn(next_queue), run_time=0.45)
        self.queue = next_queue

    def explain_objective(self):
        p = self.picture
        self.invariant = MathTex(
            r"Q(\mathrm{child})", "=", r"Q(\mathrm{parent})", r"\,q_i(x)",
            r"\leq Q(\mathrm{parent})", font_size=32, color=TEXT_PRIMARY,
        ).move_to((0, -3.05, 0))
        with self.beat(14):
            self.play(FadeOut(self.queue), FadeOut(self.root_note), run_time=0.35)
            self.play(Write(self.invariant[:4]), run_time=1.1)
            self.hold_until(0.38)
            self.play(Write(self.invariant[4]), run_time=0.7)
            self.hold_until(0.69)
            self.play(
                *[edge.animate.set_color(PRIMARY.light) for edge in p.edges.values()],
                run_time=0.6,
            )
        with self.beat(15):
            self.play(FadeOut(self.invariant), run_time=0.3)
            objective = MathTex(
                r"\mathbb{E}_{x\sim Q}[L_T(x)]", "=",
                r"\sum_{u\in T} Q(u)", font_size=32, color=TEXT_PRIMARY,
            ).move_to((4.20, 0.5, 0))
            if objective.width > 3.9:
                objective.scale_to_fit_width(3.9)
            expectation = Computation(
                *[Operand(prefix.key, prefix.mass, tex=f"{prefix.mass:.4f}".rstrip("0"))
                  for prefix in PREFIXES],
                operator="+", exact_result=sum(prefix.mass for prefix in PREFIXES),
                interpretation="expected draft matches under Q",
            )
            equation = expectation.build_equation(font_size=32).move_to((0, -3.00, 0))
            self.play(Write(objective), run_time=0.9)
            self.hold_until(0.30)
            self.play(LaggedStart(*[
                TransformFromCopy(p.nodes[prefix.key].mass, expectation.operand_term(equation, i))
                for i, prefix in enumerate(PREFIXES)
            ], lag_ratio=0.18), run_time=2.0)
            self.play(
                *(Write(equation[i]) for i in range(1, len(equation) - 2, 2)),
                run_time=0.5,
            )
            self.play(Write(equation[-2:]), run_time=0.7)
            note = text("draft-model proxy, not target acceptance", 20, ACCENT.light).move_to((0, -3.55, 0))
            self.hold_until(0.70)
            self.play(FadeIn(note), run_time=0.35)
            self.hold_until(0.92)
            self.play(FadeOut(equation), FadeOut(objective), FadeOut(note), run_time=0.4)
        with self.beat(16):
            count = MathTex("7", "+", "1", "=", "8", font_size=44, color=TEXT_PRIMARY)
            count.move_to((4.25, 0.65, 0))
            self.play(
                LaggedStart(*(node.dot.animate.set_fill(PRIMARY.light, opacity=1)
                              for key, node in p.nodes.items() if key != "root"), lag_ratio=0.15),
                Write(count[0]), run_time=1.0,
            )
            self.hold_until(0.40)
            self.play(TransformFromCopy(p.nodes["root"].dot, count[2]), Write(count[1]), run_time=0.7)
            self.play(Write(count[3:]), run_time=0.6)
            cost = text("target input positions", 21).next_to(count, DOWN, buff=0.25)
            self.play(FadeIn(cost), run_time=0.4)
            self.hold_until(0.90)
            self.play(FadeOut(count), FadeOut(cost), run_time=0.4)

    def flatten_and_mask(self):
        p = self.picture
        with self.beat(17):
            self.play(
                *(FadeOut(edge) for edge in p.edges.values()),
                *[node.mass.animate.set_opacity(0)
                  for key, node in p.nodes.items() if key != "root"],
                run_time=0.5,
            )
            self.play(p.relayout(flat=True), run_time=4.8)
            self.play(FadeIn(p.slot_ids), run_time=0.4)
        with self.beat(18):
            self.position_label = text("relative position (depth)", 20).move_to((0, 0.50, 0))
            self.play(FadeIn(p.position_ids), FadeIn(self.position_label), run_time=0.5)
            for keys in (("the", "a"), ("the-model", "a-model", "the-system")):
                self.play(*[
                    p.position_ids[INDEX[key]].animate.set_color(SUCCESS.light) for key in keys
                ], run_time=0.5)
                self.wait(0.4)
            self.hold_until(0.70)
            self.offset_note = text("actual position = context offset + depth", 22).move_to((0, -0.55, 0))
            self.play(FadeIn(self.offset_note), run_time=0.5)
        with self.beat(19):
            self.play(FadeOut(self.position_label), FadeOut(p.position_ids),
                      FadeOut(self.offset_note), run_time=0.4)
            self.mask_label = text("visibility mask: 1 = can attend", 20).next_to(
                p.matrix, UP, buff=0.15
            )
            grid = VGroup(
                *[cell[0] for row in p.matrix.cells for cell in row],
                *p.matrix.row_label_mobjects, *p.matrix.column_label_mobjects,
            )
            self.play(FadeIn(grid), FadeIn(self.mask_label), run_time=0.8)
            self.path_label = text("Slot 7: works after a / model", 21, TEXT_PRIMARY)
            self.path_label.move_to((-3.9, 0.20, 0))
            self.path_view = VGroup(*[
                text(WORDS[key], 26, PRIMARY.light, serif=True)
                for key in ancestry("a-model-works")
            ]).arrange(DOWN, buff=0.35).move_to((-3.5, -1.35, 0))
            self.play(FadeIn(self.path_label), run_time=0.3)
            selected_row = INDEX["a-model-works"]
            self.hold_until(0.33)
            for view, key in zip(self.path_view, ancestry("a-model-works")):
                column = INDEX[key]
                cell = p.matrix.cells[selected_row][column]
                self.play(
                    Indicate(VGroup(p.nodes[key].dot, p.nodes[key].word),
                             color=PRIMARY.light, scale_factor=1.06),
                    FadeIn(view),
                    cell[0].animate.set_fill(PRIMARY.base, opacity=0.42),
                    Write(cell[1]),
                    run_time=0.65,
                )
        with self.beat(20):
            zeros = VGroup(*[
                p.matrix.cells[INDEX["a-model-works"]][INDEX[key]][1]
                for key in ("the", "the-model", "the-system", "the-model-works")
            ])
            for zero in zeros:
                zero.set_color(DANGER.light)
            self.play(FadeIn(zeros), run_time=0.5)
            self.hold_until(0.50)
            self.cached_note = text("Earlier cached context is also visible.", 20).move_to((0, -3.25, 0))
            self.play(FadeIn(self.cached_note), run_time=0.5)
        with self.beat(21):
            _, overlays = map_ancestry_to_mask(PARENTS, p.matrix, INDEX, opacity=0.18)
            self.mask_overlays = overlays
            self.play(
                LaggedStart(*(FadeIn(overlay) for overlay in overlays), lag_ratio=0.04),
                FadeIn(VGroup(*[cell[1] for row in p.matrix.cells for cell in row])),
                run_time=1.4,
            )
            self.hold_until(0.40)
            batch = SurroundingRectangle(
                VGroup(*[VGroup(node.dot, node.word) for node in p.nodes.values()]),
                buff=0.18, color=ACCENT.light, stroke_width=2,
            )
            self.play(Create(batch), run_time=0.6)
            self.hold_until(0.60)
            self.play(*[node.dot.animate.set_fill(ACCENT.light, opacity=1)
                        for node in p.nodes.values()], run_time=0.65)
            self.hold_until(0.90)
            self.play(FadeOut(batch), run_time=0.3)
        self.mask_objects = VGroup(
            grid, p.matrix, self.mask_overlays, self.mask_label, self.path_view,
            self.path_label, self.cached_note,
        )

    def target_walk(self):
        p = self.picture
        with self.beat(22):
            self.play(FadeOut(self.mask_objects), FadeOut(p.slot_ids), run_time=0.6)
            self.play(p.relayout(flat=False), run_time=3.2)
            self.play(*(FadeIn(edge) for edge in p.edges.values()), run_time=0.5)
            self.decision_label = text("Already computed by the target", 20, ACCENT.light).move_to((4.20, 2.15, 0))
            self.one_pass = text("Target forward passes: 1", 20).move_to((4.2, 2.75, 0))
            self.play(FadeIn(self.decision_label), FadeIn(self.one_pass), run_time=0.4)
            self.hold_until(0.63)
            self.show_choice("root")
            self.hold_until(0.82)
            self.play(
                p.edges["a"].animate.set_color(SUCCESS.light).set_stroke(width=3),
                p.nodes["a"].animate.match(), run_time=0.7,
            )
        with self.beat(23):
            self.show_choice("a")
            self.hold_until(0.35)
            self.play(
                p.edges["a-model"].animate.set_color(SUCCESS.light).set_stroke(width=3),
                p.nodes["a-model"].animate.match(), run_time=0.7,
            )
            self.hold_until(0.73)
            self.play(p.nodes["a-model"].mass.animate.set_opacity(0.4), run_time=0.4)
        with self.beat(24):
            self.show_choice("a-model")
            self.miss_note = text("No proposed child named runs", 22, DANGER.light).move_to((3.8, -0.30, 0))
            self.hold_until(0.40)
            self.play(FadeIn(self.miss_note), run_time=0.5)
            self.bonus_dot = Circle(
                radius=0.11, stroke_color=ACCENT.light, fill_color=ACCENT.base,
                fill_opacity=1,
            ).move_to((2.3, -2.0, 0))
            self.bonus_word = text(BONUS, 26, ACCENT.light, serif=True).next_to(
                self.bonus_dot, RIGHT, buff=0.15
            )
            self.bonus = VGroup(self.bonus_dot, self.bonus_word)
            self.missing_edge = DashedLine(
                p.nodes["a-model"].dot.get_bottom(), self.bonus_dot.get_top(),
                color=ACCENT.base, stroke_width=1.6,
            )
            self.hold_until(0.76)
            self.play(
                Create(self.missing_edge), FadeIn(self.bonus_dot),
                TransformFromCopy(self.choice, self.bonus_word), run_time=0.8,
            )
            self.remove(self.bonus_dot, self.bonus_word)
            self.add(self.bonus)
        with self.beat(25):
            sampling = MathTex(r"y \sim P_{\mathrm{target}}(\cdot\mid\mathrm{prefix})",
                               font_size=29, color=ACCENT.light).move_to((3.8, -1.0, 0))
            self.play(FadeOut(self.choice), FadeOut(self.miss_note), FadeIn(sampling), run_time=0.5)
            self.hold_until(0.43)
            self.play(self.bonus_dot.animate.set_stroke(ACCENT.light, width=4), run_time=0.5)
            self.valid_note = text("Miss = stop reusing work, not reject y", 20).move_to((0, -3.12, 0))
            self.hold_until(0.70)
            self.play(FadeIn(self.valid_note), run_time=0.4)
        with self.beat(26):
            unwanted = [node for key, node in p.nodes.items() if key not in ("root", *ACCEPTED)]
            self.play(
                *(FadeOut(node) for node in unwanted),
                *(FadeOut(edge) for edge in p.edges.values()),
                FadeOut(self.missing_edge), FadeOut(sampling), FadeOut(self.valid_note),
                FadeOut(self.decision_label), FadeOut(self.one_pass),
                run_time=0.7,
            )
            bonus_position = self.bonus_dot.copy().move_to((3.1, 0.55, 0))
            self.play(
                p.nodes["root"].animate.output_at(-3.30),
                p.nodes["a"].animate.output_at(-1.50),
                p.nodes["a-model"].animate.output_at(0.45),
                self.bonus_dot.animate.move_to(bonus_position),
                self.bonus_word.animate.next_to(bonus_position, DOWN, buff=0.18),
                run_time=1.3,
            )
            anchor_label, carry = anchor_annotation(self.bonus_word)
            self.play(FadeIn(anchor_label), Create(carry), run_time=0.5)
            self.hold_until(0.57)
            two = text("2 matched drafts", 30, SUCCESS.light).move_to((-2.25, -2.05, 0))
            zero = text("0 on the single path", 24, TEXT_SECONDARY).move_to((2.50, -2.05, 0))
            pips = VGroup(*[
                Circle(radius=0.10, fill_color=SUCCESS.light, fill_opacity=1, stroke_width=0)
                .move_to((-2.45 + i * 0.4, -1.45, 0))
                for i in range(2)
            ])
            self.play(LaggedStart(*[
                TransformFromCopy(p.nodes[key].dot, pip) for key, pip in zip(ACCEPTED, pips)
            ], lag_ratio=0.3), run_time=0.8)
            self.play(FadeIn(two), FadeIn(zero), run_time=0.5)
        self.wait(1.0)

    def show_choice(self, key):
        choice = text(TARGET_CHOICES[key], 42, ACCENT.light, serif=True).move_to((4.2, 1.25, 0))
        animations = [FadeIn(choice)]
        if hasattr(self, "choice"):
            animations.append(FadeOut(self.choice))
        self.play(*animations, run_time=0.5)
        self.choice = choice
