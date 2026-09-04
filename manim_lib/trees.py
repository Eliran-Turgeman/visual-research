"""Small stable-layout tree primitives."""

from manim import BLUE, GRAY, YELLOW, Circle, Line, Text, VGroup


class TreeNode(VGroup):
    """A labeled circular tree node with an optional score."""

    def __init__(
        self,
        label: str,
        *,
        score: float | str | None = None,
        radius: float = 0.32,
    ) -> None:
        super().__init__()
        self.circle = Circle(radius=radius, color=GRAY).set_fill(GRAY, opacity=0.1)
        self.label = Text(label, font_size=24).move_to(self.circle)
        self.score_label = None
        self.add(self.circle, self.label)
        if score is not None:
            value = f"{score:.2f}" if isinstance(score, float) else str(score)
            self.score_label = Text(value, font_size=16).next_to(
                self.circle, direction=(1, 0, 0), buff=0.08
            )
            self.add(self.score_label)

    def highlight(self, color=YELLOW) -> "TreeNode":
        """Highlight this node in place."""
        self.circle.set_stroke(color, width=4).set_fill(color, opacity=0.2)
        return self

    def reset_highlight(self) -> "TreeNode":
        """Restore the neutral node style."""
        self.circle.set_stroke(GRAY, width=2).set_fill(GRAY, opacity=0.1)
        return self


class StableTree(VGroup):
    """A tree whose caller-selected node positions remain stable as it expands."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: dict[str, TreeNode] = {}
        self.edges: dict[tuple[str, str], Line] = {}

    def add_node(self, key: str, node: TreeNode, position) -> TreeNode:
        """Add a uniquely keyed node at an explicit stable position."""
        if key in self.nodes:
            raise ValueError(f"Tree node key already exists: {key}")
        node.move_to(position)
        self.nodes[key] = node
        self.add(node)
        return node

    def connect(self, parent: str, child: str) -> Line:
        """Connect two existing nodes with an edge rendered behind them."""
        if parent not in self.nodes or child not in self.nodes:
            raise KeyError("Both parent and child must exist before connecting them")
        key = (parent, child)
        if key in self.edges:
            raise ValueError(f"Tree edge already exists: {parent} -> {child}")
        edge = Line(
            self.nodes[parent].circle.get_bottom(),
            self.nodes[child].circle.get_top(),
            color=GRAY,
        )
        self.edges[key] = edge
        self.add_to_back(edge)
        return edge

    def highlight_path(self, keys: list[str], color=BLUE) -> "StableTree":
        """Highlight nodes and edges along an ordered path."""
        for key in keys:
            self.nodes[key].highlight(color)
        for pair in zip(keys, keys[1:]):
            self.edges[pair].set_color(color).set_stroke(width=4)
        return self
