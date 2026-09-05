"""Matrix and tensor-region visualization helpers."""

from collections.abc import Iterable

from manim import BLUE, DOWN, LEFT, RIGHT, UP, Rectangle, Text, VGroup


class LabeledMatrix(VGroup):
    """A fixed-cell matrix with optional row and column labels."""

    def __init__(
        self,
        values: list[list[object]],
        *,
        row_labels: list[str] | None = None,
        column_labels: list[str] | None = None,
        cell_width: float = 0.75,
        cell_height: float = 0.55,
    ) -> None:
        if not values or not values[0]:
            raise ValueError("Matrix values must not be empty")
        columns = len(values[0])
        if any(len(row) != columns for row in values):
            raise ValueError("All matrix rows must have equal length")
        if row_labels is not None and len(row_labels) != len(values):
            raise ValueError("row_labels must match the matrix row count")
        if column_labels is not None and len(column_labels) != columns:
            raise ValueError("column_labels must match the matrix column count")

        super().__init__()
        self.cells: list[list[VGroup]] = []
        self.row_label_mobjects: list[Text] = []
        self.column_label_mobjects: list[Text] = []
        for row_index, row in enumerate(values):
            cells = []
            for column_index, value in enumerate(row):
                box = Rectangle(width=cell_width, height=cell_height)
                text = Text(str(value), font_size=22).move_to(box)
                cell = VGroup(box, text).move_to(
                    (
                        column_index * cell_width,
                        -row_index * cell_height,
                        0,
                    )
                )
                cells.append(cell)
                self.add(cell)
            self.cells.append(cells)

        if row_labels:
            for label, row in zip(row_labels, self.cells):
                text = Text(label, font_size=20).next_to(row[0], LEFT, buff=0.18)
                self.row_label_mobjects.append(text)
                self.add(text)
        if column_labels:
            for label, cell in zip(column_labels, self.cells[0]):
                text = Text(label, font_size=20).next_to(cell, UP, buff=0.18)
                self.column_label_mobjects.append(text)
                self.add(text)
        self.center()

    def row_group(self, row: int) -> VGroup:
        """Return a VGroup of one row's cells, for a step-by-step reveal."""
        return VGroup(*self.cells[row])

    def highlight_cells(
        self,
        coordinates: Iterable[tuple[int, int]],
        *,
        color=BLUE,
        opacity: float = 0.35,
    ) -> VGroup:
        """Return overlays for selected cells; add or animate the returned group."""
        overlays = VGroup()
        for row, column in coordinates:
            overlays.add(
                self.cells[row][column][0]
                .copy()
                .set_stroke(color, width=3)
                .set_fill(color, opacity=opacity)
            )
        return overlays

    def highlight_row(self, row: int, **kwargs) -> VGroup:
        """Return overlays covering one row."""
        return self.highlight_cells(
            ((row, column) for column in range(len(self.cells[row]))), **kwargs
        )

    def highlight_column(self, column: int, **kwargs) -> VGroup:
        """Return overlays covering one column."""
        return self.highlight_cells(
            ((row, column) for row in range(len(self.cells))), **kwargs
        )

    def shape_label(self, text: str, *, side=RIGHT) -> Text:
        """Create a shape annotation positioned beside the matrix."""
        return Text(text, font_size=20).next_to(self, side, buff=0.25)
