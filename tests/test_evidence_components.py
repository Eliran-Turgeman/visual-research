"""Evidence semantics and exact-geometry tests."""

import pytest
from manim import RIGHT, linear

from manim_lib.evidence import CalibrationPlot, ComparisonScale, MetricCard
from manim_lib.layout import contains


def finish(animation):
    animation.begin()
    animation.interpolate(1)
    animation.finish()


def test_metric_card_retains_visible_fields_and_identity_on_update():
    card = MetricCard("Latency at p95", 12.4, "ms", "measured")
    objects = tuple(card.submobjects)
    labels = (card.value_label, card.unit_label, card.label, card.provenance_label)
    card.update(value=9.8, unit="ms", label="End-to-end p95", provenance="vendor_reported")
    assert tuple(card.submobjects) == objects
    assert labels == (card.value_label, card.unit_label, card.label, card.provenance_label)
    assert card.value == 9.8
    assert card.unit == "ms"
    assert card.metric_label == "End-to-end p95"
    assert card.provenance == "vendor_reported"
    assert card.provenance_label.text == "VENDOR-REPORTED"
    for label in labels:
        assert contains(card.panel, label)


def test_metric_card_validates_entire_update_before_mutation_and_animates():
    card = MetricCard("Throughput", 10, "req/s", "toy").scale(0.7).shift(RIGHT)
    points = card.get_all_points().copy()
    with pytest.raises(ValueError):
        card.update(value=20, provenance="anecdotal")
    assert card.value == 10
    assert card.provenance == "toy"
    assert card.get_all_points() == pytest.approx(points)
    value_label = card.value_label
    finish(card.animate(rate_func=linear).set_value(20).build())
    assert card.value_label is value_label
    assert card.value == 20
    assert card.value_label.text == "20"


@pytest.mark.parametrize("value", [0, 1, 2.5, 10])
def test_comparison_scale_uses_exact_shared_zero_based_geometry(value):
    scale = ComparisonScale(
        {
            "a": ("System A", value, "measured"),
            "b": ("System B", 10, "vendor_reported"),
        },
        unit="ms",
        maximum=10,
        track_width=4,
    )
    entry = scale.entries["a"]
    assert entry.bar.width == pytest.approx(entry.track.width * value / 10)
    assert entry.bar.get_left()[0] == pytest.approx(entry.track.get_left()[0])
    assert scale.zero_label.text == "0ms"
    assert scale.maximum_label.text == "10ms"
    assert entry.value_label.text.endswith("ms")
    assert entry.provenance_label.text == "MEASURED"


def test_comparison_ratio_is_honest_and_updates_preserve_unrelated_entries():
    scale = ComparisonScale(
        {
            "small": ("Small", 2, "toy"),
            "large": ("Large", 8, "measured"),
        },
        unit="items/s",
        maximum=10,
    ).scale(0.75).shift(RIGHT)
    small = scale.entries["small"]
    large = scale.entries["large"]
    assert large.bar.width / small.bar.width == pytest.approx(4)
    unrelated = large.get_all_points().copy()
    objects = tuple(small.submobjects)
    scale.set_value("small", 5)
    assert scale.entries["small"] is small
    assert tuple(small.submobjects) == objects
    assert small.bar.width == pytest.approx(small.track.width * 0.5)
    assert large.get_all_points() == pytest.approx(unrelated)


@pytest.mark.parametrize("value", [-1, 11, float("nan"), float("inf")])
def test_comparison_invalid_update_does_not_mutate(value):
    scale = ComparisonScale({"a": ("A", 5, "toy")}, unit="%", maximum=10)
    entry = scale.entries["a"]
    points = entry.get_all_points().copy()
    with pytest.raises(ValueError):
        scale.set_value("a", value)
    assert entry.value == 5
    assert entry.get_all_points() == pytest.approx(points)


def test_comparison_completed_animation_has_exact_geometry():
    scale = ComparisonScale({"a": ("A", 2, "toy")}, unit="x", maximum=10)
    entry = scale.entries["a"]
    finish(scale.animate(rate_func=linear).set_value("a", 7).build())
    assert scale.entries["a"] is entry
    assert entry.value == 7
    assert entry.bar.width == pytest.approx(entry.track.width * 0.7)
    assert entry.bar.get_left()[0] == pytest.approx(entry.track.get_left()[0])


def test_calibration_plot_has_distinct_axes_and_visible_ideal_reference():
    plot = CalibrationPlot({"low": (0.2, 0.3), "high": (0.8, 0.75)})
    assert plot.x_label.text == "Confidence"
    assert plot.y_label.text.replace(" ", "") == "Observedaccuracy"
    assert "notper-examplecorrectness" in plot.note.text.replace(" ", "")
    assert len(plot.ideal_reference.get_all_points()) > 0
    assert plot.ideal_reference.get_start() == pytest.approx(plot.axes.c2p(0, 0))
    assert plot.ideal_reference.get_end() == pytest.approx(plot.axes.c2p(1, 1))
    for point in plot.bins.values():
        assert point.dot.get_center() == pytest.approx(
            plot.axes.c2p(point.confidence, point.accuracy)
        )


def test_calibration_updates_preserve_point_identity_after_transform():
    plot = CalibrationPlot({"bin": (0.25, 0.4)}).scale(0.6).shift(RIGHT)
    point = plot.bins["bin"]
    dot = point.dot
    finish(plot.animate.update_point("bin", 0.9, 0.7).build())
    assert plot.bins["bin"] is point
    assert point.dot is dot
    assert point.confidence == 0.9
    assert point.accuracy == 0.7
    assert dot.get_center() == pytest.approx(plot.axes.c2p(0.9, 0.7))


@pytest.mark.parametrize(
    "confidence,accuracy",
    [(-0.1, 0.5), (1.1, 0.5), (0.5, -0.1), (0.5, 1.1), (float("nan"), 0.5)],
)
def test_calibration_invalid_values_fail_before_mutation(confidence, accuracy):
    plot = CalibrationPlot({"bin": (0.25, 0.4)})
    point = plot.bins["bin"]
    position = point.dot.get_center().copy()
    with pytest.raises(ValueError, match="between 0 and 1|finite"):
        plot.update_point("bin", confidence, accuracy)
    assert point.confidence == 0.25
    assert point.accuracy == 0.4
    assert point.dot.get_center() == pytest.approx(position)
