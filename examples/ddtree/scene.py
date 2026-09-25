"""DDTree, independently designed with native Manim 0.19.2."""
from pathlib import Path
import json
import os
from datetime import datetime, timezone

import numpy as np
from manim import (
    Scene, Text, VGroup, Circle, Line, Arrow, Rectangle, RoundedRectangle,
    FadeIn, FadeOut, Create, Transform, TransformFromCopy, Indicate,
    AnimationGroup, config, LEFT, RIGHT, UP, DOWN, ORIGIN,
)

ROOT = Path(__file__).resolve().parent
BG, INK, DRAFT, TARGET, MUTED, PALE = "#F7F5EF", "#192C35", "#107E84", "#CA5A27", "#667C85", "#DEECE9"
config.background_color = BG


def txt(s, size=30, color=INK):
    return Text(s, font="DejaVu Sans", font_size=size, color=color)


def at(m, x, y):
    return m.move_to([x, y, 0])


def node(label, x, y, color=DRAFT, radius=.34):
    return VGroup(Circle(radius, color=color, stroke_width=3, fill_color=BG, fill_opacity=1),
                  txt(label, 27, color)).move_to([x, y, 0])


def edge(a, b, color=MUTED):
    return Line(a.get_center(), b.get_center(), buff=.36, color=color, stroke_width=2.5)


def distribution(i, a, b, x, y=2.05):
    head = at(txt(f"position {i}", 23, MUTED), x, y + .55)
    atext = at(txt(f"A  {a:.2f}", 29, DRAFT), x, y)
    btext = at(txt(f"B  {b:.2f}", 29), x, y - .52)
    abar = Rectangle(width=1.4 * a, height=.08, fill_color=DRAFT, fill_opacity=1, stroke_width=0)
    bbar = Rectangle(width=1.4 * b, height=.08, fill_color=MUTED, fill_opacity=1, stroke_width=0)
    abar.next_to(atext, DOWN, buff=.06)
    bbar.next_to(btext, DOWN, buff=.06)
    return VGroup(head, atext, btext, abar, bbar)


class DDTreeExplainer(Scene):
    def run_beat(self, ident, heading, actions, note):
        entry = self.beats[ident]
        speech = self.speech.get(ident)
        start = float(self.time)
        duration = speech["duration"] + .7 if speech else max(6.5, len(entry["narration"].split()) / 2.95 + 1.0)
        if speech:
            self.add_sound(str(ROOT / "audio" / speech["wav"]), time_offset=.18)
        self.play(Transform(self.heading, txt(heading, 37).move_to(self.heading, aligned_edge=LEFT)),
                  Transform(self.note, at(txt(note, 24, MUTED), 0, -3.48)), run_time=.4)
        slot = (duration - .4) / len(actions)
        record = {"id": ident, "start": start, "planned_duration": duration,
                  "audio_start": start + .18 if speech else None,
                  "audio_end": start + .18 + speech["duration"] if speech else None,
                  "actions": [], "narration": entry["narration"]}
        for index, action in enumerate(actions):
            t = float(self.time)
            animations = action()
            runtime = min(1.6, slot * .54)
            exits = [a for a in animations if isinstance(a, FadeOut)]
            entering = [a for a in animations if not isinstance(a, FadeOut)]
            if exits and entering:
                animations = [AnimationGroup(AnimationGroup(*exits), AnimationGroup(*entering), lag_ratio=1)]
            self.play(*animations, run_time=runtime)
            record["actions"].append({"index": index, "start": t, "motion_end": float(self.time)})
            self.bounds(ident, index)
            self.wait(max(.05, slot - runtime))
        record["end"] = float(self.time)
        self.timeline.append(record)

    def bounds(self, beat, action):
        for mob in self.mobjects:
            if mob.width == 0 or mob.height == 0:
                continue
            box = [float(mob.get_left()[0]), float(mob.get_bottom()[1]),
                   float(mob.get_right()[0]), float(mob.get_top()[1])]
            if box[0] < -7.02 or box[2] > 7.02 or box[1] < -3.9 or box[3] > 3.9:
                self.geometry.append({"beat": beat, "action": action, "time": float(self.time),
                                      "type": type(mob).__name__, "bounds": box})

    def clear_except(self, *kept):
        keep = {id(self.heading), id(self.note), id(self.rule), *(id(m) for m in kept)}
        return [FadeOut(m) for m in list(self.mobjects) if id(m) not in keep]

    def make_tree(self):
        coords = {"b": (-5.65, -.1), "A": (-3.8, .8), "AA": (-1.95, .8),
                  "B": (-3.8, -1.2), "AAA": (-.1, .8), "BA": (-1.95, -1.2)}
        nodes = {p: node("b" if p == "b" else p[-1], *xy, TARGET if p == "b" else DRAFT)
                 for p, xy in coords.items()}
        parents = {"A": "b", "AA": "A", "B": "b", "AAA": "AA", "BA": "B"}
        edges = {p: edge(nodes[par], nodes[p]) for p, par in parents.items()}
        labels = {p: at(txt(p, 21, MUTED), *[coords[p][0], coords[p][1] - .65])
                  for p in parents}
        return nodes, edges, labels

    def construct(self):
        self.beats = {b["id"]: b for b in json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))}
        self.speech = {}
        narration = os.environ.get("DDTREE_NARRATED", "0")
        if narration not in ("0", "1"):
            raise ValueError("DDTREE_NARRATED must be 0 (silent) or 1 (narrated).")
        if narration == "1":
            self.speech = json.loads((ROOT / "audio" / "manifest.json").read_text(encoding="utf-8"))["beats"]
            if set(self.speech) != set(self.beats):
                raise ValueError("All speech clips are required; run scripts/narrate.py for this storyboard.")
            for ident, speech in self.speech.items():
                if speech["request"]["input"] != self.beats[ident]["narration"]:
                    raise ValueError(f"Speech for {ident} is stale; prepare the current storyboard.")
        self.timeline, self.geometry = [], []
        self.heading = txt("DDTree", 37).to_corner(UP + LEFT, buff=.55)
        self.note = at(txt("A fixed verification budget. More than one possible future.", 24, MUTED), 0, -3.48)
        self.rule = Line([-6.55, -3.12, 0], [6.55, -3.12, 0], color="#C6D1CF", stroke_width=1)
        self.add(self.heading, self.note, self.rule)

        root = node("b", -4.9, .2, TARGET)
        chain = [node("A", x, .2) for x in (-2.4, .1, 2.6)]
        arrows = VGroup(*(edge(a, b) for a, b in zip([root] + chain, chain)))
        alt = node("B", -2.4, -1.6)
        altedge = edge(root, alt)
        context = at(txt("context", 28, MUTED), -5.05, 1.35)
        budget_prompt = at(txt("Which paths earn a verifier slot?", 34), .1, 2.05)
        self.run_beat("b01", "One chain leaves alternatives uncovered", [
            lambda: [FadeIn(root), FadeIn(context), FadeIn(chain[0]), Create(arrows[0])],
            lambda: [FadeIn(chain[1]), FadeIn(chain[2]), Create(VGroup(arrows[1], arrows[2]))],
            lambda: [FadeIn(alt), Create(altedge), FadeIn(budget_prompt), Indicate(chain[0], color=TARGET)],
        ], "DDTree • Ringel & Romano • arXiv:2604.12989v1")

        masks = VGroup(*(node("?", x, .2, MUTED) for x in (-2.4, .1, 2.6)))
        features = at(txt("target features\nbefore b", 29, MUTED), -4.95, -1.5)
        marker = at(txt("selected\nnot processed", 26, TARGET), -4.95, 2.15)
        self.run_beat("b02", "A selected token is not yet a processed token", [
            lambda: [FadeOut(alt), FadeOut(altedge), FadeOut(budget_prompt),
                     *[Transform(a, b) for a, b in zip(chain, masks)]],
            lambda: [FadeIn(marker), Indicate(root, color=TARGET)],
            lambda: [FadeIn(features), Create(Arrow([-4.9, -1.02, 0], [-4.9, -.23, 0], color=MUTED, buff=.15))],
        ], "b is the carried bonus; the target cache ends immediately before it.")

        dist = VGroup(*(distribution(i + 1, a, b, x) for i, (a, b, x) in
                        enumerate([(0.6, 0.4, -3.5), (0.7, 0.3, 0), (0.8, 0.2, 3.5)])))
        passlabel = at(txt("one block-diffusion pass", 32, DRAFT), 0, -.2)
        band = at(RoundedRectangle(width=11.5, height=.8, corner_radius=.1, color=DRAFT,
                                   fill_color=PALE, fill_opacity=1), 0, -.2)
        inputlabel = at(txt("[ b,  MASK,  MASK,  MASK ]", 33), 0, -1.6)
        self.run_beat("b03", "One pass supplies three distributions", [
            lambda: self.clear_except() + [FadeIn(inputlabel)],
            lambda: [FadeIn(band), FadeIn(passlabel)],
            lambda: [FadeIn(dist)],
        ], "Toy vocabulary {A, B}; each position sums to 1.")

        qformula = at(txt("Q(y₁, y₂, y₃ | c,b) = q₁(y₁) q₂(y₂) q₃(y₃)", 30, DRAFT), 0, -.3)
        pformula = at(txt("p(y₁, y₂, y₃ | c,b) = ∏ᵢ p(yᵢ | c,b,y₁:ᵢ₋₁)", 30, TARGET), 0, -1.35)
        qlabel = at(txt("shared per-position marginals", 24, DRAFT), 0, -.85)
        plabel = at(txt("actual path-conditioned target factors", 24, TARGET), 0, -1.95)
        self.run_beat("b04", "A factorized surrogate is not the target", [
            lambda: [FadeOut(band), FadeOut(passlabel), FadeOut(inputlabel), FadeIn(qformula)],
            lambda: [FadeIn(qlabel), Indicate(dist[1], color=DRAFT)],
            lambda: [FadeIn(pformula), FadeIn(plabel)],
        ], "Shared conditioning (c,b) is suppressed in qᵢ. Paper §3, equations 1–2.")

        nodes, edges, labels = self.make_tree()
        tree = VGroup(*edges.values(), *nodes.values(), *labels.values())
        budget = at(txt("B = 5", 31), 4.4, 2.55)
        slots = VGroup(*(Circle(.12, color=DRAFT, stroke_width=2).move_to([3.55 + i * .42, 1.95, 0]) for i in range(5)))
        rootnote = at(txt("root is extra", 23, TARGET), -5.65, -1.02)
        six = at(txt("5 draft + 1 root\n= 6 verifier inputs", 29), 4.4, .7)
        self.run_beat("b05", "The budget buys prefixes, not the root", [
            lambda: self.clear_except() + [FadeIn(nodes["b"]), FadeIn(rootnote), FadeIn(budget), FadeIn(slots)],
            lambda: [FadeIn(nodes["A"]), FadeIn(nodes["AA"]), Create(edges["A"]), Create(edges["AA"]),
                     FadeIn(labels["A"]), FadeIn(labels["AA"])],
            lambda: [FadeIn(six), Indicate(nodes["b"], color=TARGET)],
        ], "A and AA are prefix IDs; the circle contains the actual token.")

        dsmall = VGroup(*(distribution(i + 1, a, b, x, 2.0) for i, (a, b, x) in
                          enumerate([(.6, .4, -4.8), (.7, .3, -1.8), (.8, .2, 1.2)])))
        eq = at(txt("q(AA) = 0.60 × 0.70", 34, DRAFT), 0, -2.35)
        scoreaa = at(txt("0.420", 26, DRAFT), -1.95, -.35)
        self.run_beat("b06", "A node's score is the whole prefix product", [
            lambda: [FadeOut(six), FadeOut(rootnote), FadeIn(dsmall)],
            lambda: [TransformFromCopy(VGroup(dsmall[0][1], dsmall[1][1]), eq)],
            lambda: [FadeIn(scoreaa), Transform(eq, at(txt("q(AA) = 0.60 × 0.70 = 0.420", 34, DRAFT), 0, -2.35))],
        ], "Products are under Q. They do not measure target acceptance directly.")
        scoreaaa = at(txt("0.336", 26, DRAFT), -.1, -.35)
        self.run_beat("b07", "Extending a prefix can only lower its mass", [
            lambda: [Indicate(scoreaa), Indicate(dsmall[2][1]), FadeIn(nodes["AAA"]),
                     Create(edges["AAA"]), FadeIn(labels["AAA"])],
            lambda: [Transform(eq, at(txt("q(AAA) = 0.420 × 0.80 = 0.336", 34, DRAFT), 0, -2.35))],
            lambda: [FadeIn(scoreaaa), Indicate(nodes["AA"], color=DRAFT)],
        ], "Finite-logit softmax: 0 < qᵢ(v) < 1, so ancestors precede descendants.")

        qhead = at(txt("frontier · largest first", 24, MUTED), 4.45, .95)
        queue = at(txt("A     0.600", 29, DRAFT), 4.45, -.05)
        selectedline = at(txt("selected:  —", 27), -.5, -2.5)

        def queue_to(text):
            nonlocal queue
            old = queue
            queue = at(txt(text, 28, DRAFT), 4.45, -.35)
            return AnimationGroup(FadeOut(old), FadeIn(queue), lag_ratio=1)

        def selectline(s):
            nonlocal selectedline
            old = selectedline
            selectedline = at(txt(s, 27), -.5, -2.5)
            return AnimationGroup(FadeOut(old), FadeIn(selectedline), lag_ratio=1)

        self.run_beat("b08", "A heap exposes only useful next candidates", [
            lambda: [FadeOut(dsmall), FadeOut(eq), FadeOut(scoreaa), FadeOut(scoreaaa),
                     *[FadeOut(nodes[p]) for p in ("A", "AA", "AAA")],
                     *[FadeOut(edges[p]) for p in ("A", "AA", "AAA")],
                     *[FadeOut(labels[p]) for p in ("A", "AA", "AAA")],
                     FadeIn(qhead), FadeIn(queue), FadeIn(selectedline)],
            lambda: [FadeIn(nodes["A"]), Create(edges["A"]), FadeIn(labels["A"]),
                     slots[0].animate.set_fill(DRAFT, 1), selectline("selected:  A  .600")],
            lambda: [queue_to("AA    0.420\nB      0.400")],
        ], "Pop one prefix; push its next sibling and its best child. Algorithm 1.")

        self.run_beat("b09", "Second pop: AA beats B", [
            lambda: [Indicate(queue, color=TARGET), FadeIn(nodes["AA"]), Create(edges["AA"]), FadeIn(labels["AA"])],
            lambda: [slots[1].animate.set_fill(DRAFT, 1), selectline("selected:  A  .600   →   AA  .420")],
            lambda: [queue_to("B       0.400\nAAA   0.336\nAB     0.180")],
        ], "q(AB) = .60 × .30 = .180; q(AAA) = .60 × .70 × .80 = .336")
        self.run_beat("b10", "Third pop: a branch beats a deeper node", [
            lambda: [FadeIn(nodes["B"]), Create(edges["B"]), FadeIn(labels["B"])],
            lambda: [slots[2].animate.set_fill(DRAFT, 1), selectline("selected:  A  →  AA  →  B")],
            lambda: [queue_to("AAA   0.336\nBA     0.280\nAB     0.180")],
        ], "q(B) = .400 > q(AAA) = .336; q(BA) = .40 × .70 = .280")
        self.run_beat("b11", "Stop after five pops", [
            lambda: [FadeIn(nodes["AAA"]), Create(edges["AAA"]), FadeIn(labels["AAA"]),
                     slots[3].animate.set_fill(DRAFT, 1), queue_to("BA     0.280\nAB     0.180\nAAB   0.084")],
            lambda: [FadeIn(nodes["BA"]), Create(edges["BA"]), FadeIn(labels["BA"]),
                     slots[4].animate.set_fill(DRAFT, 1), selectline("selected:  A  →  AA  →  B  →  AAA  →  BA")],
            lambda: [queue_to("BAA   0.224\nAB     0.180\nBB     0.120\nAAB   0.084")],
        ], "Queue scores are shown as products; code uses log scores. Root + B = 6 inputs.")

        expected = at(txt("E_Q[α_T] = Σ q(u)", 33, DRAFT), 3.7, 1.85)
        depthsum = at(txt("depth 1:  .600 + .400 = 1.000", 25), 3.7, .65)
        depth2 = at(txt("depth 2:  .420 + .280 = 0.700", 25), 3.7, -.1)
        depth3 = at(txt("depth 3:  .336             = 0.336", 25), 3.7, -.85)
        total = at(txt("1.000 + .700 + .336 = 2.036", 32, DRAFT), 0, -2.45)
        self.run_beat("b12", "Every reached depth contributes one match", [
            lambda: [FadeOut(qhead), FadeOut(queue), FadeOut(budget), FadeOut(slots), FadeOut(selectedline),
                     FadeIn(expected), FadeIn(depthsum), Indicate(nodes["A"]), Indicate(nodes["B"])],
            lambda: [FadeIn(depth2), Indicate(nodes["AA"]), Indicate(nodes["BA"])],
            lambda: [FadeIn(depth3), FadeIn(total), Indicate(nodes["AAA"])],
        ], "Expected speculative matches under Q only; α excludes the carried root. Equation 8.")

        contrast_title = at(txt("Same budget: B = 3", 32), 0, 2.3)
        left_title = at(txt("more dispersed", 28, DRAFT), -3.5, 1.55)
        right_title = at(txt("more concentrated", 28, DRAFT), 3.3, 1.55)
        ln = {"b": node("b", -6, -.2, TARGET), "A": node("A", -4.5, .45),
              "AA": node("A", -3, .45), "B": node("B", -4.5, -1.05)}
        rn = {"b": node("b", .3, -.2, TARGET), "A": node("A", 1.85, -.2),
              "AA": node("A", 3.4, -.2), "AAA": node("A", 4.95, -.2)}
        lefttree = VGroup(*(edge(ln[a], ln[b]) for a, b in (("b", "A"), ("A", "AA"), ("b", "B"))), *ln.values())
        righttree = VGroup(*(edge(rn[a], rn[b]) for a, b in (("b", "A"), ("A", "AA"), ("AA", "AAA"))), *rn.values())
        lq = at(txt("q(A):  .60, .70, .80", 25), -3.9, -1.95)
        rq = at(txt("q(A):  .90, .90, .80", 25), 3, -1.95)
        self.run_beat("b13", "The same budget can buy a branch or a chain", [
            lambda: self.clear_except() + [FadeIn(contrast_title), FadeIn(left_title), FadeIn(lefttree), FadeIn(lq)],
            lambda: [FadeIn(right_title), FadeIn(rq)],
            lambda: [Create(righttree)],
        ], "At each position q(B) = 1 − q(A). All numbers are illustrative, not measured.")

        ls = at(txt("A .600   AA .420   B .400", 24, DRAFT), -3.6, 1.05)
        rs = at(txt("A .900   AA .810   AAA .648", 24, DRAFT), 3.4, .65)
        optimal = at(txt("optimal for Q   ≠   optimal for p or latency", 31, TARGET), 0, -2.6)
        self.run_beat("b14", "Surrogate optimality has a precise boundary", [
            lambda: [FadeIn(ls), FadeIn(rs)],
            lambda: [Indicate(rn["AAA"]), Indicate(ln["B"])],
            lambda: [FadeIn(optimal)],
        ], "Theorem scope: a fixed node budget and the factorized draft distribution. Remark 1.")

        # Main tree returns unchanged; circles always display actual tokens.
        nodes, edges, labels = self.make_tree()
        tree = VGroup(*edges.values(), *nodes.values(), *labels.values())
        flat_ids = ["b", "A", "AA", "B", "AAA", "BA"]
        flatx = [-4.7 + i * 1.45 for i in range(6)]
        flat_tokens = VGroup(*(node("b" if p == "b" else p[-1], x, 2.05,
                                   TARGET if p == "b" else DRAFT, .28) for p, x in zip(flat_ids, flatx)))
        flat_labels = VGroup(*(at(txt(p, 20, MUTED), x, 2.67) for p, x in zip(flat_ids, flatx)))
        positions = VGroup(*(at(txt(str(d), 28, TARGET), x, 1.38) for x, d in zip(flatx, [0, 1, 2, 1, 3, 2])))
        posnote = at(txt("position = s + depth", 25, TARGET), 4.7, 1.38)
        self.run_beat("b15", "Storage order is not position order", [
            lambda: self.clear_except() + [FadeIn(tree), FadeIn(flat_labels)],
            lambda: [TransformFromCopy(VGroup(*(nodes[p] for p in flat_ids)), flat_tokens)],
            lambda: [FadeIn(positions), FadeIn(posnote)],
        ], "Flattened prefix IDs above; actual token IDs in circles. s is the root's position.")

        matrix = VGroup()
        cells = {}
        mx, my, step = 2.45, .5, .56
        prefixes = ["", "A", "AA", "B", "AAA", "BA"]
        for r in range(6):
            for c in range(6):
                sq = Rectangle(width=.50, height=.50, stroke_color="#CAD5D3", stroke_width=1,
                               fill_color=BG, fill_opacity=1).move_to([mx + c * step, my - r * step, 0])
                cells[r, c] = sq
                matrix.add(sq)
        mlabs = VGroup()
        for i, name in enumerate(flat_ids):
            mlabs.add(at(txt(name, 18), mx - .6, my - i * step))
            mlabs.add(at(txt(name, 18), mx + i * step, my + .48))
        cache = at(txt("+ cached context", 23, MUTED), 4, -2.88)
        ban = at(txt("other branch blocked", 24, TARGET), -.2, -2.35)
        self.run_beat("b16", "Tree attention isolates sibling paths", [
            lambda: [FadeIn(matrix), FadeIn(mlabs), FadeIn(cache)],
            lambda: [*[cells[5, c].animate.set_fill(DRAFT, 1) for c in (0, 3, 5)],
                     Indicate(nodes["b"]), Indicate(nodes["B"]), Indicate(nodes["BA"])],
            lambda: [FadeIn(ban), nodes["A"].animate.set_opacity(.3),
                     nodes["AA"].animate.set_opacity(.3), nodes["AAA"].animate.set_opacity(.3)],
        ], "Mask row = query node; column = visible key. BA sees b, B, BA, plus prior context.")

        pass2 = at(txt("one target pass", 31, TARGET), -3.2, -2.55)
        conditional = at(txt("p(next | c,b,B)\n≠ p(next | c,b,A)", 25, TARGET), -3.8, -2.5)
        self.run_beat("b17", "Parallel scoring, path-correct conditionals", [
            lambda: [FadeOut(ban), *[cells[r, c].animate.set_fill(DRAFT if prefixes[r].startswith(prefixes[c]) else BG, 1)
                                     for r in range(6) for c in range(6)],
                     *[nodes[p].animate.set_opacity(1) for p in ("A", "AA", "AAA")]],
            lambda: [FadeIn(pass2), *[Indicate(n, color=TARGET) for n in nodes.values()]],
            lambda: [FadeOut(pass2), FadeIn(conditional)],
        ], "Each row includes root, ancestors, self. No sibling leakage. Paper §4.4.")

        choices = {
            "b": at(txt("choose B", 25, TARGET), -5.65, .95),
            "B": at(txt("choose A", 25, TARGET), -3.8, -2.3),
            "BA": at(txt("choose B", 25, TARGET), -1.95, -2.3),
        }
        walktitle = at(txt("toy target outcome", 27, TARGET), 3.8, 2.2)
        outlabel = at(txt("output", 25, MUTED), 2.5, .9)
        output = VGroup(node("b", 2.2, .0, TARGET), node("B", 3.2, .0, TARGET),
                        node("A", 4.2, .0, TARGET), node("B", 5.3, .0, TARGET))
        pointer = Circle(.46, color=TARGET, stroke_width=5).move_to(nodes["b"])
        self.run_beat("b18", "The target chooses; the draft offers routes", [
            lambda: [FadeOut(flat_tokens), FadeOut(flat_labels), FadeOut(positions), FadeOut(posnote),
                     FadeOut(matrix), FadeOut(mlabs), FadeOut(cache), FadeOut(conditional),
                     FadeIn(choices["b"]), FadeIn(walktitle), FadeIn(pointer), FadeIn(outlabel), FadeIn(output[0])],
            lambda: [Indicate(choices["b"], color=TARGET)],
            lambda: [pointer.animate.move_to(nodes["B"]), edges["B"].animate.set_color(TARGET),
                     FadeIn(output[1])],
        ], "This is a target-directed walk, not selection by the largest draft q score.")

        matchcount = at(txt("2 speculative matches", 27, TARGET), 3.75, -1.0)
        self.run_beat("b19", "A matching child reuses an existing target output", [
            lambda: [FadeIn(choices["B"]), Indicate(nodes["B"], color=TARGET)],
            lambda: [pointer.animate.move_to(nodes["BA"]), edges["BA"].animate.set_color(TARGET), FadeIn(output[2])],
            lambda: [FadeIn(matchcount)],
        ], "No second verifier call: outputs for all tree nodes were computed together.")

        absent = node("B", -.05, -1.2, TARGET)
        absentedge = edge(nodes["BA"], absent, TARGET)
        absentlabel = at(txt("not in tree", 22, TARGET), -.05, -.6)
        bonuslabel = at(txt("next bonus\nnot processed", 23, TARGET), 5.0, -2.15)
        self.run_beat("b20", "An unmatched target token becomes the next root", [
            lambda: [FadeIn(choices["BA"]), FadeIn(absentlabel)],
            lambda: [FadeIn(absent), Create(absentedge)],
            lambda: [TransformFromCopy(absent, output[3]), FadeIn(bonuslabel)],
        ], "Keep the matched path. Emit the unmatched target token as the next bonus.")

        rule1 = at(txt("target: greedy or sampled", 32, TARGET), 0, 1.95)
        rule2 = at(txt("missing child  /  leaf   →   next bonus", 31), 0, .75)
        rule3 = at(txt("…   token   STOP   later tokens", 34), 0, -.75)
        stopline = Line([1.9, -1.08, 0], [4.5, -1.08, 0], color=TARGET, stroke_width=5)
        retain = at(txt("first STOP retained; suffix removed", 28, TARGET), 0, -1.95)
        self.run_beat("b21", "Match children, not acceptance ratios", [
            lambda: self.clear_except() + [FadeIn(rule1)],
            lambda: [FadeIn(rule2)],
            lambda: [FadeIn(rule3), Create(stopline), FadeIn(retain)],
        ], "Generation also respects max_new_tokens. No min(1, p/q) test is used here.")

        cachetitle = at(txt("target KV cache: processed nodes", 31), 0, 2.25)
        cachecells = VGroup()
        for i, p in enumerate(flat_ids):
            box = at(Rectangle(width=1.15, height=.8, color=DRAFT, fill_color=PALE, fill_opacity=1), -4.1 + i * 1.65, .85)
            cachecells.add(VGroup(box, at(txt(p, 28), -4.1 + i * 1.65, .85)))
        retained = VGroup()
        for i, p in enumerate(["b", "B", "BA"]):
            box = at(Rectangle(width=1.15, height=.8, color=TARGET, fill_color="#F6E4D8", fill_opacity=1), -3 + i * 1.65, -1.1)
            retained.add(VGroup(box, at(txt(p, 28), -3 + i * 1.65, -1.1)))
        nextroot = node("B", 4.8, -1.1, TARGET)
        outsidenote = at(txt("bonus outside cache", 24, TARGET), 4.5, -2.05)
        self.run_beat("b22", "Retain only the path actually processed", [
            lambda: self.clear_except() + [FadeIn(cachetitle), FadeIn(cachecells)],
            lambda: [TransformFromCopy(VGroup(cachecells[0], cachecells[3], cachecells[5]), retained),
                     *[cachecells[i].animate.set_opacity(.2) for i in (1, 2, 4)]],
            lambda: [FadeIn(nextroot), FadeIn(outsidenote)],
        ], "Retained prefix IDs: b, B, BA. Actual tokens: b, B, A. Next bonus B is not cached.")

        costs = VGroup()
        for x, name, col in [(-4.8, "draft", DRAFT), (-1.6, "build tree", DRAFT),
                             (1.6, "verify", TARGET), (4.8, "compact", TARGET)]:
            costs.add(VGroup(at(Rectangle(width=2.65, height=.9, color=col, stroke_width=2), x, 1.5),
                             at(txt(name, 29, col), x, 1.5)))
        allocate = at(txt("q: allocate paths", 35, DRAFT), -3.0, -.05)
        decide = at(txt("p: choose tokens", 35, TARGET), 3.0, -.05)
        costnote = at(txt("more coverage  ≠  free verification", 34), 0, -2.15)
        self.run_beat("b23", "Coverage helps only when it earns its cost", [
            lambda: self.clear_except(nextroot) + [FadeIn(costs[0]), FadeIn(costs[1]),
                                                   nextroot.animate.move_to([-5.4, -1.5, 0])],
            lambda: [FadeIn(costs[2]), FadeIn(costs[3]), FadeIn(allocate), FadeIn(decide)],
            lambda: [FadeIn(costnote)],
        ], "Conceptual stages, not measured latency. More nodes do not guarantee speedup.")

        finalnodes = [node("B", -4.8, -.45, TARGET), node("A", -2.5, .45),
                      node("B", -2.5, -1.25), node("A", -.2, -1.25), node("B", 2.1, -1.25, TARGET)]
        finaledges = VGroup(edge(finalnodes[0], finalnodes[1]), edge(finalnodes[0], finalnodes[2], TARGET),
                            edge(finalnodes[2], finalnodes[3], TARGET), edge(finalnodes[3], finalnodes[4], TARGET))
        endline = at(txt("Spend q on coverage.\nLet p choose the path.", 37), 3.2, 1.1)
        endcredit = at(txt("Ringel & Romano • DDTree\narXiv:2604.12989v1 · §3–4\nCode: c96427a18567", 23, MUTED), 3.5, -2.3)
        self.run_beat("b24", "A broader opportunity, the same target decision", [
            lambda: self.clear_except() + [FadeIn(VGroup(*finalnodes[:4])), Create(VGroup(*finaledges[:3]))],
            lambda: [FadeIn(finalnodes[4]), Create(finaledges[3]), FadeIn(endline)],
            lambda: [FadeIn(endcredit), Indicate(finalnodes[4], color=TARGET)],
        ], "The next target-selected bonus starts the next round.")

        outdir = ROOT / os.environ.get("DDTREE_RECORD_DIR", "records")
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "timeline.json").write_text(json.dumps({
            "created_utc": datetime.now(timezone.utc).isoformat(), "narrated": bool(self.speech),
            "duration": float(self.time), "fps": config.frame_rate, "beats": self.timeline,
        }, indent=2), encoding="utf-8")
        (outdir / "geometry.json").write_text(json.dumps({
            "scope": "Top-level visible mobject frame bounds after every semantic action; not a collision proof",
            "frame": [config.frame_width, config.frame_height], "out_of_frame": self.geometry,
            "node_radius": .34, "main_tree_min_horizontal_spacing": 1.85,
            "matrix_cell_step": .56, "matrix_cell_width": .50,
        }, indent=2), encoding="utf-8")
