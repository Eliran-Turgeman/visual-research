"""DDTree: derive the objective, predict a choice, then separate coverage from truth."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import textwrap

from manim import (
    Scene, Text, VGroup, Line, Arrow, Rectangle, RoundedRectangle, SurroundingRectangle,
    FadeIn, FadeOut, Create, TransformFromCopy, Circumscribe,
    AnimationGroup, LaggedStart, config, LEFT, RIGHT, UP,
)


ROOT = Path(__file__).resolve().parent
BG, INK, DRAFT, TARGET, MUTED, PALE = (
    "#F7F5EF", "#192C35", "#107E84", "#B4471F", "#536B75", "#DEECE9",
)
config.background_color = BG
WORDS = (("dog", "cat"), ("stayed", "slept"), ("outside", "inside"))
TARGET_CHOICES = {
    "b": "cat", "A": "stayed", "AA": "outside",
    "B": "stayed", "AAA": "today", "BA": "inside",
}


def phrase(prefix):
    if prefix == "b":
        return "My"
    return " ".join(WORDS[i]["AB".index(choice)] for i, choice in enumerate(prefix))


def token_word(prefix):
    return phrase(prefix).split()[-1]


def txt(value, size=28, color=INK):
    return Text(value, font="DejaVu Sans", font_size=size, color=color)


def at(mobject, x, y):
    return mobject.move_to([x, y, 0])


def node(label, x, y, color=DRAFT, font_size=25):
    word = txt(label, font_size, color)
    return at(VGroup(
        RoundedRectangle(width=max(.75, word.width + .28), height=.6,
                         corner_radius=.08, color=color, stroke_width=2.5,
                         fill_color=BG, fill_opacity=1),
        word,
    ), x, y)


def edge(source, destination, color=MUTED):
    return Line(source.get_right(), destination.get_left(), buff=.04,
                color=color, stroke_width=2.5)


def tree_at(x=-5.85, y=.55, step=1.75, paths=("A", "AA", "B", "AAA", "BA")):
    locations = {
        "b": (x, y), "A": (x + step, y + .7), "AA": (x + 2 * step, y + .7),
        "AAA": (x + 3 * step, y + .7), "B": (x + step, y - 1.0),
        "BA": (x + 2 * step, y - 1.0),
    }
    nodes = {p: node(token_word(p), *locations[p],
                     TARGET if p == "b" else DRAFT) for p in ("b", *paths)}
    edges = {p: edge(nodes[p[:-1] or "b"], nodes[p]) for p in paths}
    labels = {p: at(txt("after My" if len(p) == 1 else f"{phrase(p[0])} path", 17, MUTED),
                    locations[p][0], locations[p][1] - .57)
              for p in paths}
    return nodes, edges, labels


def tree_group(nodes, edges, labels):
    return VGroup(*edges.values(), *nodes.values(), *labels.values())


def subtitle_time(seconds):
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


class DDTreeExplainer(Scene):
    def present(self, ident, animations=(), *, motion=1.2):
        entry = self.beats[ident]
        anchor = at(txt(entry["anchor"], 23, MUTED), 0, -3.45)
        replacements = [FadeOut(self.anchor)]
        section_changed = entry["section"] != self.section
        if section_changed:
            replacements.append(FadeOut(self.heading))
        self.play(*replacements, run_time=.2)
        if section_changed:
            self.heading = txt(entry["section"], 34).to_corner(UP + LEFT, buff=.5)
            self.section = entry["section"]
            self.add(self.heading)
        self.anchor = anchor
        self.add(anchor)
        start = float(self.time)
        speech = self.speech.get(ident)
        speech_start = start + .15
        if speech:
            self.add_sound(str(ROOT / "audio" / speech["wav"]), time_offset=.15)
        exits = [a for a in animations if isinstance(a, FadeOut)]
        entering = [a for a in animations if not isinstance(a, FadeOut)]
        if exits and entering:
            animations = [AnimationGroup(
                AnimationGroup(*exits), AnimationGroup(*entering), lag_ratio=1,
            )]
        if animations:
            self.play(*animations, run_time=motion)
        motion_end = float(self.time)
        duration = max(entry["seconds"], speech["duration"] + .5 if speech else 0)
        self.wait(max(.1, start + duration - float(self.time)))
        think_start = float(self.time)
        if entry.get("think"):
            self.wait(entry["think"])
        self.timeline.append({
            "id": ident, "start": start, "motion_end": motion_end,
            "think_start": think_start, "end": float(self.time),
            "audio_start": speech_start if speech else None,
            "audio_end": speech_start + speech["duration"] if speech else None,
            "narration": entry["narration"],
        })
        self.check_bounds(ident)

    def check_bounds(self, ident):
        for mob in self.mobjects:
            if not mob.width or not mob.height:
                continue
            bounds = [float(mob.get_left()[0]), float(mob.get_bottom()[1]),
                      float(mob.get_right()[0]), float(mob.get_top()[1])]
            if bounds[0] < -7.02 or bounds[2] > 7.02 or bounds[1] < -3.9 or bounds[3] > 3.9:
                self.geometry.append({"beat": ident, "bounds": bounds})

    def clear_except(self, *keep):
        retained = {id(self.heading), id(self.anchor), id(self.rule), *(id(m) for m in keep)}
        return [FadeOut(m) for m in list(self.mobjects) if id(m) not in retained]

    def introduce_context(self):
        def panel(label, x, y, color, width=2.9):
            caption = txt(label, 24, color)
            if caption.width > width - .25 or caption.height > .75:
                raise ValueError(f"Context label needs more space: {label!r}")
            return at(VGroup(
                RoundedRectangle(width=width, height=1, corner_radius=.1,
                                 color=color, stroke_width=2.5,
                                 fill_color=BG, fill_opacity=1),
                caption,
            ), x, y)

        def connect(source, destination):
            return Arrow(source.get_right(), destination.get_left(), buff=.12,
                         color=MUTED, stroke_width=2.5)

        prefix = panel("known prefix\nprompt + text", -4.8, .8, MUTED)
        target = panel("trained\ntarget model", 0, .8, TARGET)
        next_token = panel("predict\nnext token", 4.8, .8, TARGET)
        into_target, out_of_target = connect(prefix, target), connect(target, next_token)
        use_not_train = at(txt("Use learned weights; do not train them here.", 28), 0, 2.25)
        self.present("inference", [
            FadeIn(prefix), FadeIn(target), FadeIn(next_token),
            Create(into_target), Create(out_of_target), FadeIn(use_not_train),
        ])
        feedback = VGroup(
            Line(next_token.get_bottom(), [4.8, -.65, 0], color=TARGET, stroke_width=2.5),
            Arrow([4.8, -.65, 0], [-4.8, -.65, 0], buff=0, color=TARGET, stroke_width=2.5),
            Line([-4.8, -.65, 0], prefix.get_bottom(), color=TARGET, stroke_width=2.5),
        )
        repeat = at(txt("add the chosen token to the prefix, then repeat", 28), 0, -1.4)
        serial = at(txt("one next-token decision per target pass", 28, TARGET), 0, -2.35)
        self.present("autoregressive_loop", [Create(feedback), FadeIn(repeat), FadeIn(serial)])

        drafter = panel("cheap drafter\npropose a block", -4.8, .8, DRAFT)
        accepted = panel("accepted\ncontinuation", 4.8, .8, TARGET)
        proposed_label = at(txt("several\nproposals", 21, DRAFT), -2.4, 1.9)
        checked_label = at(txt("check them\ntogether", 21, TARGET), 2.4, 1.9)
        speculative = at(txt("Spend cheap draft work to reuse one expensive target pass.", 27), 0, -1.5)
        self.present("speculation", [
            FadeOut(prefix), FadeOut(next_token), FadeOut(use_not_train),
            FadeOut(feedback), FadeOut(repeat), FadeOut(serial),
            FadeIn(drafter), FadeIn(accepted), FadeIn(proposed_label),
            FadeIn(checked_label), FadeIn(speculative),
            Circumscribe(target, color=TARGET),
        ])

        draft_steps = [panel("draft next\ntoken", x, .6, DRAFT) for x in (-4, 0, 4)]
        draft_links = VGroup(*(connect(a, b) for a, b in zip(draft_steps, draft_steps[1:])))
        focus = at(txt("Zoom in: an autoregressive drafter", 29, DRAFT), 0, 2.25)
        dependent = at(txt("The next proposal needs the previous proposal.", 28), 0, -1.3)
        self.present("draft_bottleneck", self.clear_except() + [
            FadeIn(VGroup(*draft_steps)), Create(draft_links), FadeIn(focus), FadeIn(dependent),
        ])

        columns = (-2, .6, 3.2)
        masks = VGroup(*(node("MASK", x, 1.1, MUTED) for x in columns))
        hidden = at(txt("unknown future token positions", 28), .6, 2.35)
        recover = at(txt("learn to recover masked text", 30, DRAFT), .6, -.2)
        together = at(txt("update several positions together", 28), .6, -1.05)
        refine = at(txt("Many diffusion systems repeat the refinement.", 25, MUTED), .6, -2.2)
        self.present("masked_diffusion", self.clear_except() + [
            FadeIn(masks), FadeIn(hidden), FadeIn(recover), FadeIn(together), FadeIn(refine),
        ])

        features = panel("target context\nfeatures", -5, -.25, TARGET)
        processed = at(txt("from the already-\nprocessed prefix", 20, MUTED), -5, -1.6)
        block_drafter = panel("DFlash block drafter\none forward pass", .6, -.25, DRAFT, 5.8)
        feature_link = connect(features, block_drafter)
        probabilities = VGroup(*(panel("token\nprobabilities", x, -2.05, DRAFT, 2.35) for x in columns))
        input_links = VGroup(*(Arrow(m.get_bottom(), [x, .25, 0], buff=.08,
                                     color=MUTED, stroke_width=2)
                              for x, m in zip(columns, masks)))
        output_links = VGroup(*(Arrow([x, -.75, 0], p.get_top(), buff=.08,
                                      color=DRAFT, stroke_width=2)
                               for x, p in zip(columns, probabilities)))
        self.present("dflash", [
            FadeOut(recover), FadeOut(together), FadeOut(refine),
            FadeIn(features), FadeIn(processed), FadeIn(block_drafter), Create(feature_link),
            Create(input_links), Create(output_links), FadeIn(probabilities),
        ])

        parallel_draft = panel("DFlash\nparallel draft", -4.8, .8, DRAFT, 3.1)
        tree_builder = panel("DDTree\nchoose paths", 0, .8, DRAFT, 3.1)
        verifier = panel("target model\nverify paths", 4.8, .8, TARGET, 3.1)
        roles = VGroup(
            at(txt("token alternatives", 24, MUTED), -4.8, -.25),
            at(txt("fixed node budget", 24, MUTED), 0, -.25),
            at(txt("same target model", 24, MUTED), 4.8, -.25),
        )
        budget_question = at(txt("Which continuations deserve a verifier slot?", 31), 0, -1.65)
        self.present("ddtree_context", self.clear_except() + [
            FadeIn(parallel_draft), FadeIn(tree_builder), FadeIn(verifier), FadeIn(roles),
            Create(connect(parallel_draft, tree_builder)), Create(connect(tree_builder, verifier)),
            FadeIn(budget_question),
        ])

    def construct(self):
        self.beats = {
            b["id"]: b for b in json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
        }
        self.speech = {}
        narration = os.environ.get("DDTREE_NARRATED", "0")
        if narration not in ("0", "1"):
            raise ValueError("DDTREE_NARRATED must be 0 (silent) or 1 (narrated).")
        if narration == "1":
            self.speech = json.loads(
                (ROOT / "audio" / "manifest.json").read_text(encoding="utf-8")
            )["beats"]
            if set(self.speech) != set(self.beats):
                raise ValueError("All speech clips are required; run scripts/narrate.py for this storyboard.")
            for ident, speech in self.speech.items():
                if speech["request"]["input"] != self.beats[ident]["narration"]:
                    raise ValueError(f"Speech for {ident} is stale; prepare the current storyboard.")
        self.timeline, self.geometry = [], []
        self.section = None
        self.heading = txt("DDTree", 34).to_corner(UP + LEFT, buff=.5)
        self.anchor = at(txt("A fixed budget. More than one possible future.", 23, MUTED), 0, -3.45)
        self.rule = Line([-6.55, -3.1, 0], [6.55, -3.1, 0], color="#B9C7C8", stroke_width=1)
        self.add(self.heading, self.anchor, self.rule)
        self.introduce_context()

        # Establish the need with the same three-slot budget on both alternatives.
        nodes, edges, labels = tree_at(x=-4.8, y=.0, step=2.4, paths=("A", "AA", "AAA"))
        chain = tree_group(nodes, edges, labels)
        proposal = at(txt('Writing a message: "My dog stayed outside"', 30, DRAFT), 0, 2.1)
        root_note = at(txt("already\nselected", 21, MUTED), -4.8, -.8)
        self.present("problem", self.clear_except() + [FadeIn(chain), FadeIn(proposal), FadeIn(root_note)])
        target_choice = at(txt('target: "My cat ..."', 32, TARGET), -.6, -1.8)
        self.present("miss", [FadeIn(target_choice), Circumscribe(nodes["b"], color=TARGET)])
        branch = node("cat", -2.4, -1.0)
        branch_edge = edge(nodes["b"], branch)
        branch_label = at(txt("another possible message", 21, MUTED), -1.4, -1.75)
        budget_note = at(txt("3 draft slots\nroot is extra", 27), 4.9, -1.35)
        self.present("budget", [
            FadeOut(nodes["AAA"]), FadeOut(edges["AAA"]), FadeOut(labels["AAA"]),
            FadeOut(proposal), FadeOut(target_choice),
            FadeIn(branch), Create(branch_edge), FadeIn(branch_label), FadeIn(budget_note),
        ])

        distributions = VGroup()
        for i, (a, b, x) in enumerate(((.6, .4, -4), (.7, .3, 0), (.8, .2, 4)), 1):
            distributions.add(VGroup(
                at(txt(f"position {i}", 25, MUTED), x, 2.05),
                VGroup(at(txt(WORDS[i-1][0], 30, DRAFT), x - .45, 1.25),
                       at(txt(f"{a:.2f}", 30, DRAFT), x + .95, 1.25)),
                VGroup(at(txt(WORDS[i-1][1], 30), x - .45, .5),
                       at(txt(f"{b:.2f}", 30), x + .95, .5)),
            ))
        self.present("marginals", self.clear_except() + [FadeIn(distributions)])
        operands = VGroup(*(txt(part, 32, DRAFT) for part in ("q(dog stayed) =", "0.60", "x", "0.70")))
        operands.arrange(RIGHT, buff=.15).move_to([-1, -.65, 0])
        meaning = at(txt('first "dog", then "stayed"', 27), 0, -1.5)
        self.present("prefix_operands", [
            FadeIn(operands[0]), FadeIn(operands[2]), FadeIn(meaning),
            AnimationGroup(Circumscribe(distributions[0][1][1], color=DRAFT), FadeIn(operands[1])),
            AnimationGroup(Circumscribe(distributions[1][1][1], color=DRAFT), FadeIn(operands[3])),
        ])
        result = txt("= 0.420", 32, DRAFT)
        at(result, operands.get_right()[0] + .15 + result.width / 2, -.65)
        self.present("prefix_product", [FadeIn(result)])
        extended = at(txt("q(dog stayed outside) = 0.420 x 0.80 = 0.336", 30, DRAFT), 0, -1.8)
        self.present("ancestor", [
            FadeOut(meaning), FadeIn(extended), Circumscribe(distributions[2][1], color=DRAFT),
        ])

        nodes, edges, labels = tree_at()
        tree = tree_group(nodes, edges, labels)
        candidate = at(txt("candidate tree", 26, MUTED), -3.5, 2.4)
        count_label = at(txt('"dog stayed outside"', 27), 3.3, 1.4)
        units = [at(txt("1", 36, DRAFT), x, .45) for x in (1.6, 2.8, 4.0)]
        additions = VGroup(*(at(txt("+", 30), x, .45) for x in (2.2, 3.4)))
        count_total = at(txt("= 3 matches", 30), 3.3, -.5)
        count = VGroup(count_label, *units, additions, count_total)
        self.present("count_matches", self.clear_except() + [
            FadeIn(tree), FadeIn(candidate), FadeIn(count_label),
            LaggedStart(
                *[AnimationGroup(Circumscribe(nodes[p], color=DRAFT), FadeIn(unit))
                  for p, unit in zip(("A", "AA", "AAA"), units)],
                FadeIn(additions), FadeIn(count_total), lag_ratio=.5,
            ),
        ], motion=3.5)
        bars = []
        for depth, probability, terms, y in (
            (1, 1.0, ".600 + .400", 1.35),
            (2, .7, ".420 + .280", .10),
            (3, .336, ".336", -1.15),
        ):
            x = .9
            background = Rectangle(width=4.8, height=.26, color=MUTED, stroke_width=1)
            at(background, x + 2.4, y - .38)
            fill = Rectangle(width=4.8 * probability, height=.26,
                             fill_color=DRAFT, fill_opacity=1, stroke_width=0)
            at(fill, x + 2.4 * probability, y - .38)
            value = f"{terms} = {probability:.3f}" if depth < 3 else "0.336"
            label = at(txt(f"at least {depth}: {value}", 23), 3.3, y)
            bars.append(VGroup(background, fill, label))
        self.present("depth_one", [
            FadeOut(count), FadeIn(bars[0]),
            Circumscribe(nodes["A"], color=DRAFT), Circumscribe(nodes["B"], color=DRAFT),
        ])
        branch_product = at(txt("q(cat stayed) = 0.40 x 0.70 = 0.280", 30, DRAFT), 0, -2.45)
        self.present("branch_product", [
            FadeIn(branch_product), Circumscribe(nodes["B"], color=DRAFT),
            Circumscribe(nodes["BA"], color=DRAFT),
        ])
        self.present("depth_two", [
            FadeIn(bars[1]), Circumscribe(nodes["AA"], color=DRAFT),
            Circumscribe(nodes["BA"], color=DRAFT),
        ])
        self.present("depth_three", [FadeIn(bars[2]), Circumscribe(nodes["AAA"], color=DRAFT)])
        expected = at(txt("1.000 + 0.700 + 0.336 = 2.036", 32, DRAFT), .5, -2.45)
        self.present("expectation", [FadeOut(branch_product), FadeIn(expected)])

        ranking = VGroup()
        ranked = (("A", ".600"), ("B", ".400"), ("AA", ".420"),
                  ("BA", ".280"), ("AAA", ".336"), ("BAA", ".224"))
        for i, (path, mass) in enumerate(ranked):
            y = 1.9 - i * .62
            name = txt(phrase(path), 25, DRAFT).move_to([.75, y, 0], aligned_edge=LEFT)
            ranking.add(VGroup(name, at(txt(mass, 26, DRAFT), 6.0, y)))
        nodes, edges, labels = tree_at()
        budget = at(txt("5 slots", 28), -3.3, 2.4)
        self.present("selection_rule", self.clear_except() + [
            FadeIn(nodes["b"]), FadeIn(ranking), FadeIn(budget),
        ])
        self.present("first_two", [
            *[FadeIn(nodes[p]) for p in ("A", "AA")],
            *[Create(edges[p]) for p in ("A", "AA")],
            *[FadeIn(labels[p]) for p in ("A", "AA")],
        ])
        question = at(txt('prepare "cat"\nor finish "dog stayed outside"?', 26), -2.9, -1.7)
        self.present("choose_question", [
            FadeIn(question), Circumscribe(ranking[1], color=TARGET),
            Circumscribe(ranking[4], color=TARGET),
        ])
        self.present("choose_answer", [
            FadeOut(question), FadeIn(nodes["B"]), Create(edges["B"]), FadeIn(labels["B"]),
            Circumscribe(ranking[1], color=TARGET),
        ])
        self.present("finish_selection", [
            *[FadeIn(nodes[p]) for p in ("AAA", "BA")],
            *[Create(edges[p]) for p in ("AAA", "BA")],
            *[FadeIn(labels[p]) for p in ("AAA", "BA")],
            ranking[5].animate.set_opacity(.35),
        ])

        left_nodes, left_edges, left_labels = tree_at(-6, .0, 1.8, ("A", "AA", "B"))
        right_nodes, right_edges, right_labels = tree_at(.45, .0, 1.85, ("A", "AA", "AAA"))
        left = tree_group(left_nodes, left_edges, left_labels)
        right_start = VGroup(right_nodes["b"], right_nodes["A"], right_nodes["AA"],
                             right_edges["A"], right_edges["AA"],
                             right_labels["A"], right_labels["AA"])
        left_q = at(txt("dog .60 / stayed .70 / outside .80", 23), -3.4, 2)
        right_q = at(txt("dog .90 / stayed .90 / outside .80", 23), 3.4, 2)
        same_budget = at(txt("3 slots each; root extra", 27, MUTED), 0, -2.25)
        unknown = at(txt('"cat" or "dog stayed outside"?', 25), 3.4, -1.1)
        self.present("contrast_question", self.clear_except() + [
            FadeIn(left), FadeIn(right_start), FadeIn(left_q), FadeIn(right_q),
            FadeIn(same_budget), FadeIn(unknown),
        ])
        comparison = at(txt("dog stayed outside: .648\ncat: .100", 25, DRAFT), 3.4, -1.3)
        self.present("contrast_answer", [
            FadeOut(unknown), FadeIn(right_nodes["AAA"]), Create(right_edges["AAA"]),
            FadeIn(right_labels["AAA"]), FadeIn(comparison),
        ])

        nodes, edges, labels = tree_at()
        tree = tree_group(nodes, edges, labels)
        roles = at(txt('target after "dog stayed": outside\n\ntarget after "cat stayed": inside', 24, TARGET), 3.4, .9)
        self.present("target_roles", self.clear_except() + [FadeIn(tree), FadeIn(roles)])
        flat_ids = ["b", "A", "AA", "B", "AAA", "BA"]
        flat_x = [-5 + i * 1.8 for i in range(6)]
        flat_tokens = VGroup(*(
            node(token_word(p), x, 2.05, TARGET if p == "b" else DRAFT, 22)
            for p, x in zip(flat_ids, flat_x)
        ))
        flat_labels = VGroup(*(at(txt("root" if p == "b" else f"{phrase(p[0])} path", 18, MUTED),
                                     x, 2.65) for p, x in zip(flat_ids, flat_x)))
        positions = VGroup(*(at(txt(str(d), 23, TARGET), x, 1.5)
                             for x, d in zip(flat_x, (0, 1, 2, 1, 3, 2))))
        depth_label = at(txt("depth", 21, TARGET), 6.0, 1.5)
        # Move the tree down before adding the array; the entity correspondence remains explicit.
        self.play(tree.animate.shift([0, -.8, 0]), run_time=.8)
        self.present("flatten", [
            FadeOut(roles), FadeIn(flat_labels), FadeIn(positions), FadeIn(depth_label),
            *[TransformFromCopy(nodes[p], token) for p, token in zip(flat_ids, flat_tokens)],
        ])

        matrix, cells, matrix_labels = VGroup(), {}, VGroup()
        mx, my, step_x, step_y = 1.3, .35, 1.0, .52
        prefixes = ["", "A", "AA", "B", "AAA", "BA"]
        mask_names = ["My", "dog", "stayed\n(dog)", "cat", "outside\n(dog)", "stayed\n(cat)"]
        for r in range(6):
            for c in range(6):
                cell = at(Rectangle(width=.9, height=.46, stroke_color=MUTED,
                                    stroke_width=1, fill_color=BG, fill_opacity=1),
                          mx + c * step_x, my - r * step_y)
                cells[r, c] = cell
                matrix.add(cell)
            matrix_labels.add(txt(mask_names[r], 16).move_to(
                [mx - .55, my - r * step_y, 0], aligned_edge=RIGHT,
            ))
            matrix_labels.add(at(txt(mask_names[r], 16), mx + r * step_x, my + .67))
        context_note = at(txt("+ prior cached context", 20, MUTED), 3.8, -2.8)
        row_box = at(RoundedRectangle(width=5.95, height=.5, corner_radius=.06,
                                      color=TARGET, stroke_width=2), 3.8, my - 5 * step_y)
        self.present("mask_question", [
            FadeIn(matrix), FadeIn(matrix_labels), FadeIn(row_box), FadeIn(context_note),
        ])
        self.present("mask_answer", [
            *[cells[5, c].animate.set_fill(DRAFT, 1) for c in (0, 3, 5)],
            *[Circumscribe(nodes[p], color=TARGET) for p in ("b", "B", "BA")],
        ])
        self.present("parallel_outputs", [
            FadeOut(row_box),
            *[cells[r, c].animate.set_fill(DRAFT if p.startswith(a) else BG, 1)
              for r, p in enumerate(prefixes) for c, a in enumerate(prefixes)],
        ])

        target_choices = {}
        for p in flat_ids:
            target_choices[p] = at(
                txt(f"next: {TARGET_CHOICES[p]}", 19, TARGET), nodes[p].get_x(),
                .65 if p == "b" else (1.02 if p in ("A", "AA", "AAA") else -2.35),
            )
        self.present("prepared_choices", [FadeIn(VGroup(*target_choices.values()))])
        draft_preference = at(txt("draft: dog .600 > cat .400", 27, DRAFT), 3.3, 2.0)
        pointer = SurroundingRectangle(nodes["b"], buff=.1, color=TARGET, stroke_width=3)
        out_label = at(txt("message so far", 24, MUTED), 3.4, .95)
        output = VGroup(*(node(word, 0, 0, TARGET) for word in ("My", "cat", "stayed", "inside")))
        output.arrange(RIGHT, buff=.18).move_to([3.4, .1, 0])
        self.present("walk_question", [
            FadeOut(matrix), FadeOut(matrix_labels), FadeOut(context_note),
            *[FadeOut(m) for m in flat_tokens], FadeOut(flat_labels),
            FadeOut(positions), FadeOut(depth_label),
            Circumscribe(target_choices["b"], color=TARGET),
            FadeIn(draft_preference), FadeIn(pointer),
            FadeIn(out_label), FadeIn(output[0]),
        ])
        self.present("walk_first", [
            pointer.animate.become(SurroundingRectangle(nodes["B"], buff=.1, color=TARGET, stroke_width=3)),
            edges["B"].animate.set_color(TARGET),
            FadeIn(output[1]),
        ])
        matches = at(txt("2 speculative matches", 26, TARGET), 3.4, -1.0)
        self.present("walk_second", [
            Circumscribe(target_choices["B"], color=TARGET),
            pointer.animate.become(SurroundingRectangle(nodes["BA"], buff=.1, color=TARGET, stroke_width=3)),
            edges["BA"].animate.set_color(TARGET), FadeIn(output[2]), FadeIn(matches),
        ])
        final_choice = at(txt('no "inside" child', 19, TARGET), -.25, -2.35)
        bonus_note = at(txt("next root\nnot processed", 22, TARGET), output[3].get_x(), -1.9)
        self.present("bonus", [
            Circumscribe(target_choices["BA"], color=TARGET),
            FadeIn(final_choice), FadeIn(output[3]), FadeIn(bonus_note),
        ])
        kept = at(txt('processed: "My cat stayed"', 28, TARGET), -.4, 2.05)
        self.present("cache", [
            FadeOut(draft_preference), FadeIn(kept),
            *[nodes[p].animate.set_opacity(.2) for p in ("A", "AA", "AAA")],
            *[edges[p].animate.set_opacity(.2) for p in ("A", "AA", "AAA")],
            *[labels[p].animate.set_opacity(.2) for p in ("A", "AA", "AAA")],
            *[target_choices[p].animate.set_opacity(.2) for p in ("A", "AA", "AAA")],
        ])

        left_nodes, left_edges, left_labels = tree_at(-6, .0, 1.8, ("A", "AA", "B"))
        right_nodes, right_edges, right_labels = tree_at(.45, .0, 1.85, ("A", "AA", "AAA"))
        left, right = (tree_group(*parts) for parts in (
            (left_nodes, left_edges, left_labels), (right_nodes, right_edges, right_labels),
        ))
        fixed = at(txt('target writes "My cat ..." in both cases', 31, TARGET), 0, 2.1)
        transfer = at(txt("Does the emitted token change?", 30), 0, -2.2)
        self.present("transfer_question", self.clear_except() + [
            FadeIn(left), FadeIn(right), FadeIn(fixed), FadeIn(transfer),
        ])
        left_result = at(txt('write "cat"\nprepared child: 1 match', 25, TARGET), -3.7, -2.05)
        right_result = at(txt('write "cat"\nmissing child: next bonus', 25, TARGET), 3.35, -2.05)
        self.present("transfer_answer", [
            FadeOut(transfer), FadeIn(left_result), FadeIn(right_result),
            Circumscribe(left_nodes["B"], color=TARGET),
        ])
        conclusion = at(txt("DFlash proposes in parallel.\nDDTree allocates the budget.\nThe target chooses tokens.", 32), 0, 1.5)
        costs = VGroup()
        for x, name in ((-4.5, "draft"), (-1.5, "build"), (1.5, "verify"), (4.5, "compact")):
            costs.add(VGroup(
                at(Rectangle(width=2.4, height=.8, color=DRAFT), x, -.35),
                at(txt(name, 27), x, -.35),
            ))
        limit = at(txt("Optimal under Q and a node budget\nNot a target-acceptance or latency guarantee", 27), 0, -1.65)
        credit = at(txt("Ringel & Romano, DDTree | arXiv:2604.12989v1", 20, MUTED), 0, -2.65)
        self.present("boundary", self.clear_except() + [
            FadeIn(conclusion), FadeIn(costs), FadeIn(limit), FadeIn(credit),
        ])
        self.write_records()

    def write_records(self):
        outdir = ROOT / os.environ.get("DDTREE_RECORD_DIR", "records")
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "timeline.json").write_text(json.dumps({
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "narrated": bool(self.speech), "duration": float(self.time),
            "fps": config.frame_rate, "beats": self.timeline,
        }, indent=2), encoding="utf-8")
        (outdir / "geometry.json").write_text(json.dumps({
            "scope": "Top-level frame bounds after each beat; not a collision or learning check",
            "out_of_frame": self.geometry,
        }, indent=2), encoding="utf-8")
        captions = []
        for i, beat in enumerate(self.timeline, 1):
            start = beat["audio_start"] if self.speech else beat["start"]
            end = beat["audio_end"] if self.speech else beat["think_start"]
            captions.append(
                f"{i}\n{subtitle_time(start)} --> {subtitle_time(end)}\n"
                f"{textwrap.fill(beat['narration'], width=76)}\n"
            )
        name = "narration.srt" if self.speech else "draft-script.srt"
        (outdir / name).write_text("\n".join(captions), encoding="utf-8")
