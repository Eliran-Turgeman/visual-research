"""Helpers for progressive equation presentation."""

from manim import MathTex, TransformMatchingTex

from .theme import TEXT_PRIMARY


class EquationSteps:
    """Build matching equations and transformations between adjacent steps."""

    def __init__(self, *steps: str, font_size: float = 44) -> None:
        if not steps:
            raise ValueError("At least one equation step is required")
        self.equations = [
            MathTex(step, font_size=font_size, color=TEXT_PRIMARY)
            for step in steps
        ]

    @property
    def first(self) -> MathTex:
        """Return the initial equation."""
        return self.equations[0]

    def transform(self, index: int, *, run_time: float = 1.0):
        """Transform step ``index`` into the following step using matching terms."""
        if index < 0 or index >= len(self.equations) - 1:
            raise IndexError("Equation step has no following step")
        target = self.equations[index + 1].move_to(self.equations[index])
        return TransformMatchingTex(
            self.equations[index], target, run_time=run_time
        )
