"""Geometry and identity contracts for programming visualization primitives."""

import pytest
from manim import RIGHT, linear

from manim_lib.layout import contains
from manim_lib.programming import CodeBlock, QueueLane, RecordTable


def finish(animation):
    animation.begin()
    animation.interpolate(1)
    animation.finish()


def test_code_block_lines_are_addressable_stable_and_contained():
    block = CodeBlock(["def very_long_function_name(argument):", "    return argument"])
    identities = tuple(block.lines)
    assert block.line(1) is block.lines[0]
    assert block.line(2).source == "    return argument"
    assert all(contains(block.panel, line) for line in block.lines)
    block.focus_line(2)
    assert tuple(block.lines) == identities
    assert block.current_line == 2
    assert block.execution_highlight.get_center() == pytest.approx(block.line(2).get_center())
    with pytest.raises(IndexError):
        block.focus_line(0)
    assert block.current_line == 2


def test_code_focus_survives_scale_shift_and_completed_animation():
    block = CodeBlock("load()\nexecute()\nstore()").scale(0.7).shift(RIGHT)
    lines = tuple(block.lines)
    highlight = block.execution_highlight
    finish(block.animate(rate_func=linear).focus_line(3).build())
    assert tuple(block.lines) == lines
    assert block.execution_highlight is highlight
    assert block.current_line == 3
    assert highlight.get_center() == pytest.approx(block.line(3).get_center())


def test_record_table_updates_one_cell_and_preserves_all_identities():
    table = RecordTable(
        ["name", "result"],
        {"a": {"name": "alpha", "result": "pending"}, "b": {"name": "beta", "result": "7"}},
    )
    rows = dict(table.rows)
    cells = {key: dict(row.cells) for key, row in table.rows.items()}
    unrelated = table.rows["b"].get_all_points().copy()
    table.update_cell("a", "result", "a much longer completed result")
    assert table.rows == rows
    assert table.rows["a"].cells == cells["a"]
    assert table.rows["a"].cells["result"].value == "a much longer completed result"
    assert contains(
        table.rows["a"].cells["result"].box,
        table.rows["a"].cells["result"].label,
    )
    assert table.rows["b"].get_all_points() == pytest.approx(unrelated)


def test_record_table_status_validation_precedes_mutation_and_animation_finishes():
    table = RecordTable(["value"], {"a": ["1"], "b": ["2"]})
    row = table.rows["a"]
    status_label = row.status_label
    other = table.rows["b"].get_all_points().copy()
    before = row.get_all_points().copy()
    with pytest.raises(ValueError):
        table.set_status("a", "invented")
    assert row.get_all_points() == pytest.approx(before)
    finish(table.animate.set_status("a", "success").build())
    assert table.rows["a"] is row
    assert row.status_label is status_label
    assert row.status == "success"
    assert row.status_label.text == "success"
    assert table.rows["b"].get_all_points() == pytest.approx(other)


def test_record_cell_completed_animation_preserves_cell_identity():
    table = RecordTable(["value"], {"a": ["before"]}).scale(0.75).shift(RIGHT)
    row = table.rows["a"]
    cell = row.cells["value"]
    label = cell.label
    finish(table.animate.update_cell("a", "value", "after").build())
    assert table.rows["a"] is row
    assert row.cells["value"] is cell
    assert cell.label is label
    assert cell.value == "after"
    assert contains(cell.box, cell.label)


def test_queue_enqueue_only_appends_and_status_does_not_rearrange():
    queue = QueueLane([("a", "compile"), ("b", "test")])
    prefix = [queue.items[key] for key in queue.order]
    points = [item.get_all_points().copy() for item in prefix]
    appended = queue.enqueue("c", "a label long enough to require fitting")
    assert queue.order == ["a", "b", "c"]
    assert [queue.items[key] for key in ("a", "b")] == prefix
    for item, original in zip(prefix, points):
        assert item.get_all_points() == pytest.approx(original)
    assert appended.get_left()[0] > queue.items["b"].get_right()[0]
    assert contains(appended.box, appended.label)
    positions = {key: queue.items[key].get_center().copy() for key in queue.order}
    queue.set_status("b", "running")
    assert queue.order == ["a", "b", "c"]
    for key, position in positions.items():
        assert queue.items[key].get_center() == pytest.approx(position)


def test_queue_dequeue_is_the_only_operation_that_compacts_existing_items():
    queue = QueueLane([("a", "A"), ("b", "B"), ("c", "C")])
    b = queue.items["b"]
    c = queue.items["c"]
    b_x = b.get_center()[0]
    c_x = c.get_center()[0]
    removed = queue.dequeue()
    assert removed.key == "a"
    assert queue.order == ["b", "c"]
    assert queue.items["b"] is b and queue.items["c"] is c
    shift = b.get_center()[0] - b_x
    assert shift < 0
    assert c.get_center()[0] - c_x == pytest.approx(shift)


def test_queue_invalid_operations_do_not_mutate():
    queue = QueueLane([("a", "A")])
    points = queue.get_all_points().copy()
    with pytest.raises(ValueError):
        queue.enqueue("a", "duplicate")
    with pytest.raises(ValueError):
        queue.set_status("a", "unknown")
    assert queue.order == ["a"]
    assert queue.get_all_points() == pytest.approx(points)
    empty = QueueLane()
    with pytest.raises(IndexError):
        empty.dequeue()


def test_queue_works_after_scale_and_shift():
    queue = QueueLane([("a", "A")]).scale(0.6).shift(RIGHT * 2)
    original = queue.items["a"].get_all_points().copy()
    second = queue.enqueue("b", "B")
    assert queue.items["a"].get_all_points() == pytest.approx(original)
    assert second.get_left()[0] - queue.items["a"].get_right()[0] == pytest.approx(
        0.15 * 0.6
    )
    assert second.box.height == pytest.approx(queue.items["a"].box.height)


def test_queue_completed_status_animation_preserves_item_identity_and_position():
    queue = QueueLane([("a", "A"), ("b", "B")])
    item = queue.items["b"]
    position = item.get_center().copy()
    finish(queue.animate.set_status("b", "success").build())
    assert queue.items["b"] is item
    assert item.status == "success"
    assert item.get_center() == pytest.approx(position)
    assert queue.order == ["a", "b"]
