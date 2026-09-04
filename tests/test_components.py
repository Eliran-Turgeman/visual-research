import pytest

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
