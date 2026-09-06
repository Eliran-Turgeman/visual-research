"""Layout, invariant, and storyboard-consistency tests for the DFlash visual episode."""

import importlib.util
import sys
from pathlib import Path

import pytest

# Use importlib to explicitly load from the dflash_visual directory,
# avoiding collisions with the ddtree_dflash scene module that other
# tests also add to sys.path.
_DFLASH_DIR = Path(__file__).resolve().parent.parent / "examples" / "dflash_visual"

def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Temporarily prepend the directory for intra-package imports
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod

_storyboard = _load_module("dflash_storyboard", _DFLASH_DIR / "storyboard.py")
_scene_mod = _load_module("dflash_scene", _DFLASH_DIR / "scene.py")

BEATS = _storyboard.BEATS
BEAT_COUNT = _storyboard.BEAT_COUNT
BONUS_TOKEN = _storyboard.BONUS_TOKEN
CANDIDATE_PATH = _storyboard.CANDIDATE_PATH
Q1 = _storyboard.Q1
Q2 = _storyboard.Q2
Q3 = _storyboard.Q3
VERIFICATION_RESULT = _storyboard.VERIFICATION_RESULT

CONTEXT_TOKENS = _scene_mod.CONTEXT_TOKENS
RIBBON_POSITION = _scene_mod.RIBBON_POSITION
RIBBON_Y = _scene_mod.RIBBON_Y
SLOT_COUNT = _scene_mod.SLOT_COUNT
SLOT_HEIGHT = _scene_mod.SLOT_HEIGHT
SLOT_WIDTH = _scene_mod.SLOT_WIDTH
DFlashVisualExplainer = _scene_mod.DFlashVisualExplainer

from manim_lib.layout import within_safe_frame, assert_no_overlaps, bounding_box
from manim_lib.tokens import TokenBox, TokenState
from manim_lib.probability import ProbabilityDistribution
from manim import VGroup, RIGHT, RoundedRectangle, Text


# ---------------------------------------------------------------
# Storyboard consistency
# ---------------------------------------------------------------

class TestStoryboardConsistency:

    def test_beat_count_matches_tuple_length(self):
        assert BEAT_COUNT == len(BEATS)

    def test_beat_indices_are_sequential(self):
        for i, beat in enumerate(BEATS):
            assert beat.index == i, f"Beat at position {i} has index {beat.index}"

    def test_all_beats_have_narration(self):
        for beat in BEATS:
            assert beat.narration.strip(), f"Beat {beat.index} has empty narration"

    def test_all_beats_have_valid_duration_ranges(self):
        for beat in BEATS:
            lo, hi = beat.duration_range
            assert 0 < lo <= hi, f"Beat {beat.index} has invalid duration range ({lo}, {hi})"

    def test_candidate_path_matches_marginals(self):
        """Candidate tokens must be present in the corresponding marginal."""
        marginals = [Q1, Q2, Q3]
        for i, tok in enumerate(CANDIDATE_PATH):
            assert tok in marginals[i], (
                f"Candidate '{tok}' not in Q{i+1}: {list(marginals[i].keys())}"
            )

    def test_verification_result_length_matches_candidate_path(self):
        assert len(VERIFICATION_RESULT) == len(CANDIDATE_PATH)

    def test_slot_count_matches_marginals(self):
        assert SLOT_COUNT == len([Q1, Q2, Q3])


# ---------------------------------------------------------------
# Toy numerical invariants
# ---------------------------------------------------------------

class TestToyNumerics:

    def test_marginals_sum_to_one(self):
        for name, dist in [("Q1", Q1), ("Q2", Q2), ("Q3", Q3)]:
            total = sum(dist.values())
            assert abs(total - 1.0) < 1e-6, f"{name} sums to {total}, not 1.0"

    def test_all_marginal_values_positive(self):
        for name, dist in [("Q1", Q1), ("Q2", Q2), ("Q3", Q3)]:
            for tok, val in dist.items():
                assert val > 0, f"{name}['{tok}'] = {val} is not positive"

    def test_candidate_path_is_most_likely(self):
        """The candidate path should be the argmax per position."""
        marginals = [Q1, Q2, Q3]
        for i, (tok, dist) in enumerate(zip(CANDIDATE_PATH, marginals)):
            best = max(dist, key=dist.get)
            assert tok == best, (
                f"Position {i}: candidate '{tok}' is not argmax "
                f"(expected '{best}' with p={dist[best]:.2f})"
            )


# ---------------------------------------------------------------
# Layout: ribbon geometry
# ---------------------------------------------------------------

class TestRibbonLayout:

    def _build_ribbon(self):
        """Build a representative ribbon matching the scene's layout."""
        items = []
        for tok in CONTEXT_TOKENS:
            box = RoundedRectangle(
                width=SLOT_WIDTH, height=SLOT_HEIGHT, corner_radius=0.06,
            )
            txt = Text(tok, font_size=24).move_to(box)
            items.append(VGroup(box, txt))
        for _ in range(SLOT_COUNT):
            box = RoundedRectangle(
                width=SLOT_WIDTH, height=SLOT_HEIGHT, corner_radius=0.06,
            )
            items.append(VGroup(box))
        group = VGroup(*items).arrange(RIGHT, buff=0.1)
        group.move_to(RIBBON_POSITION)
        return group, items

    def test_ribbon_fits_in_safe_frame(self):
        group, _ = self._build_ribbon()
        assert within_safe_frame(group), "Ribbon extends outside safe frame"

    def test_ribbon_items_do_not_overlap(self):
        _, items = self._build_ribbon()
        assert_no_overlaps(items, labels=[
            *(f"ctx_{tok}" for tok in CONTEXT_TOKENS),
            *(f"slot_{i}" for i in range(SLOT_COUNT)),
        ])


# ---------------------------------------------------------------
# Layout: probability distributions
# ---------------------------------------------------------------

class TestDistributionLayout:

    def _build_dists(self):
        dist_entries = [
            {"the": ("the", 0.55), "a": ("a", 0.35), "this": ("this", 0.10)},
            {"model": ("model", 0.60), "system": ("system", 0.30), "code": ("code", 0.10)},
            {"works": ("works", 0.52), "runs": ("runs", 0.28), "fails": ("fails", 0.20)},
        ]
        dists = []
        for entries in dist_entries:
            d = ProbabilityDistribution(
                entries, max_bar_width=1.0, bar_height=0.20,
                font_size=16,
            )
            dists.append(d)
        group = VGroup(*dists).arrange(RIGHT, buff=1.2, aligned_edge=True)
        group.move_to((0, -1.8, 0))
        return dists, group

    def test_distributions_fit_in_safe_frame(self):
        _, group = self._build_dists()
        assert within_safe_frame(group), "Distributions extend outside safe frame"

    def test_distribution_columns_do_not_overlap(self):
        dists, _ = self._build_dists()
        assert_no_overlaps(
            dists,
            labels=[f"dist_q{i+1}" for i in range(3)],
        )


# ---------------------------------------------------------------
# Beat count matches scene sections
# ---------------------------------------------------------------

class TestSceneBeatAlignment:

    def test_scene_has_ten_beat_methods(self):
        """The scene should have one method per beat."""
        actual = [m for m in dir(DFlashVisualExplainer) if m.startswith("_beat_")]
        assert len(actual) == BEAT_COUNT, (
            f"Scene has {len(actual)} beat methods but storyboard has {BEAT_COUNT} beats"
        )
