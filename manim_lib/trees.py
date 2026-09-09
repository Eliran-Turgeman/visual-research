"""Small stable-layout tree primitives."""

from manim import RIGHT, Circle, Line, Text, VGroup

from .theme import (
    ACCENT,
    NEUTRAL,
    PRIMARY,
    STROKES,
    SURFACE_ELEVATED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

# Fraction of the circle's diameter a label may occupy before it is scaled
# down to stay inside the circle. Leaves a visible ring of padding.
_LABEL_FIT_FRACTION = 0.82


class TreeNode(VGroup):
    """A labeled circular tree node with an optional score.

    The label is automatically scaled down, preserving its aspect ratio, so it
    never escapes the circle regardless of token length. The score, when
    given, is placed outside the circle in a caller-chosen direction so it can
    be moved out of the way of neighboring nodes in a crowded layout.
    """

    def __init__(
        self,
        label: str,
        *,
        score: float | str | None = None,
        radius: float = 0.32,
        font_size: float = 24,
        score_direction=RIGHT,
        score_buff: float = 0.08,
        score_font_size: float = 16,
    ) -> None:
        super().__init__()
        self.radius = radius
        self.halo = Circle(radius=radius + 0.055).set_stroke(
            NEUTRAL.dim, width=5.5, opacity=0.16
        ).set_fill(opacity=0)
        self.circle = Circle(radius=radius).set_stroke(
            NEUTRAL.base, width=STROKES.normal.width
        ).set_fill(SURFACE_ELEVATED, opacity=0.98)
        self.inner_ring = Circle(radius=radius * 0.84).set_stroke(
            NEUTRAL.light, width=STROKES.hairline.width, opacity=0.18
        ).set_fill(opacity=0)
        self.label = Text(label, font_size=font_size, color=TEXT_PRIMARY)
        self._fit_label_to_circle()
        self.label.move_to(self.circle)
        self.score_label = None
        self.add(self.halo, self.circle, self.inner_ring, self.label)
        if score is not None:
            self.set_score(
                score,
                direction=score_direction,
                buff=score_buff,
                font_size=score_font_size,
            )

    def _fit_label_to_circle(self) -> None:
        """Scale ``self.label`` down so it stays within the node circle."""
        available = 2 * self.radius * _LABEL_FIT_FRACTION
        width_factor = available / self.label.width if self.label.width else 1.0
        height_factor = available / self.label.height if self.label.height else 1.0
        factor = min(1.0, width_factor, height_factor)
        if factor < 1.0:
            self.label.scale(factor)

    def set_score(
        self,
        score: float | str,
        *,
        direction=RIGHT,
        buff: float = 0.08,
        font_size: float = 16,
    ) -> Text:
        """Create the score label at ``direction`` outside the circle and
        attach it immediately.

        Use this when the label should simply appear alongside the node
        (for example inside the node's own constructor, or a plain
        ``FadeIn``). When a *different* mobject should visibly turn into
        the score (an equation result flying to its node), build the target
        with :meth:`prepare_score` instead, animate into it, and finish with
        :meth:`attach_score` -- attaching a label before its arrival
        animation plays makes it pop into view early and can leave a stray
        duplicate behind once the animation finishes.

        Passing a different ``direction`` for crowded siblings (for example
        ``DOWN`` instead of the default ``RIGHT``) is the supported way to
        avoid a score label colliding with a neighboring node.
        """
        label = self.prepare_score(
            score, direction=direction, buff=buff, font_size=font_size
        )
        self.attach_score(label)
        return label

    def prepare_score(
        self,
        score: float | str,
        *,
        direction=RIGHT,
        buff: float = 0.08,
        font_size: float = 16,
    ) -> Text:
        """Build the score label's final look and position without
        attaching it to this node or the scene.

        The returned :class:`~manim.mobject.text.text_mobject.Text` is a
        pure blueprint: use it as a ``Transform``/``TransformFromCopy``
        target so some other mobject (an equation result, say) can
        visibly become the score. Once that animation finishes, adopt its
        actual on-screen result with :meth:`attach_score` so the node ends
        up owning exactly one score label, never a second stray copy.
        """
        value = f"{score:.2f}" if isinstance(score, float) else str(score)
        return Text(value, font_size=font_size, color=TEXT_SECONDARY).next_to(
            self.circle, direction=direction, buff=buff
        )

    def attach_score(self, label: Text) -> Text:
        """Adopt ``label`` as this node's official, persistent score label.

        ``label`` should already carry its final on-screen appearance --
        typically the mobject an animation produced by transforming into a
        target built with :meth:`prepare_score`. Any previous score label
        is dropped so the node always shows at most one.
        """
        if self.score_label is not None:
            self.remove(self.score_label)
        self.score_label = label
        self.add(label)
        return label

    def highlight(self, color=ACCENT.base) -> "TreeNode":
        """Highlight this node in place."""
        self.halo.set_stroke(color, width=7, opacity=0.22)
        self.circle.set_stroke(color, width=STROKES.heavy.width).set_fill(
            color, opacity=0.24
        )
        self.inner_ring.set_stroke(color, opacity=0.5)
        return self

    def reset_highlight(self) -> "TreeNode":
        """Restore the neutral node style."""
        self.halo.set_stroke(NEUTRAL.dim, width=5.5, opacity=0.16)
        self.circle.set_stroke(
            NEUTRAL.base, width=STROKES.normal.width
        ).set_fill(SURFACE_ELEVATED, opacity=0.98)
        self.inner_ring.set_stroke(NEUTRAL.light, opacity=0.18)
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
            color=NEUTRAL.dim,
            stroke_width=STROKES.normal.width,
        )
        self.edges[key] = edge
        self.add_to_back(edge)
        return edge

    def highlight_path(self, keys: list[str], color=PRIMARY.base) -> "StableTree":
        """Highlight nodes and edges along an ordered path."""
        for key in keys:
            self.nodes[key].highlight(color)
        for pair in zip(keys, keys[1:]):
            self.edges[pair].set_color(color).set_stroke(
                width=STROKES.heavy.width
            )
        return self
