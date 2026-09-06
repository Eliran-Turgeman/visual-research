"""Reusable Manim primitives for narrated technical explainers."""

from .composition import (
    center_group,
    dim_overlay,
    place_at_safe_edge,
    safe_frame_rect,
    side_by_side,
)
from .computation import Computation, Operand
from .continuity import (
    grow_branch,
    map_ancestry_to_mask,
    map_tree_to_sequence,
    restore_semantic_focus,
    section_transition,
    semantic_focus,
)
from .equations import EquationSteps
from .focus import FocusContext, focus_on, restore_focus
from .layout import (
    assert_no_overlaps,
    assert_within_safe_frame,
    bounding_box,
    bounding_box_overlay,
    boxes_overlap,
    contains,
    find_overlaps,
    mobjects_overlap,
    within_safe_frame,
)
from .matrices import LabeledMatrix
from .probability import (
    DistributionEntry,
    ProbabilityDistribution,
    animate_mass_transfer,
)
from .theme import (
    ACCENT,
    BACKGROUND,
    DANGER,
    DIM_OPACITY,
    FOCUS_RESTORE_OPACITY,
    NEUTRAL,
    PRIMARY,
    ROLE_COLORS,
    SAFE_MARGINS,
    SPACING,
    STROKES,
    SUCCESS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TYPOGRAPHY,
)
from .timelines import EventTimeline
from .tokens import CandidateToken, TokenBox, TokenSequence, TokenState
from .trees import StableTree, TreeNode

__all__ = [
    # Theme
    "ACCENT",
    "BACKGROUND",
    "DANGER",
    "DIM_OPACITY",
    "FOCUS_RESTORE_OPACITY",
    "NEUTRAL",
    "PRIMARY",
    "ROLE_COLORS",
    "SAFE_MARGINS",
    "SPACING",
    "STROKES",
    "SUCCESS",
    "TEXT_MUTED",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "TYPOGRAPHY",
    # Focus
    "FocusContext",
    "focus_on",
    "restore_focus",
    # Composition
    "center_group",
    "dim_overlay",
    "place_at_safe_edge",
    "safe_frame_rect",
    "side_by_side",
    # Computation
    "Computation",
    "Operand",
    # Continuity
    "grow_branch",
    "map_ancestry_to_mask",
    "map_tree_to_sequence",
    "restore_semantic_focus",
    "section_transition",
    "semantic_focus",
    # Probability
    "DistributionEntry",
    "ProbabilityDistribution",
    "animate_mass_transfer",
    # Equations
    "EquationSteps",
    # Layout
    "assert_no_overlaps",
    "assert_within_safe_frame",
    "bounding_box",
    "bounding_box_overlay",
    "boxes_overlap",
    "contains",
    "find_overlaps",
    "mobjects_overlap",
    "within_safe_frame",
    # Components
    "CandidateToken",
    "EventTimeline",
    "LabeledMatrix",
    "StableTree",
    "TokenBox",
    "TokenSequence",
    "TokenState",
    "TreeNode",
]
