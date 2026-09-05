import pytest
from manim import DOWN, RIGHT

from manim_lib import (
    CandidateToken,
    EquationSteps,
    EventTimeline,
    LabeledMatrix,
    StableTree,
    TokenBox,
    TokenSequence,
    TokenState,
    TreeNode,
    contains,
)


def test_token_components_preserve_state_and_order():
    sequence = TokenSequence("a", "b")
    appended = sequence.append_token("c", state=TokenState.SPECULATIVE)
    assert [box.token for box in sequence.token_boxes] == ["a", "b", "c"]
    assert appended.state is TokenState.SPECULATIVE
    assert CandidateToken("x", 0.5).probability_label.text == "50%"
    assert TokenBox("x").state is TokenState.NEUTRAL


def test_stable_tree_requires_existing_unique_nodes():
    tree = StableTree()
    tree.add_node("root", TreeNode("r"), (0, 1, 0))
    tree.add_node("child", TreeNode("c", score=0.8), (0, 0, 0))
    edge = tree.connect("root", "child")
    original_position = tree.nodes["root"].get_center().copy()
    tree.highlight_path(["root", "child"])
    assert tree.nodes["root"].get_center() == pytest.approx(original_position)
    assert edge is tree.edges[("root", "child")]
    with pytest.raises(ValueError):
        tree.add_node("root", TreeNode("duplicate"), (1, 1, 0))


def test_tree_node_constrains_long_label_within_circle():
    node = TreeNode("system", radius=0.32)
    assert contains(node.circle, node.label, padding=0.0)
    # A long token at a small radius must actually shrink, not merely fit by
    # accident, so this also guards against a no-op containment check.
    unscaled_width_at_font_24 = 1.1
    assert node.label.width < unscaled_width_at_font_24


def test_tree_node_short_label_is_not_shrunk_unnecessarily():
    node = TreeNode("a", radius=0.46)
    default_width = TreeNode("a", radius=10.0).label.width
    assert node.label.width == pytest.approx(default_width)


def test_tree_node_score_placement_is_configurable_and_backward_compatible():
    default_node = TreeNode("model", score=0.6, radius=0.4)
    assert default_node.score_label is not None
    # Default placement keeps the historical behavior: to the right.
    assert default_node.score_label.get_center()[0] > default_node.circle.get_center()[0]

    below_node = TreeNode("model", score=".60", radius=0.4, score_direction=DOWN)
    assert below_node.score_label.get_center()[1] < below_node.circle.get_center()[1]
    assert not contains(below_node.circle, below_node.score_label)


def test_tree_node_set_score_moves_existing_label_in_place():
    node = TreeNode("model", radius=0.4)
    assert node.score_label is None
    first = node.set_score(".60", direction=RIGHT)
    assert first is node.score_label
    node.set_score(".33", direction=DOWN)
    assert node.score_label.text == ".33"
    assert node.score_label.get_center()[1] < node.circle.get_center()[1]


def test_matrix_highlights_and_validates_shape():
    matrix = LabeledMatrix([[1, 2], [3, 4]], row_labels=["a", "b"])
    assert len(matrix.highlight_row(0)) == 2
    assert len(matrix.highlight_column(1)) == 2
    assert matrix.shape_label("2 x 2").text == "2x2"
    with pytest.raises(ValueError):
        LabeledMatrix([[1], [2, 3]])


def test_equation_and_timeline_validation():
    equations = EquationSteps("x+0=x", "x=x")
    assert equations.first is equations.equations[0]
    assert equations.transform(0) is not None
    with pytest.raises(IndexError):
        equations.transform(1)
    timeline = EventTimeline(start=0, end=4)
    timeline.add_event(1, "arrive")
    timeline.add_interval(1, 3, "run")
    assert timeline.point_at(2) == pytest.approx(timeline.axis.get_center())
