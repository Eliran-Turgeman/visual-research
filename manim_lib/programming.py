"""Stable visual primitives for explaining software state and execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    Circle,
    Rectangle,
    RoundedRectangle,
    Text,
    VGroup,
)

from .theme import (
    ACCENT,
    DANGER,
    NEUTRAL,
    PRIMARY,
    SPACING,
    STROKES,
    SUCCESS,
    SURFACE,
    SURFACE_ELEVATED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


STATUS_COLORS = {
    "neutral": NEUTRAL.base,
    "pending": NEUTRAL.light,
    "active": ACCENT.base,
    "running": PRIMARY.base,
    "success": SUCCESS.base,
    "complete": SUCCESS.base,
    "failed": DANGER.base,
    "error": DANGER.base,
    "blocked": DANGER.dim,
}


def _positive(value: float, name: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return float(value)


def _status(value: str) -> str:
    if value not in STATUS_COLORS:
        raise ValueError(f"status must be one of: {', '.join(STATUS_COLORS)}")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _fit(mobject: Text, *, width: float, height: float) -> Text:
    factor = min(
        1.0,
        width / mobject.width if mobject.width else 1.0,
        height / mobject.height if mobject.height else 1.0,
    )
    if factor < 1:
        mobject.scale(factor)
    return mobject


def _replacement_text(
    current: Text,
    value: str,
    *,
    font_size: float,
    width: float,
    height: float,
    color,
) -> Text:
    replacement = Text(value, font_size=font_size, color=color)
    _fit(replacement, width=width, height=height)
    replacement.move_to(current)
    return replacement


class CodeLine(VGroup):
    """One addressable line in a :class:`CodeBlock`."""

    def __init__(
        self,
        number: int,
        source: str,
        *,
        width: float,
        height: float,
        number_width: float,
        font_size: float,
        font: str,
    ) -> None:
        super().__init__()
        self.number = number
        self.source = source
        self.background = Rectangle(
            width=width,
            height=height,
            stroke_width=0,
            fill_opacity=0,
        )
        self.number_label = Text(
            str(number), font=font, font_size=font_size * 0.72, color=TEXT_MUTED
        )
        self.code_label = Text(
            source if source else " ", font=font, font_size=font_size, color=TEXT_PRIMARY
        )
        _fit(
            self.code_label,
            width=width - number_width - 3 * SPACING.xs,
            height=height * 0.62,
        )
        self.number_label.move_to(self.background.get_left() + RIGHT * (number_width / 2))
        self.code_label.next_to(
            self.background.get_left() + RIGHT * number_width,
            RIGHT,
            buff=SPACING.xs,
        ).align_to(self.background, LEFT)
        self.code_label.shift(RIGHT * (number_width + SPACING.xs))
        self.add(self.background, self.number_label, self.code_label)


class CodeBlock(VGroup):
    """A service-free code listing with stable line objects and execution focus.

    Lines are available in order through :attr:`lines` and by one-based source
    number through :meth:`line`. The highlight object is created once and moved
    in place by :meth:`focus_line`, including through ``block.animate``.
    """

    def __init__(
        self,
        code: str | Sequence[str],
        *,
        width: float = 6.4,
        line_height: float = 0.48,
        font_size: float = 22,
        font: str = "Consolas",
        padding: float = SPACING.sm,
    ) -> None:
        width = _positive(width, "width")
        line_height = _positive(line_height, "line_height")
        padding = _positive(padding, "padding")
        source_lines = code.splitlines() if isinstance(code, str) else list(code)
        if not source_lines:
            raise ValueError("code must contain at least one line")
        if not all(isinstance(line, str) for line in source_lines):
            raise TypeError("all code lines must be strings")
        super().__init__()
        self.current_line: int | None = None
        self._line_height = line_height
        digits = len(str(len(source_lines)))
        number_width = max(0.38, digits * font_size * 0.017)
        inner_width = width - 2 * padding
        if inner_width <= number_width + 2 * SPACING.xs:
            raise ValueError("width is too small for code content")
        height = len(source_lines) * line_height + 2 * padding
        self.panel = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.14,
            fill_color=SURFACE,
            fill_opacity=0.98,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.normal.width,
        )
        self.execution_highlight = RoundedRectangle(
            width=inner_width,
            height=line_height * 0.88,
            corner_radius=0.07,
            fill_color=ACCENT.base,
            fill_opacity=0,
            stroke_color=ACCENT.light,
            stroke_width=0,
        )
        self.lines = [
            CodeLine(
                index,
                source,
                width=inner_width,
                height=line_height,
                number_width=number_width,
                font_size=font_size,
                font=font,
            )
            for index, source in enumerate(source_lines, 1)
        ]
        line_group = VGroup(*self.lines).arrange(DOWN, buff=0)
        line_group.move_to(self.panel)
        self.execution_highlight.move_to(self.lines[0])
        self.add(self.panel, self.execution_highlight, *self.lines)

    def line(self, number: int) -> CodeLine:
        """Return a stable line object by one-based source number."""
        if type(number) is not int or not 1 <= number <= len(self.lines):
            raise IndexError("line number out of range")
        return self.lines[number - 1]

    def focus_line(self, number: int) -> "CodeBlock":
        """Move the execution highlight to ``number`` without replacing lines."""
        target = self.line(number)
        self.execution_highlight.move_to(target)
        self.execution_highlight.set_fill(ACCENT.base, opacity=0.18)
        self.execution_highlight.set_stroke(
            ACCENT.light, width=STROKES.normal.width, opacity=0.9
        )
        self.current_line = number
        return self

    def clear_focus(self) -> "CodeBlock":
        """Hide execution focus while retaining the highlight object's identity."""
        self.execution_highlight.set_fill(opacity=0)
        self.execution_highlight.set_stroke(width=0, opacity=0)
        self.current_line = None
        return self


class RecordCell(VGroup):
    """A fixed cell whose text can change without replacing the cell."""

    def __init__(self, value: str, *, width: float, height: float, font_size: float):
        super().__init__()
        self.value = value
        self.box = Rectangle(
            width=width,
            height=height,
            fill_color=SURFACE,
            fill_opacity=0.92,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.hairline.width,
        )
        self.label = Text(value if value else " ", font_size=font_size, color=TEXT_PRIMARY)
        _fit(self.label, width=width - 2 * SPACING.xs, height=height * 0.55)
        self.label.move_to(self.box)
        self.add(self.box, self.label)

    def set_value(self, value: str, *, font_size: float) -> "RecordCell":
        value = _text(value, "cell value")
        replacement = _replacement_text(
            self.label,
            value if value else " ",
            font_size=font_size,
            width=self.box.width - 2 * SPACING.xs,
            height=self.box.height * 0.55,
            color=self.label[0].get_color(),
        )
        self.label.become(replacement)
        self.label.text = value
        self.value = value
        return self


class RecordRow(VGroup):
    """One keyed, stable row in a :class:`RecordTable`."""

    def __init__(
        self,
        key: str,
        values: Mapping[str, str],
        columns: Sequence[str],
        *,
        column_widths: Sequence[float],
        row_height: float,
        font_size: float,
        status: str,
    ) -> None:
        super().__init__()
        self.key = key
        self.status = status
        self.cells = {
            column: RecordCell(
                values[column],
                width=column_widths[index],
                height=row_height,
                font_size=font_size,
            )
            for index, column in enumerate(columns)
        }
        self.cell_group = VGroup(*(self.cells[column] for column in columns)).arrange(
            RIGHT, buff=0
        )
        self.status_dot = Circle(
            radius=min(0.07, row_height * 0.12),
            fill_color=STATUS_COLORS[status],
            fill_opacity=1,
            stroke_width=0,
        )
        self.status_label = Text(
            status, font_size=max(12, font_size * 0.65), color=STATUS_COLORS[status]
        )
        status_group = VGroup(self.status_dot, self.status_label).arrange(
            RIGHT, buff=SPACING.xs
        )
        status_group.next_to(self.cell_group, RIGHT, buff=SPACING.sm)
        self.add(self.cell_group, self.status_dot, self.status_label)


class RecordTable(VGroup):
    """A keyed table whose rows and cells retain identity across updates."""

    def __init__(
        self,
        columns: Sequence[str],
        records: Mapping[str, Mapping[str, object] | Sequence[object]],
        *,
        column_widths: Sequence[float] | None = None,
        row_height: float = 0.52,
        font_size: float = 20,
        status: str = "neutral",
    ) -> None:
        columns = list(columns)
        if not columns or len(set(columns)) != len(columns):
            raise ValueError("columns must be nonempty and unique")
        if not records:
            raise ValueError("records must not be empty")
        row_height = _positive(row_height, "row_height")
        status = _status(status)
        if column_widths is None:
            column_widths = [1.65] * len(columns)
        column_widths = list(column_widths)
        if len(column_widths) != len(columns):
            raise ValueError("column_widths must match columns")
        column_widths = [_positive(width, "column width") for width in column_widths]

        normalized: dict[str, dict[str, str]] = {}
        for key, raw in records.items():
            _text(key, "record key")
            if isinstance(raw, Mapping):
                if set(raw) != set(columns):
                    raise ValueError(f"record {key!r} must contain exactly the declared columns")
                normalized[key] = {
                    column: str(raw[column]) for column in columns
                }
            else:
                values = list(raw)
                if len(values) != len(columns):
                    raise ValueError(f"record {key!r} must match the column count")
                normalized[key] = {
                    column: str(value) for column, value in zip(columns, values)
                }
        super().__init__()
        self.columns = tuple(columns)
        self._font_size = font_size
        self.header_cells = [
            RecordCell(
                column,
                width=column_widths[index],
                height=row_height,
                font_size=font_size,
            )
            for index, column in enumerate(columns)
        ]
        self.header = VGroup(*self.header_cells).arrange(RIGHT, buff=0)
        for cell in self.header_cells:
            cell.box.set_fill(SURFACE_ELEVATED, opacity=1)
            cell.label.set_color(TEXT_SECONDARY)
        self.rows: dict[str, RecordRow] = {
            key: RecordRow(
                key,
                values,
                columns,
                column_widths=column_widths,
                row_height=row_height,
                font_size=font_size,
                status=status,
            )
            for key, values in normalized.items()
        }
        body = VGroup(*self.rows.values()).arrange(DOWN, buff=0, aligned_edge=LEFT)
        body.next_to(self.header, DOWN, buff=0).align_to(self.header, LEFT)
        self.add(self.header, *self.rows.values())

    def update_cell(self, key: str, column: str, value: object) -> "RecordTable":
        """Update exactly one existing cell after validating all references."""
        if key not in self.rows:
            raise KeyError(f"unknown record key: {key!r}")
        if column not in self.columns:
            raise KeyError(f"unknown column: {column!r}")
        text = str(value)
        self.rows[key].cells[column].set_value(text, font_size=self._font_size)
        return self

    def set_status(self, key: str, status: str) -> "RecordTable":
        """Update one row's visible status without changing any row geometry."""
        if key not in self.rows:
            raise KeyError(f"unknown record key: {key!r}")
        status = _status(status)
        row = self.rows[key]
        color = STATUS_COLORS[status]
        replacement = _replacement_text(
            row.status_label,
            status,
            font_size=max(12, self._font_size * 0.65),
            width=max(row.status_label.width, 0.8 * row.status_label.height),
            height=row.status_label.height,
            color=color,
        )
        replacement.move_to(row.status_label, aligned_edge=LEFT)
        row.status_dot.set_fill(color, opacity=1)
        row.status_label.become(replacement)
        row.status_label.text = status
        row.status = status
        return self


class QueueItem(VGroup):
    """One identity-stable item in a :class:`QueueLane`."""

    def __init__(
        self,
        key: str,
        label: str,
        *,
        status: str,
        width: float,
        height: float,
        font_size: float,
    ) -> None:
        super().__init__()
        self.key = key
        self.label_text = label
        self.status = status
        color = STATUS_COLORS[status]
        self.box = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=min(0.11, height * 0.2),
            fill_color=color if status != "neutral" else SURFACE_ELEVATED,
            fill_opacity=0.24 if status != "neutral" else 0.98,
            stroke_color=color,
            stroke_width=STROKES.normal.width,
        )
        self.label = Text(label if label else " ", font_size=font_size, color=TEXT_PRIMARY)
        _fit(self.label, width=width - 2 * SPACING.xs, height=height * 0.48)
        self.label.move_to(self.box).shift(DOWN * height * 0.08)
        self.status_label = Text(
            status, font_size=max(11, font_size * 0.48), color=color
        )
        _fit(self.status_label, width=width - 2 * SPACING.xs, height=height * 0.2)
        self.status_label.next_to(self.box.get_top(), DOWN, buff=height * 0.08)
        self.add(self.box, self.label, self.status_label)

    def set_status(self, status: str) -> "QueueItem":
        status = _status(status)
        color = STATUS_COLORS[status]
        replacement = _replacement_text(
            self.status_label,
            status,
            font_size=self.status_label.font_size,
            width=self.box.width - 2 * SPACING.xs,
            height=self.box.height * 0.2,
            color=color,
        )
        replacement.move_to(self.status_label)
        self.box.set_stroke(color, width=STROKES.normal.width)
        self.box.set_fill(
            color if status != "neutral" else SURFACE_ELEVATED,
            opacity=0.24 if status != "neutral" else 0.98,
        )
        self.status_label.become(replacement)
        self.status_label.text = status
        self.status = status
        return self


class QueueLane(VGroup):
    """An ordered queue with explicit enqueue/dequeue and stable item identity."""

    def __init__(
        self,
        items: Sequence[tuple[str, str]] = (),
        *,
        width: float = 7.0,
        height: float = 1.1,
        item_width: float = 1.15,
        item_height: float = 0.72,
        buff: float = SPACING.xs,
        font_size: float = 20,
    ) -> None:
        width = _positive(width, "width")
        height = _positive(height, "height")
        item_width = _positive(item_width, "item_width")
        item_height = _positive(item_height, "item_height")
        if item_height >= height:
            raise ValueError("item_height must be smaller than lane height")
        super().__init__()
        self._item_width = item_width
        self._item_height = item_height
        self._buff = _positive(buff, "buff")
        self._font_size = font_size
        self.lane = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.14,
            fill_color=SURFACE,
            fill_opacity=0.78,
            stroke_color=NEUTRAL.dim,
            stroke_width=STROKES.normal.width,
        )
        self.order: list[str] = []
        self.items: dict[str, QueueItem] = {}
        self.add(self.lane)
        for key, label in items:
            self.enqueue(key, label)

    def _first_center_x(self, item_width: float) -> float:
        return self.lane.get_left()[0] + SPACING.sm * self.lane.height / 1.1 + item_width / 2

    def enqueue(
        self, key: str, label: str, *, status: str = "pending"
    ) -> QueueItem:
        """Append one item; existing item geometry is left untouched."""
        _text(key, "queue key")
        label = _text(label, "queue label")
        if key in self.items:
            raise ValueError(f"queue key already exists: {key!r}")
        status = _status(status)
        item = QueueItem(
            key,
            label,
            status=status,
            width=self._item_width,
            height=self._item_height,
            font_size=self._font_size,
        )
        scale = self.lane.height / 1.1
        item.scale(scale)
        if self.order:
            item.next_to(self.items[self.order[-1]], RIGHT, buff=self._buff * scale)
        else:
            item.move_to(
                (
                    self._first_center_x(item.box.width),
                    self.lane.get_center()[1],
                    self.lane.get_center()[2],
                )
            )
        if item.get_right()[0] > self.lane.get_right()[0] - SPACING.xs * scale:
            raise ValueError("queue lane has no room for another item")
        self.order.append(key)
        self.items[key] = item
        self.add(item)
        return item

    def dequeue(self) -> QueueItem:
        """Remove the front item and shift the remaining queue forward."""
        if not self.order:
            raise IndexError("cannot dequeue an empty queue")
        key = self.order[0]
        item = self.items[key]
        remaining = self.order[1:]
        if remaining:
            target_x = self._first_center_x(self.items[remaining[0]].box.width)
            delta = target_x - self.items[remaining[0]].get_center()[0]
            for remaining_key in remaining:
                self.items[remaining_key].shift(RIGHT * delta)
        self.order.pop(0)
        del self.items[key]
        self.remove(item)
        return item

    def set_status(self, key: str, status: str) -> "QueueLane":
        """Change one item's state without changing queue order or positions."""
        if key not in self.items:
            raise KeyError(f"unknown queue key: {key!r}")
        status = _status(status)
        self.items[key].set_status(status)
        return self


__all__ = [
    "CodeBlock",
    "CodeLine",
    "QueueItem",
    "QueueLane",
    "RecordCell",
    "RecordRow",
    "RecordTable",
    "STATUS_COLORS",
]
