"""Semantic token primitives."""

from enum import Enum

from manim import BLUE, GRAY, GREEN, RED, YELLOW, RoundedRectangle, Text, VGroup

# Backward-compatible: these direct manim color imports are retained so
# existing code referencing STATE_COLORS keeps working.  New scenes should
# prefer manim_lib.theme role colors.


class TokenState(str, Enum):
    """Visual states shared by token-based explainers."""

    NEUTRAL = "neutral"
    SPECULATIVE = "speculative"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ACTIVE = "active"


STATE_COLORS = {
    TokenState.NEUTRAL: GRAY,
    TokenState.SPECULATIVE: BLUE,
    TokenState.ACCEPTED: GREEN,
    TokenState.REJECTED: RED,
    TokenState.ACTIVE: YELLOW,
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
        self.box = RoundedRectangle(
            width=width, height=height, corner_radius=0.08
        )
        self.label = Text(token, font_size=font_size).move_to(self.box)
        self.add(self.box, self.label)
        self.set_state(state)

    def set_state(self, state: TokenState) -> "TokenBox":
        """Apply a token state in place and return this object."""
        self.state = state
        color = STATE_COLORS[state]
        self.box.set_stroke(color, width=2.5)
        self.box.set_fill(color, opacity=0.18 if state != TokenState.NEUTRAL else 0.08)
        self.label.set_color(RED if state == TokenState.REJECTED else "#FFFFFF")
        return self


class TokenSequence(VGroup):
    """A stable, horizontally arranged sequence of :class:`TokenBox` objects."""

    def __init__(self, *tokens: str, buff: float = 0.12) -> None:
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
            self.token_box, direction=(0, -1, 0), buff=0.1
        )
        self.add(self.token_box, self.probability_label)
