"""Layout, invariant, and storyboard-consistency tests for the DFlash visual episode."""

import importlib.util
import itertools
import math
import shutil
import sys
import uuid
from fractions import Fraction
from pathlib import Path

import pytest

# Use importlib to explicitly load from the dflash_visual directory,
# avoiding collisions with the ddtree_dflash scene module that other
# tests also add to sys.path.
_DFLASH_DIR = Path(__file__).resolve().parent.parent / "examples" / "dflash_visual"

def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    saved_storyboard = sys.modules.pop("storyboard", None)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
        sys.modules.pop("storyboard", None)
        if saved_storyboard is not None:
            sys.modules["storyboard"] = saved_storyboard
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

from manim_lib.layout import within_safe_frame, assert_no_overlaps
from manim_lib.tokens import TokenState
from manim import VGroup, Text, tempconfig


@pytest.fixture(scope="module", autouse=True)
def local_media():
    """No paid narration, shared caches, or files outside this worktree."""
    media = Path(__file__).resolve().parents[1] / "media" / "dflash-tests" / uuid.uuid4().hex
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MANIM_TTS_PROVIDER", "none")
        with tempconfig({
            "media_dir": str(media),
            "quality": "low_quality",
            "dry_run": True,
            "skip_animations": True,
            "disable_caching": True,
            "progress_bar": "none",
        }):
            yield media
    shutil.rmtree(media, ignore_errors=True)


@pytest.fixture(scope="module")
def constructed_scene(local_media):
    scene = DFlashVisualExplainer()
    scene.review_timeline_path = local_media / "timeline.json"
    scene.render()
    return scene


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
        """Independently enumerate all paths using exact decimal probabilities."""
        marginals = (Q1, Q2, Q3)
        weights = {
            path: math.prod(Fraction(str(q[t])) for q, t in zip(marginals, path))
            for path in itertools.product(*(q.keys() for q in marginals))
        }
        assert sum(weights.values()) == 1
        assert weights[CANDIDATE_PATH] == Fraction(429, 2500)
        assert all(weights[CANDIDATE_PATH] > weight
                   for path, weight in weights.items() if path != CANDIDATE_PATH)

    def test_target_rows_are_causal_normalized_toy_distributions(self):
        for i, chosen in enumerate(_storyboard.TARGET_CHOICES):
            dist = _storyboard.TARGET_CONDITIONALS[CANDIDATE_PATH[:i]]
            assert sum(Fraction(str(p)) for p in dist.values()) == 1
            assert all(0 < p <= 1 for p in dist.values())
            assert all(dist[chosen] > p for token, p in dist.items() if token != chosen)


class TestPrefixVerification:

    @pytest.mark.parametrize("length", range(5))
    def test_every_match_pattern_uses_cumulative_prefix(self, length):
        """An independent product-of-indicators oracle catches suffix acceptance."""
        proposals = tuple(f"draft{i}" for i in range(length))
        for matches in itertools.product((False, True), repeat=length):
            targets = tuple(
                proposals[i] if match else f"target{i}"
                for i, match in enumerate(matches)
            ) + ("extra",)
            result = _storyboard.verify_greedy(proposals, targets)
            prefix_length = sum(
                math.prod(matches[:i + 1]) for i in range(length)
            )
            assert result.accepted_count == prefix_length
            assert result.accepted_mask == tuple(i < prefix_length for i in range(length))
            assert result.bonus_token == targets[prefix_length]
            assert result.committed_tokens == proposals[:prefix_length] + (targets[prefix_length],)
            assert len(result.committed_tokens) >= 1

    def test_committed_tokens_match_an_independent_sequential_target(self):
        # A prefix-dependent target; enumerate drafts rather than assuming agreement.
        def target(prefix):
            return "b" if prefix.count("b") % 2 == 0 else "a"

        for proposals in itertools.product(("a", "b"), repeat=4):
            choices = tuple(target(proposals[:i]) for i in range(5))
            result = _storyboard.verify_greedy(proposals, choices)
            baseline = ()
            for _ in result.committed_tokens:
                baseline += (target(baseline),)
            assert result.committed_tokens == baseline

    @pytest.mark.parametrize("choices", [(), ("a",), ("a", "b", "c")])
    def test_requires_n_plus_one_target_choices(self, choices):
        with pytest.raises(ValueError, match="one target choice"):
            _storyboard.verify_greedy(("a",), choices)

    def test_toy_later_match_is_not_accepted(self):
        assert tuple(a == b for a, b in zip(
            CANDIDATE_PATH, _storyboard.TARGET_CHOICES,
        )) == (True, False, True)
        assert _storyboard.VERIFICATION.accepted_mask == (True, False, False)
        assert _storyboard.VERIFICATION.committed_tokens == ("the", "system")


# ---------------------------------------------------------------
# Layout: ribbon geometry
# ---------------------------------------------------------------

class TestRibbonLayout:

    def _build_ribbon(self):
        scene = DFlashVisualExplainer()
        items = [scene._make_committed_token(tok) for tok in CONTEXT_TOKENS]
        items.extend(scene._make_slot() for _ in range(SLOT_COUNT))
        group = scene._arrange_ribbon(items)
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
        return DFlashVisualExplainer()._make_distributions()

    def test_distributions_fit_in_safe_frame(self):
        _, group = self._build_dists()
        assert within_safe_frame(group), "Distributions extend outside safe frame"

    def test_distribution_columns_do_not_overlap(self):
        dists, _ = self._build_dists()
        assert_no_overlaps(
            dists,
            labels=[f"dist_q{i+1}" for i in range(3)],
        )

    def test_constructed_entries_display_storyboard_values(self, constructed_scene):
        for dist, q in zip(constructed_scene._dists, _storyboard.DRAFT_MARGINALS):
            assert tuple(dist.entries) == tuple(q)
            for token, probability in q.items():
                entry = dist.entries[token]
                assert entry.token_label.text == token
                assert entry.value_label.text == f"{probability:.2f}"
                assert entry.value == probability
                assert entry.bar.width == pytest.approx(probability)

    def test_visual_builder_uses_supplied_episode_data(self, monkeypatch):
        changed = ({"new": 0.75, "other": 0.25}, {"token": 1.0})
        monkeypatch.setattr(_scene_mod, "DRAFT_MARGINALS", changed)
        dists, _ = self._build_dists()
        assert len(dists) == 2
        assert dists[0].entries["new"].value_label.text == "0.75"
        assert dists[1].entries["token"].bar.width == pytest.approx(1.0)


class TestConstructedVerification:

    def test_comparison_row_and_marks_are_derived_from_target(self, constructed_scene):
        scene = constructed_scene
        assert tuple(t.label.text for t in scene._target_tokens) == _storyboard.TARGET_CHOICES
        assert tuple(m.text for m in scene._check_marks) == ("match", "STOP", "unused")
        assert "temperature=0" in scene._regime_label.text

    def test_rejected_suffix_never_joins_committed_ribbon(self, constructed_scene):
        scene = constructed_scene
        assert tuple(t.token for t in scene._rejected_suffix) == ("model", "works")
        assert all(t.state is TokenState.REJECTED for t in scene._rejected_suffix)
        assert all(t not in scene.get_mobject_family_members() for t in scene._rejected_suffix)
        assert tuple(t.label.text for t in scene.ribbon_items) == CONTEXT_TOKENS + ("the", "system")
        assert all(t.state is TokenState.ACCEPTED for t in scene._committed_new)
        assert all(t.box.get_stroke_color().to_hex() == _scene_mod.SUCCESS.base.upper()
                   for t in scene._committed_new)
        assert tuple(t.token for t in scene._baseline_tokens) == ("the", "system")

    def test_bonus_replaces_first_miss_not_end_of_proposals(self, constructed_scene):
        scene = constructed_scene
        assert scene._bonus_group.token == "system"
        assert scene._bonus_group.get_center() == pytest.approx(scene._candidates[1].get_center())
        assert scene._bonus_group.get_x() < scene._candidates[-1].get_x()

    @pytest.mark.parametrize("targets,expected", [
        (("a", "model", "works", "well"), ("a",)),
        (("the", "model", "fails", "well"), ("the", "model", "fails")),
        (("the", "model", "works", "well"), ("the", "model", "works", "well")),
    ])
    def test_constructed_boundary_cases(self, local_media, targets, expected):
        scene = DFlashVisualExplainer()
        scene.setup()
        scene.verification = _storyboard.verify_greedy(CANDIDATE_PATH, targets)
        scene.ribbon_items = [scene._make_committed_token(t) for t in CONTEXT_TOKENS]
        scene._candidates = [scene._make_candidate_token(t) for t in CANDIDATE_PATH]
        scene._arrange_ribbon(scene.ribbon_items + scene._candidates)
        scene.add(*scene.ribbon_items, *scene._candidates)
        scene._target_tokens = scene._make_target_row()
        scene._target_row_label = Text("target")
        scene._check_marks = []
        scene.add(*scene._target_tokens)
        scene._beat_8_discard_suffix()
        scene._beat_9_commit()
        assert tuple(t.token for t in scene.ribbon_items) == CONTEXT_TOKENS + expected
        assert all(t not in scene.get_mobject_family_members() for t in scene._rejected_suffix)
        boundary = scene.verification.accepted_count
        if boundary < SLOT_COUNT:
            assert scene._bonus_group.get_center() == pytest.approx(
                scene._candidates[boundary].get_center(),
            )
        else:
            assert scene._bonus_group.get_left()[0] > scene._candidates[-1].get_right()[0]
        assert within_safe_frame(VGroup(*scene.ribbon_items))
        assert_no_overlaps(scene.ribbon_items)

    def test_verification_layout_fits_and_does_not_overlap(self, constructed_scene):
        scene = constructed_scene
        groups = [
            *scene._target_tokens, scene._target_row_label,
            *scene._check_marks, scene._regime_label, scene._bonus_label,
            *scene.ribbon_items,
        ]
        assert within_safe_frame(VGroup(*groups))
        assert_no_overlaps(groups)

    def test_baseline_layout_fits_and_does_not_overlap(self, constructed_scene):
        scene = constructed_scene
        groups = [
            *scene._baseline_tokens, *scene._equivalence_labels,
            scene._regime_label, scene._bonus_label, *scene.ribbon_items,
        ]
        assert within_safe_frame(VGroup(*groups))
        assert_no_overlaps(groups)

    def test_final_frame_has_no_discarded_mechanism_fragments(self, constructed_scene):
        scene = constructed_scene
        expected = {
            leaf
            for mob in [
                *scene.ribbon_items, scene._bonus_label,
                scene._regime_label, scene._bridge,
            ]
            for leaf in mob.family_members_with_points()
        }
        actual = {
            leaf for mob in scene.mobjects
            for leaf in mob.family_members_with_points()
        }
        assert actual == expected


# ---------------------------------------------------------------
# Beat count matches scene sections
# ---------------------------------------------------------------

class TestSceneBeatAlignment:

    def test_scene_has_one_method_per_beat(self):
        """The scene should have one method per beat."""
        actual = [m for m in dir(DFlashVisualExplainer) if m.startswith("_beat_")]
        assert len(actual) == BEAT_COUNT, (
            f"Scene has {len(actual)} beat methods but storyboard has {BEAT_COUNT} beats"
        )

    def test_constructed_narration_matches_storyboard(self, constructed_scene):
        assert [block["text"] for block in constructed_scene._review_blocks] == [
            beat.narration for beat in BEATS
        ]

    def test_setup_calls_parent_once(self, monkeypatch):
        calls = []
        original = _scene_mod.NarratedScene.setup

        def record_setup(scene):
            calls.append(scene)
            original(scene)

        monkeypatch.setattr(_scene_mod.NarratedScene, "setup", record_setup)
        scene = DFlashVisualExplainer()
        scene.setup()
        assert calls == [scene]
