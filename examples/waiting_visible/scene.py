"""A causal, shared-clock picture of speculative decoding.

The payoff is designed first: the same accepted prefix reaches two different
completion points on one time scale. All durations are illustrative.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Circle,
    Create,
    DashedLine,
    FadeIn,
    FadeOut,
    Line,
    Polygon,
    Rectangle,
    Restore,
    Text,
    UpdateFromAlphaFunc,
    VGroup,
    linear,
)

from manim_lib import (
    ACCENT,
    BACKGROUND,
    NEUTRAL,
    PRIMARY,
    SUCCESS,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    EventTimeline,
    NarratedScene,
)


WORDS = ("can", "reason", "fast")
NARRATION = (
    "Watch the waiting. The next token cannot start until this target pass finishes.",
    "Then another pass. And another. Three tokens, three expensive waits.",
    "Now keep the same clock. A small draft model proposes three tokens, one after another.",
    "They're only guesses.",
    "One target pass checks the proposed positions together.",
    "Here, all three are accepted. The same prefix is ready sooner, even including drafting.",
)
BASELINE_Y = 1.60
DRAFT_Y = -0.30
ROW_Y = (-0.95, -1.50, -2.05)
TIMELINE_LENGTH = 10.20
ZOOM = 1.65


@dataclass(frozen=True)
class ToyTiming:
    """A deliberately simple cost model, not measured model latency."""

    target_pass: float = 1.0
    draft_step: float = 0.2
    verification: float = 1.0

    def __post_init__(self):
        if not all(
            isfinite(value) and value > 0
            for value in (self.target_pass, self.draft_step, self.verification)
        ):
            raise ValueError("Toy durations must be positive and finite")

    @property
    def baseline_end(self):
        return len(WORDS) * self.target_pass

    @property
    def draft_end(self):
        return len(WORDS) * self.draft_step

    @property
    def speculative_end(self):
        return self.draft_end + self.verification


TIMING = ToyTiming()


def label(text, *, size=20, color=TEXT_SECONDARY, font="Segoe UI"):
    return Text(text, font=font, font_size=size, color=color)


class WorkInterval(VGroup):
    """A duration whose moving boundary exposes completion, not a model box."""

    def __init__(self, timeline, start, end, y, *, color, height=0.30, text=None):
        if not timeline.start_value <= start < end <= timeline.end_value:
            raise ValueError("Work must lie within the shared timeline")
        x0 = timeline.point_at(start)[0]
        x1 = timeline.point_at(end)[0]
        self.start_time = start
        self.end_time = end
        self.base_height = height
        self.progress = 0.0
        self.track = Rectangle(
            width=x1 - x0,
            height=height,
            fill_color=SURFACE,
            fill_opacity=1,
            stroke_width=0,
        ).move_to(((x0 + x1) / 2, y, 0))
        self.fill = Polygon(
            (x0, y - height / 2, 0),
            (x0, y + height / 2, 0),
            (x0, y + height / 2, 0),
            (x0, y - height / 2, 0),
            fill_color=color,
            fill_opacity=0.34 if height < 0.5 else 0.13,
            stroke_width=0,
        )
        self.rail = Line(
            (x0, y - height / 2, 0),
            (x1, y - height / 2, 0),
            color=NEUTRAL.dim,
            stroke_width=1.4,
        )
        self.cursor = Line(
            (x0, y - height / 2 - 0.06, 0),
            (x0, y + height / 2 + 0.06, 0),
            color=color,
            stroke_width=3,
        )
        super().__init__(self.track, self.fill, self.rail, self.cursor)
        self.caption = None
        if text:
            self.caption = label(text).next_to(self.track, DOWN, buff=0.16)
            self.add(self.caption)

    def set_progress(self, alpha):
        if not isfinite(alpha) or not 0 <= alpha <= 1:
            raise ValueError("Progress must be between zero and one")
        self.progress = alpha
        left = self.track.get_left()[0]
        right = left + self.track.width * alpha
        bottom = self.track.get_bottom()[1]
        top = self.track.get_top()[1]
        self.fill.set_points_as_corners(
            [
                (left, bottom, 0),
                (left, top, 0),
                (right, top, 0),
                (right, bottom, 0),
                (left, bottom, 0),
            ]
        )
        padding = 0.06 * self.track.height / self.base_height
        self.cursor.put_start_and_end_on(
            (right, bottom - padding, 0), (right, top + padding, 0)
        )
        return self

    def finish(self):
        self.set_progress(1)
        self.cursor.set_stroke(opacity=0)
        return self


class TokenMark(VGroup):
    """Outline means tentative; solid means accepted. The marker survives."""

    def __init__(self, word, point, *, accepted=False, direction=UP):
        self.word = word
        self.accepted = accepted
        self.dot = Circle(
            radius=0.105,
            stroke_color=PRIMARY.light,
            stroke_width=2.2,
            fill_color=BACKGROUND,
            fill_opacity=1,
        ).move_to(point)
        self.word_label = label(
            word, size=28, font="Georgia", color=TEXT_PRIMARY
        ).next_to(self.dot, direction, buff=0.15)
        super().__init__(self.dot, self.word_label)
        self.set_z_index(3)
        if accepted:
            self.accept()

    def accept(self):
        self.accepted = True
        self.dot.set_fill(SUCCESS.light, opacity=1).set_stroke(
            SUCCESS.light, width=1.4
        )
        return self


class WaitingPicture:
    """Scene-local objects shared by the animation and its geometry tests."""

    def __init__(self):
        self.clock = EventTimeline(
            start=0, end=TIMING.baseline_end, length=TIMELINE_LENGTH
        )
        self.upper_label = label("Standard decoding", color=TEXT_PRIMARY)
        self.upper_label.move_to((-5.1, 3.12, 0), aligned_edge=LEFT)
        self.lower_label = label("Speculative decoding", color=TEXT_PRIMARY)
        self.lower_label.move_to((-5.1, 0.35, 0), aligned_edge=LEFT)
        self.assumption = label("Illustrative time  /  all accepted", size=18)
        self.assumption.move_to((-5.85, -3.48, 0), aligned_edge=LEFT)
        self.scale_note = label("same time scale", size=18)
        self.scale_note.move_to((5.1, 0.35, 0), aligned_edge=RIGHT)

        self.baseline_intervals = []
        self.baseline_tokens = []
        self.stems = []
        self.stages = []
        for index, word in enumerate(WORDS):
            end = (index + 1) * TIMING.target_pass
            interval = WorkInterval(
                self.clock,
                index * TIMING.target_pass,
                end,
                BASELINE_Y,
                color=ACCENT.base,
                text="target pass",
            )
            x = self.clock.point_at(end)[0]
            token = TokenMark(word, (x, 2.16, 0), accepted=True)
            stem = Line(
                (x, BASELINE_Y + 0.15, 0),
                token.dot.get_bottom(),
                color=SUCCESS.base,
                stroke_width=1.5,
            )
            self.baseline_intervals.append(interval)
            self.baseline_tokens.append(token)
            self.stems.append(stem)
            self.stages.append(VGroup(interval, stem, token))
        start_x = self.clock.point_at(0)[0]
        self.origin = VGroup(
            Circle(
                radius=0.06, fill_color=TEXT_PRIMARY, fill_opacity=1, stroke_width=0
            ).move_to((start_x, BASELINE_Y, 0)),
            label("The model", size=22, font="Georgia").move_to(
                (start_x, 2.16, 0)
            ),
        )
        self.stages[0].add(self.origin)
        self.baseline = VGroup(*self.stages)

        self.drafts = [
            WorkInterval(
                self.clock,
                index * TIMING.draft_step,
                (index + 1) * TIMING.draft_step,
                DRAFT_Y,
                color=PRIMARY.base,
                height=0.18,
            )
            for index in range(len(WORDS))
        ]
        self.candidates = [
            TokenMark(
                word,
                (self.clock.point_at((index + 1) * TIMING.draft_step)[0], DRAFT_Y, 0),
                direction=LEFT,
            )
            for index, word in enumerate(WORDS)
        ]
        for candidate in self.candidates:
            candidate.word_label.set_opacity(0)
        self.draft_caption = label("draft", color=PRIMARY.light).next_to(
            VGroup(*self.drafts), UP, buff=0.13
        )
        self.verifier = WorkInterval(
            self.clock,
            TIMING.draft_end,
            TIMING.speculative_end,
            -1.50,
            height=1.68,
            color=ACCENT.base,
        )
        self.verify_caption = label("one target pass", color=ACCENT.light)
        self.verify_caption.next_to(self.verifier.track, UP, buff=0.22)
        self.verify_rows = VGroup(
            *[
                Line(
                    (self.clock.point_at(TIMING.draft_end)[0], y, 0),
                    (self.clock.point_at(TIMING.speculative_end)[0], y, 0),
                    stroke_width=1.1,
                    color=NEUTRAL.dim,
                )
                for y in ROW_Y
            ]
        )
        self.lead_ins = VGroup(
            *[
                DashedLine(
                    (self.clock.point_at((index + 1) * TIMING.draft_step)[0], y, 0),
                    (self.clock.point_at(TIMING.draft_end)[0], y, 0),
                    color=PRIMARY.dim,
                    stroke_width=1.2,
                )
                for index, y in enumerate(ROW_Y[:-1])
            ]
        )
        self.start_guide = DashedLine(
            (start_x, BASELINE_Y - 0.2, 0),
            (start_x, DRAFT_Y - 0.16, 0),
            stroke_width=1,
            stroke_opacity=0.45,
            color=NEUTRAL.base,
        )
        self.baseline_finish_x = self.clock.point_at(TIMING.baseline_end)[0]
        self.speculative_finish_x = self.clock.point_at(TIMING.speculative_end)[0]
        self.finish_guides = VGroup(
            DashedLine(
                (self.baseline_finish_x, BASELINE_Y, 0),
                (self.baseline_finish_x, -2.85, 0),
                color=NEUTRAL.base,
                stroke_width=1.2,
            ),
            Line(
                (self.speculative_finish_x, -2.35, 0),
                (self.speculative_finish_x, -2.85, 0),
                color=SUCCESS.light,
                stroke_width=1.8,
            ),
        )
        self.saved_time = VGroup(
            Line(
                (self.speculative_finish_x, -2.85, 0),
                (self.baseline_finish_x, -2.85, 0),
                color=SUCCESS.light,
                stroke_width=2,
            ),
            *[
                Line(
                    (x, -2.73, 0), (x, -2.97, 0),
                    color=SUCCESS.light, stroke_width=2,
                )
                for x in (self.speculative_finish_x, self.baseline_finish_x)
            ],
        )
        self.payoff = label(
            "Less waiting.", size=34, font="Georgia", color=SUCCESS.light
        ).next_to(self.saved_time, DOWN, buff=0.20)
        self.same_prefix = label(
            "Same accepted prefix", color=TEXT_PRIMARY
        ).move_to((3.30, -1.45, 0))
        self.prefix = label(
            "can  reason  fast", size=28, font="Georgia", color=SUCCESS.light
        ).next_to(self.same_prefix, DOWN, buff=0.18)

    def candidate_row_position(self, index):
        return np.array([
            self.clock.point_at((index + 1) * TIMING.draft_step)[0],
            ROW_Y[index],
            0,
        ])

    def accepted_position(self, index):
        return np.array([self.speculative_finish_x, ROW_Y[index], 0])


class WaitingVisible(NarratedScene):
    """From one dependent pass to a shorter all-accepted speculative round."""

    review_timeline_path = Path("media/review/waiting_visible/timeline.json")
    external_voiceover_subdir = "waiting_visible_external"

    @contextmanager
    def beat(self, index):
        with self.narrate(NARRATION[index]) as tracker:
            start = self.time
            yield tracker
            remaining = tracker.duration - (self.time - start)
            if remaining > 0:
                self.wait(remaining)

    def run_work(self, interval, duration):
        self.play(
            UpdateFromAlphaFunc(interval, lambda item, alpha: item.set_progress(alpha)),
            run_time=duration,
            rate_func=linear,
        )
        interval.finish()

    def construct(self):
        p = self.picture = WaitingPicture()
        first = p.stages[0]
        home = first.get_center().copy()
        first.scale(ZOOM).move_to((0, 0.40, 0))
        opening = label(
            "The next token has to wait.", size=32, font="Georgia",
            color=TEXT_PRIMARY,
        ).move_to((0, -1.60, 0))
        self.add(p.baseline_intervals[0], p.origin, opening)

        with self.beat(0) as tracker:
            self.run_work(p.baseline_intervals[0], max(2.5, tracker.duration - 1.0))
            self.play(
                Create(p.stems[0]), FadeIn(p.baseline_tokens[0]), run_time=0.4
            )
            self.wait(0.35)

        self.remove(p.baseline_intervals[0], p.origin, p.stems[0], p.baseline_tokens[0])
        self.add(first)
        with self.beat(1) as tracker:
            self.play(
                first.animate.scale(1 / ZOOM).move_to(home),
                FadeOut(opening),
                FadeIn(p.upper_label),
                run_time=0.9,
            )
            pass_duration = max(0.9, (tracker.duration - 1.6) / 2)
            for index in (1, 2):
                self.add(p.baseline_intervals[index])
                self.run_work(p.baseline_intervals[index], pass_duration)
                self.play(
                    Create(p.stems[index]),
                    FadeIn(p.baseline_tokens[index]),
                    run_time=0.3,
                )

        self.remove(*p.stages, *p.baseline_intervals, *p.baseline_tokens, *p.stems)
        self.add(p.baseline)
        p.baseline.save_state()
        with self.beat(2) as tracker:
            self.play(
                p.baseline.animate.fade(0.50),
                FadeIn(p.lower_label),
                Create(p.start_guide),
                FadeIn(p.scale_note),
                FadeIn(p.assumption),
                run_time=0.65,
            )
            self.play(FadeIn(p.draft_caption), run_time=0.25)
            for interval, candidate in zip(p.drafts, p.candidates):
                self.add(interval)
                self.run_work(interval, 0.5)
                self.play(FadeIn(candidate.dot), run_time=0.15)
            self.wait(0.25)
            self.remove(*(candidate.dot for candidate in p.candidates))
            self.add(*p.candidates)
            self.play(
                *[
                    candidate.animate.shift(
                        p.candidate_row_position(index) - candidate.dot.get_center()
                    )
                    for index, candidate in enumerate(p.candidates)
                ],
                run_time=0.8,
            )
            self.play(
                *[candidate.word_label.animate.set_opacity(1) for candidate in p.candidates],
                run_time=0.3,
            )

        with self.beat(3):
            self.play(
                FadeIn(p.verifier.track),
                Create(p.verify_rows),
                Create(p.lead_ins),
                FadeIn(p.verify_caption),
                run_time=0.65,
            )

        with self.beat(4) as tracker:
            # One boundary spans all three rows. A row-by-row sweep would imply
            # serial target passes, the exact misconception this picture avoids.
            self.remove(p.verifier.track)
            self.add(p.verifier)
            self.bring_to_front(p.verify_rows, *p.candidates)
            self.run_work(p.verifier, max(2.0, tracker.duration - 0.3))

        with self.beat(5):
            self.play(
                *[
                    candidate.animate.shift(
                        p.accepted_position(index) - candidate.dot.get_center()
                    ).accept()
                    for index, candidate in enumerate(p.candidates)
                ],
                run_time=0.65,
            )
            self.play(
                Restore(p.baseline),
                Create(p.finish_guides),
                run_time=0.65,
            )
            self.play(Create(p.saved_time), run_time=0.7)
            self.wait(0.45)
            self.play(
                FadeIn(p.payoff),
                FadeIn(p.same_prefix),
                FadeIn(p.prefix),
                run_time=0.5,
            )
        self.wait(1.0)
        self._finalize()
