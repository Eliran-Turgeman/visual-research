"""Semantic token primitives."""

from enum import Enum

from manim import DOWN, RIGHT, RoundedRectangle, Text, VGroup

from .theme import (
    ACCENT,
    DANGER,
    NEUTRAL,
    PRIMARY,
    SHADOW,
    SPACING,
    STROKES,
    SUCCESS,
    SURFACE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class TokenState(str, Enum):
    """Visual states shared by token-based explainers."""

    NEUTRAL = "neutral"
    SPECULATIVE = "speculative"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ACTIVE = "active"


STATE_COLORS = {
    TokenState.NEUTRAL: NEUTRAL.base,
    TokenState.SPECULATIVE: PRIMARY.base,
    TokenState.ACCEPTED: SUCCESS.base,
    TokenState.REJECTED: DANGER.base,
    TokenState.ACTIVE: ACCENT.base,
}


class TokenBox(VGroup):
    """A fixed-size token box whose state can change without moving it."""

    def __init__(
        self,
        token: str,
        *,
        state: TokenState = TokenState.NEUTRAL,
        width: float = 1.15,
        height: float = 0.62,
        font_size: float = 28,
    ) -> None:
        super().__init__()
        self.token = token
        self.state = state
        self.shadow = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=min(0.14, height * 0.24),
            stroke_width=0,
            fill_color=SHADOW,
            fill_opacity=0.55,
        ).shift(RIGHT * 0.045 + DOWN * 0.055)
        self.box = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=min(0.14, height * 0.24),
            stroke_width=STROKES.normal.width,
            fill_color=SURFACE,
        )
        self.inner_border = RoundedRectangle(
            width=max(0.05, width - 0.07),
            height=max(0.05, height - 0.07),
            corner_radius=min(0.12, height * 0.20),
            fill_opacity=0,
        ).move_to(self.box)
        self.label = Text(token, font_size=font_size, color=TEXT_PRIMARY)
        self._fit_label(width, height)
        self.label.move_to(self.box)
        self.add(self.shadow, self.box, self.inner_border, self.label)
        self.set_state(state)

    def _fit_label(self, width: float, height: float) -> None:
        """Keep long tokens readable without allowing them to escape the box."""
        max_width = width - 2 * SPACING.xs
        max_height = height * 0.55
        factor = min(
            1.0,
            max_width / self.label.width if self.label.width else 1.0,
            max_height / self.label.height if self.label.height else 1.0,
        )
        if factor < 1.0:
            self.label.scale(factor)

    def set_state(self, state: TokenState) -> "TokenBox":
        """Apply a token state in place and return this object."""
        self.state = state
        color = STATE_COLORS[state]
        active = state is not TokenState.NEUTRAL
        self.box.set_stroke(
            color if active else NEUTRAL.dim,
            width=STROKES.heavy.width if state is TokenState.ACTIVE else STROKES.normal.width,
            opacity=1.0 if active else 0.8,
        )
        self.box.set_fill(color if active else SURFACE, opacity=0.22 if active else 0.96)
        self.inner_border.set_stroke(
            color if active else NEUTRAL.base,
            width=STROKES.hairline.width,
            opacity=0.34 if active else 0.18,
        )
        self.label.set_color(DANGER.light if state is TokenState.REJECTED else TEXT_PRIMARY)
        return self


class TokenSequence(VGroup):
    """A stable, horizontally arranged sequence of :class:`TokenBox` objects."""

    def __init__(self, *tokens: str, buff: float = SPACING.xs) -> None:
        self.token_boxes = [TokenBox(token) for token in tokens]
        super().__init__(*self.token_boxes)
        self.buff = buff
        self.arrange(buff=buff)

    def append_token(
        self, token: str, *, state: TokenState = TokenState.NEUTRAL
    ) -> TokenBox:
        """Append a token at the sequence edge without moving the existing prefix."""
        box = TokenBox(token, state=state)
        if self.token_boxes:
            box.next_to(self.token_boxes[-1], buff=self.buff)
        self.token_boxes.append(box)
        self.add(box)
        return box


class CandidateToken(VGroup):
    """A token box with a probability or score directly associated beneath it."""

    def __init__(
        self,
        token: str,
        probability: float | str,
        *,
        state: TokenState = TokenState.SPECULATIVE,
    ) -> None:
        super().__init__()
        self.token_box = TokenBox(token, state=state)
        value = (
            f"{probability:.0%}" if isinstance(probability, float) else str(probability)
        )
        self.probability_label = Text(value, font_size=20).next_to(
            self.token_box, direction=DOWN, buff=SPACING.xs
        )
        self.probability_label.set_color(TEXT_SECONDARY)
        self.add(self.token_box, self.probability_label)
