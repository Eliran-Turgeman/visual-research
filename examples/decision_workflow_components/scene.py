r"""Still reference for typed decisions and confidence-aware routing.

Render at the review resolution with:

    .\.venv\Scripts\python.exe -m manim render -ql -s \
        examples\decision_workflow_components\scene.py DecisionWorkflowComponents
"""

from manim import DOWN, LEFT, RIGHT, UP, Arrow, Scene, Text, VGroup

from manim_lib import (
    ACCENT,
    BACKGROUND,
    SAFE_MARGINS,
    SPACING,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ConfidenceGate,
    DecisionResult,
    DecisionRouter,
    DecisionState,
    OptionSet,
    QuestionCard,
    SchemaBoundary,
    StructuredState,
    SystemNode,
    assert_within_safe_frame,
    center_group,
    side_by_side,
)


def _label(text: str, *, color=TEXT_SECONDARY, size: float = 17) -> Text:
    return Text(text, font_size=size, color=color)


def _flow_arrow(start, end, *, color=TEXT_MUTED) -> Arrow:
    return Arrow(
        start,
        end,
        buff=0.12,
        color=color,
        stroke_width=2,
        max_tip_length_to_length_ratio=0.12,
    )


class DecisionWorkflowComponents(Scene):
    """Show structural validity and confidence policy as separate decisions."""

    def construct(self):
        self.camera.background_color = BACKGROUND

        title = Text(
            "Typed decision workflow",
            font_size=38,
            color=TEXT_PRIMARY,
        )
        subtitle = _label(
            "A valid answer can still require policy review",
            color=TEXT_SECONDARY,
            size=17,
        )
        heading = center_group(title, subtitle, buff=0.08)

        state = StructuredState(
            {
                "request": ("request", "refund #1842", "str"),
                "amount": ("amount", "$128", "money"),
                "account": ("account", "verified", "status"),
            },
            width=3.0,
            field_height=0.53,
            field_buff=0.08,
            font_size=17,
        )
        state.highlight_field("amount")
        state_region = center_group(
            _label("STRUCTURED STATE", color=ACCENT.light, size=14),
            state,
            buff=0.14,
        )

        questions = VGroup(
            QuestionCard.choice(
                "action",
                "Choose the next action",
                ("approve", "review", "reject"),
                active=True,
                width=3.7,
                height=1.22,
                font_size=18,
            ),
            QuestionCard.score(
                "risk",
                "Estimate policy risk",
                width=3.7,
                height=1.22,
                font_size=18,
            ),
            QuestionCard.noul(
                "claim",
                "Is the claim supported?",
                width=3.7,
                height=1.22,
                font_size=18,
            ),
        ).arrange(RIGHT, buff=0.22)
        question_region = center_group(
            _label("TYPED QUESTIONS", color=ACCENT.light, size=14),
            questions,
            buff=0.14,
        )

        result = DecisionResult(
            "action",
            "approve",
            answer_type=str,
            state=DecisionState.RESOLVED,
            width=3.25,
            height=1.35,
            font_size=19,
        )
        allowed_actions = OptionSet(
            ("approve", "review", "reject"),
            option_width=0.92,
            option_height=0.4,
            font_size=15,
        )
        schema = SchemaBoundary(
            "Action schema",
            allowed_actions,
            width=3.45,
        ).highlight_allowed("approve")
        structural_note = _label(
            "STRUCTURALLY VALID",
            color=SUCCESS.light,
            size=14,
        )
        result_region = center_group(
            _label("TYPED RESULT", color=ACCENT.light, size=14),
            result,
            buff=0.14,
        )
        schema_region = center_group(
            schema,
            structural_note,
            buff=0.12,
        )

        structural_row = VGroup(
            state_region,
            result_region,
            schema_region,
        ).arrange(RIGHT, buff=0.75)
        structural_row.move_to([0, -0.08, 0])
        question_region.move_to([0, 1.82, 0])
        structural_flow = VGroup(
            _flow_arrow(state.get_right(), result.get_left()),
            _flow_arrow(result.get_right(), schema.get_left()),
            _flow_arrow(questions.get_bottom(), result.get_top()),
        )

        gate = ConfidenceGate(
            thresholds=(0.60, 0.85),
            region_names=("abstain", "review", "auto"),
            value=0.74,
            width=4.25,
            bar_height=0.25,
            marker_height=0.18,
            font_size=15,
        )
        gate_note = VGroup(
            _label("74% confidence", color=ACCENT.light, size=15),
            _label("selected route: REVIEW", color=ACCENT.light, size=15),
        ).arrange(DOWN, buff=0.04)
        gate_region = center_group(
            _label("CONFIDENCE / POLICY", color=ACCENT.light, size=14),
            gate,
            gate_note,
            buff=0.16,
        )

        policy = SystemNode("policy", width=1.35, height=0.82, font_size=17)
        auto = SystemNode("auto", width=1.25, height=0.78, font_size=16)
        review = SystemNode("human review", width=1.7, height=0.78, font_size=15)
        auto.move_to([2.0, 0.55, 0])
        review.move_to([2.0, -0.55, 0])
        policy.move_to([-0.45, 0, 0])
        router = DecisionRouter(
            policy,
            {"auto": auto, "review": review},
        ).select_route("review")
        router_region = center_group(
            _label("ROUTE BY THRESHOLD", color=ACCENT.light, size=14),
            router,
            buff=0.14,
        )

        policy_row = side_by_side(gate_region, router_region, buff=1.05)
        policy_row.move_to([0, -2.30, 0])

        composition = VGroup(
            heading,
            question_region,
            structural_row,
            structural_flow,
            policy_row,
        )
        heading.move_to([0, 3.18, 0])
        assert composition.width <= SAFE_MARGINS.safe_width
        assert composition.height <= SAFE_MARGINS.safe_height
        assert_within_safe_frame(composition, label="decision workflow reference")
        self.add(composition)
