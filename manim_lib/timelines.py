"""Timeline primitive for scheduling and concurrency explanations."""

from manim import BLUE, DOWN, LEFT, Line, Rectangle, Text, VGroup


class EventTimeline(VGroup):
    """A labeled horizontal timeline with event markers and duration intervals."""

    def __init__(
        self,
        *,
        start: float = 0,
        end: float = 10,
        length: float = 8,
        label: str | None = None,
    ) -> None:
        if end <= start:
            raise ValueError("Timeline end must be greater than start")
        super().__init__()
        self.start_value = start
        self.end_value = end
        self.axis = Line(LEFT * length / 2, -LEFT * length / 2)
        self.add(self.axis)
        if label:
            self.add(Text(label, font_size=22).next_to(self.axis, LEFT, buff=0.25))

    def point_at(self, value: float):
        """Return the scene point corresponding to a timeline value."""
        alpha = (value - self.start_value) / (self.end_value - self.start_value)
        return self.axis.point_from_proportion(alpha)

    def add_event(self, value: float, label: str) -> VGroup:
        """Add and return a labeled event marker."""
        point = self.point_at(value)
        tick = Line(point + DOWN * 0.12, point - DOWN * 0.12, color=BLUE)
        text = Text(label, font_size=18).next_to(tick, DOWN, buff=0.1)
        event = VGroup(tick, text)
        self.add(event)
        return event

    def add_interval(
        self, start: float, end: float, label: str, *, color=BLUE
    ) -> VGroup:
        """Add and return a labeled duration bar."""
        left = self.point_at(start)
        right = self.point_at(end)
        bar = Rectangle(
            width=max(right[0] - left[0], 0.02),
            height=0.28,
            color=color,
            fill_color=color,
            fill_opacity=0.4,
        ).move_to((left + right) / 2 + DOWN * 0.5)
        text = Text(label, font_size=17).move_to(bar)
        interval = VGroup(bar, text)
        self.add(interval)
        return interval
