"""Tests for the pure-Python DDTree best-first construction used by the
ddtree_dflash example scene.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "ddtree_dflash"))

from algorithm import Q1, Q2, Q3, best_first_prefixes  # noqa: E402


def test_toy_prefix_scores_and_order_match_worked_example():
    prefixes = best_first_prefixes([Q1, Q2, Q3], budget=7)
    keys = [prefix.key for prefix in prefixes]
    assert keys == [
        "the",
        "a",
        "the-model",
        "a-model",
        "the-model-works",
        "the-system",
        "a-model-works",
    ]
    masses = {prefix.key: prefix.mass for prefix in prefixes}
    assert masses["the"] == pytest.approx(0.55)
    assert masses["a"] == pytest.approx(0.35)
    assert masses["the-model"] == pytest.approx(0.55 * 0.60)
    assert masses["a-model"] == pytest.approx(0.35 * 0.60)
    assert masses["the-model-works"] == pytest.approx(0.55 * 0.60 * 0.52)
    assert masses["the-system"] == pytest.approx(0.55 * 0.30)
    assert masses["a-model-works"] == pytest.approx(0.35 * 0.60 * 0.52)


def test_pop_order_is_non_increasing_mass():
    prefixes = best_first_prefixes([Q1, Q2, Q3], budget=7)
    masses = [prefix.mass for prefix in prefixes]
    assert masses == sorted(masses, reverse=True)


def test_result_is_prefix_closed():
    prefixes = best_first_prefixes([Q1, Q2, Q3], budget=7)
    keys = {prefix.key for prefix in prefixes}
    keys.add("root")
    for prefix in prefixes:
        assert prefix.parent in keys


def test_budget_must_be_positive():
    with pytest.raises(ValueError):
        best_first_prefixes([Q1, Q2, Q3], budget=0)


def test_marginals_must_be_non_empty():
    with pytest.raises(ValueError):
        best_first_prefixes([], budget=1)


def test_path_identity_is_unambiguous_even_when_tokens_contain_hyphens():
    # The scene's "-"-joined display key is inherently ambiguous once a
    # token itself contains "-": path ("a-b", "c") and path ("a", "b-c")
    # both join to the string "a-b-c". These two toy marginals are chosen
    # so both prefixes are popped within the same small budget, proving the
    # collision is real, not theoretical.
    hyphen_q1 = {"a-b": 0.9, "a": 0.5, "z": 0.01}
    hyphen_q2 = {"b-c": 0.9, "c": 0.5, "d": 0.01}

    prefixes = best_first_prefixes([hyphen_q1, hyphen_q2], budget=5)

    keys = [prefix.key for prefix in prefixes]
    paths = [prefix.path for prefix in prefixes]

    assert keys.count("a-b-c") == 2, "expected the two distinct lineages to collide on key"
    # Despite the display-string collision, the internal path identity must
    # stay unique per prefix: this is what the algorithm now uses for its
    # own bookkeeping (sibling/child expansion), so it never confuses one
    # lineage's mass or parent with another's.
    assert len(paths) == len(set(paths))
    assert ("a-b", "c") in paths
    assert ("a", "b-c") in paths

    by_path = {prefix.path: prefix for prefix in prefixes}
    collided_from_ab = by_path[("a-b", "c")]
    collided_from_a = by_path[("a", "b-c")]
    assert collided_from_ab.parent == "a-b"
    assert collided_from_a.parent == "a"
    assert collided_from_ab.mass == pytest.approx(0.9 * 0.5)
    assert collided_from_a.mass == pytest.approx(0.5 * 0.9)


def test_budget_larger_than_reachable_tree_stops_early():
    # Only 3 tokens per depth over 3 depths -> at most 3+9+27 = 39 nodes are
    # reachable at all, but the heap frontier is far smaller than that; a
    # very large budget must not raise, and should simply return everything
    # the heap can offer without duplicating keys.
    prefixes = best_first_prefixes([Q1, Q2, Q3], budget=1000)
    keys = [prefix.key for prefix in prefixes]
    assert len(keys) == len(set(keys))
    assert len(prefixes) > 7
