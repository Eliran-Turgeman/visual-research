r"""Visual reference for the shared technical-object language.

Render a still while iterating on the design system:

    .\.venv\Scripts\python.exe -m manim render -ql -s \
        examples\style_showcase\scene.py VisualLanguageShowcase
"""

from manim import DOWN, LEFT, RIGHT, UP, Scene, Text, VGroup

from manim_lib import (
    BACKGROUND,
    SAFE_MARGINS,
    SPACING,
    TEXT_SECONDARY,
    TYPOGRAPHY,
    LabeledMatrix,
    ProbabilityDistribution,
    StableTree,
    TokenBox,
    TokenState,
    TreeNode,
    center_group,
    side_by_side,
)


def _caption(text: str) -> Text:
    return Text(
        text,
        font_size=TYPOGRAPHY.caption.font_size,
        color=TEXT_SECONDARY,
    )


class VisualLanguageShowcase(Scene):
    """Display the core primitives in one frame for visual review."""

    def construct(self):
        self.camera.background_color = BACKGROUND

        title = Text(
            "One visual language",
            font_size=TYPOGRAPHY.heading.font_size,
            color=TYPOGRAPHY.heading.color,
        )
        subtitle = Text(
            "stable geometry  •  semantic color  •  focused detail",
            font_size=TYPOGRAPHY.caption.font_size,
            color=TEXT_SECONDARY,
        )
        heading = center_group(title, subtitle, buff=SPACING.xs)

        tokens = VGroup(
            TokenBox("context"),
            TokenBox("draft", state=TokenState.SPECULATIVE),
            TokenBox("accept", state=TokenState.ACCEPTED),
            TokenBox("reject", state=TokenState.REJECTED),
        ).arrange(RIGHT, buff=SPACING.sm)
        token_section = center_group(
            _caption("state stays attached to the object"),
            tokens,
            buff=SPACING.sm,
        )

        distribution = ProbabilityDistribution(
            {
                "model": ("model", 0.58),
                "system": ("system", 0.27),
                "code": ("code", 0.15),
            },
            max_bar_width=1.55,
        )
        distribution.highlight_entry("model")
        probability_section = center_group(
            _caption("stable probability scale"),
            distribution,
            buff=SPACING.sm,
        )

        tree = StableTree()
        tree.add_node("root", TreeNode("root"), (0, 0.65, 0))
        tree.add_node("a", TreeNode("A"), (-0.7, -0.55, 0))
        tree.add_node("b", TreeNode("B"), (0.7, -0.55, 0))
        tree.connect("root", "a")
        tree.connect("root", "b")
        tree.highlight_path(["root", "b"])
        tree_section = center_group(
            _caption("stable structure"),
            tree,
            buff=SPACING.sm,
        )

        matrix = LabeledMatrix(
            [[1, 0, 0], [1, 1, 0], [1, 0, 1]],
            row_labels=["r", "A", "B"],
            column_labels=["r", "A", "B"],
        )
        matrix.add(matrix.highlight_cells([(0, 0), (1, 0), (1, 1)]))
        matrix_section = center_group(
            _caption("visible relationships"),
            matrix,
            buff=SPACING.sm,
        )

        lower = side_by_side(
            probability_section,
            side_by_side(tree_section, matrix_section, buff=SPACING.lg),
            buff=SPACING.xl,
        )
        composition = center_group(
            heading,
            token_section,
            lower,
            buff=SPACING.lg,
        )
        if composition.width > SAFE_MARGINS.safe_width:
            composition.scale_to_fit_width(SAFE_MARGINS.safe_width)
        if composition.height > SAFE_MARGINS.safe_height:
            composition.scale_to_fit_height(SAFE_MARGINS.safe_height)
        self.add(composition)
