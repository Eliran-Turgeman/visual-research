"""Tests for the reusable narrated-computation helper."""

import pytest

from manim_lib import Computation, Operand


def test_computation_autocomputes_product_and_rounds_for_display():
    computation = Computation(
        Operand("the", 0.55, tex=".55"),
        Operand("model", 0.60, tex=".60"),
    )
    assert computation.exact_result == pytest.approx(0.55 * 0.60)
    assert computation.result_display == "0.330"


def test_computation_preserves_exact_result_through_rounding():
    computation = Computation(
        Operand("the-model", 0.33, tex=".330"),
        Operand("works", 0.52, tex=".52"),
    )
    # 0.33 * 0.52 = 0.1716, which must round for display without losing the
    # exact value used by any later arithmetic.
    assert computation.exact_result == pytest.approx(0.1716)
    assert computation.result_display == "0.172"


def test_computation_leading_zero_toggle_matches_toy_convention():
    computation = Computation(
        Operand("the", 0.55, tex=".55"),
        Operand("model", 0.60, tex=".60"),
        leading_zero=False,
    )
    assert computation.result_display == ".330"


def test_computation_requires_at_least_two_operands():
    with pytest.raises(ValueError):
        Computation(Operand("solo", 1.0))


def test_computation_requires_exact_result_for_non_multiply_operator():
    with pytest.raises(ValueError):
        Computation(Operand("a", 1.0), Operand("b", 2.0), operator="+")
    # Providing exact_result explicitly is fine for any operator.
    computation = Computation(
        Operand("a", 1.0), Operand("b", 2.0), operator="+", exact_result=3.0
    )
    assert computation.result_display == "3.000"


def test_build_equation_parts_are_indexable():
    computation = Computation(
        Operand("the", 0.55, tex=".55"),
        Operand("model", 0.60, tex=".60"),
        Operand("works", 0.52, tex=".52"),
    )
    equation = computation.build_equation()
    # n operands, n-1 operators, "=", result -> 2n + 1 parts.
    assert len(equation) == 2 * 3 + 1
    assert computation.operand_term(equation, 0) is equation[0]
    assert computation.operand_term(equation, 2) is equation[4]
    assert computation.result_term(equation) is equation[-1]
    with pytest.raises(IndexError):
        computation.operand_term(equation, 3)


def test_build_interpretation_is_optional():
    without_interpretation = Computation(Operand("a", 1.0), Operand("b", 2.0))
    assert without_interpretation.build_interpretation() is None

    with_interpretation = Computation(
        Operand("a", 1.0),
        Operand("b", 2.0),
        interpretation="a joint mass under Q",
    )
    label = with_interpretation.build_interpretation()
    assert label is not None
    # manim's Text.text getter strips whitespace; compare ignoring spaces.
    assert label.text.replace(" ", "") == "ajointmassunderQ"
