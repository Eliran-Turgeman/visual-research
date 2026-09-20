import pytest
from manim import RIGHT, linear

from manim_lib.layout import contains
from manim_lib.state import ContentPolicy, StateField, StructuredState


def test_structured_state_is_ordered_and_rejects_unknown_updates():
    state = StructuredState(
        {
            "status": ("Status", "ready", "str"),
            "attempt": ("Attempt", 1, "int"),
        }
    )
    assert list(state.fields) == ["status", "attempt"]
    points = state.get_all_points().copy()
    with pytest.raises(KeyError, match="missing"):
        state.set_value("missing", "value")
    assert state.get_all_points() == pytest.approx(points)


def test_state_update_preserves_identity_and_unrelated_geometry_after_transform():
    state = StructuredState(
        {
            "status": ("Status", "ready", "str"),
            "attempt": ("Attempt", 1, "int"),
        }
    ).scale(0.65).shift(RIGHT * 2)
    row = state["status"]
    objects = tuple(row.submobjects)
    background_points = row.background.get_all_points().copy()
    other_points = state["attempt"].get_all_points().copy()
    value_center = row.value_label.get_center().copy()

    assert state.set_value("status", "running") is state
    assert state["status"] is row
    assert tuple(row.submobjects) == objects
    assert row.value == "running"
    assert row.value_label.text == "running"
    assert row.value_label.get_center() == pytest.approx(value_center)
    assert row.background.get_all_points() == pytest.approx(background_points)
    assert state["attempt"].get_all_points() == pytest.approx(other_points)


def test_state_field_long_content_respects_fit_and_wrap_policy():
    fit = StateField(
        "long",
        "A very long field label",
        "an extraordinarily long value that must remain contained",
        "long-custom-type",
        width=3.4,
        content_policy=ContentPolicy.FIT,
    )
    wrapped = StateField(
        "long",
        "Label",
        "a long value that should wrap explicitly",
        width=3.4,
        content_policy=ContentPolicy.WRAP,
    )
    for row in (fit, wrapped):
        assert contains(row.background, row.label)
        assert contains(row.background, row.value_label)
        assert contains(row.badge, row.type_badge)
    assert "\n" not in fit.value_label.original_text
    assert "\n" in wrapped.value_label.original_text
    with pytest.raises(ValueError, match="fit.*wrap"):
        StateField("x", "X", "v", content_policy="truncate")


def test_add_field_keeps_existing_rows_fixed_and_matches_transformed_geometry():
    state = StructuredState({"a": ("A", 1), "b": ("B", 2)}, field_buff=0.2)
    state.scale(0.5).shift(RIGHT)
    existing = {key: row.get_all_points().copy() for key, row in state.fields.items()}
    previous = state["b"]
    added = state.add_field("c", "C", 3, "int")
    assert list(state.fields) == ["a", "b", "c"]
    for key, points in existing.items():
        assert state[key].get_all_points() == pytest.approx(points)
    assert added.background.height == pytest.approx(previous.background.height)
    assert previous.get_bottom()[1] - added.get_top()[1] == pytest.approx(0.1)
    with pytest.raises(ValueError, match="duplicate"):
        state.add_field("c", "duplicate", 4)


def test_highlight_and_animated_value_update_preserve_semantics():
    state = StructuredState({"phase": ("Phase", "idle", "str")})
    row = state.highlight_field("phase")
    assert row.highlighted
    objects = tuple(row.submobjects)
    animation = row.animate(rate_func=linear).set_value("done").build()
    animation.begin()
    animation.interpolate(1)
    animation.finish()
    assert row.value == "done"
    assert row.value_label.text == "done"
    assert tuple(row.submobjects) == objects
