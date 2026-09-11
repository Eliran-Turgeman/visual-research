"""Geometry contracts for probability mass, including completed animations."""

import numpy as np
import pytest
from manim import LEFT, RIGHT, UP, Text, linear

from manim_lib.probability import DistributionEntry, ProbabilityDistribution


@pytest.mark.parametrize("value", [0.0, 1e-8, 0.001, 0.01, 0.25, 1.0])
def test_probability_bar_encodes_its_value_without_minimum_width(value):
    entry = DistributionEntry("key", "token", value, max_bar_width=2.0)
    assert entry.bar.width == pytest.approx(2.0 * value, abs=1e-14)
    assert entry.bar.get_left()[0] == pytest.approx(entry.track.get_left()[0])
    # An outline would make a collapsed/tiny bar look like nonzero mass.
    assert entry.bar.get_stroke_width() == 0
    assert np.isfinite(entry.bar.get_all_points()).all()
    if value > 0:
        assert float(entry.value_label.text) > 0


def test_positive_bar_ratios_remain_faithful_at_small_values():
    dist = ProbabilityDistribution(
        {"small": ("small", 0.0001), "large": ("large", 0.001)}
    )
    assert dist.entries["large"].bar.width / dist.entries["small"].bar.width == (
        pytest.approx(10)
    )


@pytest.mark.parametrize("values", [(0.2, 0.3), (0.8, 0.9)])
def test_probability_entries_are_not_implicitly_normalized(values):
    dist = ProbabilityDistribution(
        {str(i): (str(i), value) for i, value in enumerate(values)}
    )
    for entry, value in zip(dist.entries.values(), values):
        assert entry.value == value
        assert entry.bar.width / entry.track.width == pytest.approx(value)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), -float("inf")])
def test_invalid_probabilities_fail_before_mutating_an_entry(value):
    with pytest.raises(ValueError, match="between 0 and 1"):
        DistributionEntry("key", "token", value)
    entry = DistributionEntry("key", "token", 0.4)
    points = entry.get_all_points().copy()
    with pytest.raises(ValueError, match="between 0 and 1"):
        entry.set_value(value)
    assert entry.value == 0.4
    assert entry.value_label.text == "0.40"
    assert entry.get_all_points() == pytest.approx(points)


@pytest.mark.parametrize("dimension", ["max_bar_width", "bar_height"])
@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_probability_dimensions_must_be_positive_and_finite(dimension, value):
    with pytest.raises(ValueError, match="positive and finite"):
        DistributionEntry("key", "token", 0.5, **{dimension: value})


def test_varying_token_and_value_labels_share_track_and_value_columns():
    dist = ProbabilityDistribution(
        {"a": ("a", 0.5), "long": ("much longer token", 0.00001), "z": ("z", 0)}
    ).scale(0.7).shift(RIGHT + UP)
    entries = list(dist.entries.values())
    baseline = entries[0].track.get_left()[0]
    value_left = entries[0].value_label.get_left()[0]
    for entry in entries:
        assert entry.track.get_left()[0] == pytest.approx(baseline)
        assert entry.bar.get_left()[0] == pytest.approx(baseline)
        assert entry.token_label.get_right()[0] < baseline
        assert entry.value_label.get_left()[0] == pytest.approx(value_left)
    for above, below in zip(entries, entries[1:]):
        assert above.get_bottom()[1] > below.get_top()[1]


def test_legacy_local_baseline_adjustment_is_idempotent():
    dist = ProbabilityDistribution({"a": ("a", 0), "long": ("longer token", 0.2)})
    baseline = max(e.token_label.get_right()[0] for e in dist.entries.values()) + 0.25

    def align_locally():
        for entry in dist.entries.values():
            entry.track.shift(RIGHT * (baseline - entry.track.get_left()[0]))
            entry.bar.move_to(entry.track).align_to(entry.track, LEFT)
            entry.value_label.next_to(entry.track, RIGHT, buff=0.12)

    align_locally()
    points = dist.get_all_points().copy()
    align_locally()
    assert dist.get_all_points() == pytest.approx(points)
    for entry in dist.entries.values():
        assert entry.bar.width == pytest.approx(entry.track.width * entry.value)
        assert entry.bar.get_left()[0] == pytest.approx(baseline)


def test_value_updates_preserve_identity_position_scale_and_highlight():
    dist = ProbabilityDistribution({"a": ("a", 0), "b": ("long token", 0.5)})
    dist.scale(0.6).shift(UP + RIGHT)
    entry = dist.entries["a"].highlight("#ff0000")
    objects = tuple(entry.submobjects)
    track_points = entry.track.points.copy()
    token_points = entry.token_label.get_all_points().copy()
    other_points = dist.entries["b"].get_all_points().copy()
    value_left = entry.value_label.get_left()[0]
    value_color = entry.value_label[0].get_color()
    entry.value_label.set_opacity(0.6)
    for value in (0.00001, 0.3, 1.0, 0.0, 0.999999):
        assert entry.set_value(value) is entry
        assert tuple(entry.submobjects) == objects
        assert dist.entries["a"] is entry
        assert entry.value == value
        assert float(entry.value_label.text) == pytest.approx(value, abs=1e-10)
        assert entry.bar.width == pytest.approx(entry.track.width * value)
        assert entry.bar.get_left()[0] == pytest.approx(entry.track.get_left()[0])
        assert entry.bar.get_fill_color().to_hex() == "#FF0000"
        assert entry.bar.get_stroke_width() == 0
        assert entry.value_label.get_left()[0] == pytest.approx(value_left)
        expected_label = Text(entry.value_label.text, font_size=20).scale(0.6)
        assert entry.value_label.width == pytest.approx(expected_label.width)
        assert entry.value_label.height == pytest.approx(expected_label.height)
        visible_glyphs = [
            glyph for glyph in entry.value_label.family_members_with_points()
            if glyph.get_fill_opacity() > 0
        ]
        assert visible_glyphs
        for glyph in visible_glyphs:
            assert glyph.get_color() == value_color
            assert glyph.get_fill_opacity() == pytest.approx(0.6)
        assert entry.track.points == pytest.approx(track_points)
        assert entry.token_label.get_all_points() == pytest.approx(token_points)
        assert dist.entries["b"].get_all_points() == pytest.approx(other_points)


def test_animated_updates_finish_with_correct_geometry_and_semantics():
    entry = DistributionEntry("key", "token", 0).scale(0.8).shift(RIGHT)
    objects = tuple(entry.submobjects)
    baseline = entry.track.get_left()[0]
    value_color = entry.value_label[0].get_color()
    for target in (0.8, 0, 0.0001, 0.4):
        start = entry.value
        animation = entry.animate(rate_func=linear).set_value(target).build()
        animation.begin()
        animation.interpolate(0.5)
        assert entry.bar.width == pytest.approx(
            entry.track.width * (start + target) / 2
        )
        assert entry.bar.get_left()[0] == pytest.approx(baseline)
        animation.finish()
        assert tuple(entry.submobjects) == objects
        assert entry.value == target
        assert float(entry.value_label.text) == pytest.approx(target)
        assert entry.bar.width == pytest.approx(entry.track.width * target)
        assert entry.bar.get_left()[0] == pytest.approx(baseline)
        visible_glyphs = [
            glyph for glyph in entry.value_label.family_members_with_points()
            if glyph.get_fill_opacity() > 0
        ]
        assert visible_glyphs
        for glyph in visible_glyphs:
            assert glyph.get_color() == value_color
            assert glyph.get_fill_opacity() == 1
