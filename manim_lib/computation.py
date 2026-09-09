"""A reusable helper for narrated computations.

Use this whenever narration describes a computation: it makes the operands,
the operation, and the result's interpretation explicit objects instead of a
single opaque number. It builds a part-indexed ``MathTex`` equation so a
scene can grab the exact submobject for an operand or the result, for example
to visually connect a highlighted table cell to an operand, or a result to
the node it produces.

This module returns mobjects, not an ``Animation`` subclass, so a scene
remains free to choose how and when to animate them (``Write``, ``FadeIn``,
``TransformFromCopy``, and so on) alongside its own narration pacing.
"""

from dataclasses import dataclass
from math import isclose, prod

from manim import MathTex, Text

from .theme import ACCENT, TEXT_PRIMARY, TEXT_SECONDARY


@dataclass(frozen=True)
class Operand:
    """One labeled numeric input to a :class:`Computation`.

    ``tex`` overrides the default decimal rendering when a toy example uses a
    specific display convention (for example ``.55`` instead of ``0.55``).
    """

    label: str
    value: float
    tex: str | None = None

    @property
    def display(self) -> str:
        """Return the LaTeX-safe display string for this operand."""
        return self.tex if self.tex is not None else f"{self.value:.3g}"


class Computation:
    """A narrated input -> operation -> result step.

    ``exact_result`` is preserved at full precision even though the equation
    displays a rounded value, so a scene can state "about 0.172" while later
    arithmetic keeps using the exact product. When ``exact_result`` is
    omitted and ``operator`` is multiplication, it is computed automatically
    from the operand values, which keeps the displayed equation and the
    underlying numbers from silently drifting apart.
    """

    def __init__(
        self,
        *operands: Operand,
        operator: str = r"\times",
        exact_result: float | None = None,
        result_digits: int = 3,
        interpretation: str | None = None,
        leading_zero: bool = True,
    ) -> None:
        if len(operands) < 2:
            raise ValueError("A computation needs at least two operands")
        if exact_result is None:
            if operator != r"\times":
                raise ValueError(
                    "exact_result is required unless operator is '\\times'"
                )
            exact_result = prod(operand.value for operand in operands)
        self.operands = operands
        self.operator = operator
        self.exact_result = exact_result
        self.result_digits = result_digits
        self.interpretation = interpretation
        self.leading_zero = leading_zero

    @property
    def result_display(self) -> str:
        """Return the rounded, display-friendly result string.

        When ``leading_zero`` is ``False``, a result between -1 and 1 is
        shown without its leading zero (``.330`` instead of ``0.330``), to
        match a toy example's existing display convention.
        """
        rounded = round(self.exact_result, self.result_digits)
        text = f"{rounded:.{self.result_digits}f}"
        if not self.leading_zero and text.startswith("0."):
            text = text[1:]
        elif not self.leading_zero and text.startswith("-0."):
            text = "-" + text[2:]
        return text

    def build_equation(self, *, font_size: float = 30, result_color=None) -> MathTex:
        """Build operands, operators, a relation, and the displayed result.

        Use :meth:`operand_term` and :meth:`result_term` to reference the
        individual parts of the returned mobject. Rounded results use an
        approximation sign instead of asserting false numerical equality.
        """
        parts: list[str] = []
        for index, operand in enumerate(self.operands):
            if index:
                parts.append(self.operator)
            parts.append(operand.display)
        parts.append(
            "=" if isclose(
                self.exact_result, float(self.result_display),
                rel_tol=1e-12, abs_tol=1e-12,
            ) else r"\approx"
        )
        parts.append(self.result_display)
        equation = MathTex(*parts, font_size=font_size, color=TEXT_PRIMARY)
        equation[-1].set_color(result_color or ACCENT.light)
        for index in range(1, len(parts) - 2, 2):
            equation[index].set_color(TEXT_SECONDARY)
        equation[-2].set_color(TEXT_SECONDARY)
        return equation

    def operand_term(self, equation: MathTex, index: int):
        """Return the submobject for operand ``index`` inside a built equation."""
        if index < 0 or index >= len(self.operands):
            raise IndexError("operand index out of range")
        return equation[2 * index]

    def result_term(self, equation: MathTex):
        """Return the submobject for the result inside a built equation."""
        return equation[-1]

    def build_interpretation(self, *, font_size: float = 22, color=None) -> Text | None:
        """Build the interpretation label, or return ``None`` when there is none."""
        if self.interpretation is None:
            return None
        kwargs = {"font_size": font_size, "color": color or TEXT_SECONDARY}
        return Text(self.interpretation, **kwargs)
