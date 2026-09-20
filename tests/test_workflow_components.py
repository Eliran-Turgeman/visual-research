import numpy as np
import pytest
from manim import Circle, Square, Text

from manim_lib.workflow import SystemNode, animate_parallel_evaluation


def _finish(animation):
    animation.begin()
    animation.interpolate(1)
    animation.finish()


def test_system_node_exposes_stable_boundary_anchors_after_transform():
    node = SystemNode("Policy service")
    input_id = id(node.input_anchor)
    output_id = id(node.output_anchor)
    assert node.input_point[0] == pytest.approx(node.body.get_left()[0])
    assert node.output_point[0] == pytest.approx(node.body.get_right()[0])
    node.scale(1.5).shift(np.array([2.0, -1.0, 0]))
    assert id(node.input_anchor) == input_id
    assert id(node.output_anchor) == output_id
    assert node.input_point[0] == pytest.approx(node.body.get_left()[0])
    assert node.output_point[0] == pytest.approx(node.body.get_right()[0])


def test_system_node_requires_distinct_valid_anchor_directions():
    with pytest.raises(ValueError):
        SystemNode("bad", input_direction=np.zeros(3))
    with pytest.raises(ValueError):
        SystemNode("bad", input_direction=np.array([1, 0, 0]), output_direction=np.array([2, 0, 0]))


def test_parallel_evaluation_preserves_objects_and_completes_at_results():
    sources = {"fraud": Circle().shift(np.array([-2, 1, 0])), "risk": Circle().shift(np.array([-2, -1, 0]))}
    questions = {"fraud": Text("fraud?"), "risk": Text("risk?")}
    results = {"fraud": Square().shift(np.array([2, 1, 0])), "risk": Square().shift(np.array([2, -1, 0]))}
    source_id = id(sources["fraud"])
    endpoints = {
        key: (value.get_center().copy(), value.width, value.height)
        for key, value in results.items()
    }
    animation = animate_parallel_evaluation(sources, questions, results)
    assert animation.lag_ratio == 0
    _finish(animation)
    for key, result in results.items():
        center, width, height = endpoints[key]
        assert result.get_center() == pytest.approx(center)
        assert result.width == pytest.approx(width)
        assert result.height == pytest.approx(height)
    assert id(sources["fraud"]) == source_id


def test_parallel_evaluation_never_infers_or_accepts_missing_mapping():
    with pytest.raises(ValueError, match="match exactly"):
        animate_parallel_evaluation(
            {"a": Circle(), "b": Circle()},
            {"a": Text("?")},
            {"a": Square(), "b": Square()},
        )


def test_parallel_evaluation_rejects_duplicate_and_ambiguous_mappings():
    with pytest.raises(ValueError, match="duplicate"):
        animate_parallel_evaluation(
            [("a", Circle()), ("a", Circle())],
            [("a", Text("?"))],
            [("a", Square())],
        )
    shared = Circle()
    with pytest.raises(ValueError, match="ambiguous"):
        animate_parallel_evaluation(
            {"a": shared, "b": shared},
            {"a": Text("a?"), "b": Text("b?")},
            {"a": Square(), "b": Square()},
        )


def test_parallel_evaluation_rejects_non_mobjects():
    with pytest.raises(TypeError):
        animate_parallel_evaluation(
            {"a": Circle()},
            {"a": "not a mobject"},
            {"a": Square()},
        )
