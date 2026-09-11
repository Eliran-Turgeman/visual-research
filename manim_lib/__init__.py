"""Reusable Manim primitives, loaded only when a public export is requested.

Leaf modules such as timeline, teaching, production, doctor and metrics remain
importable without graphics/audio dependencies. ``from manim_lib import X``
retains the same public objects; requesting visual exports still requires Manim.
"""

from importlib import import_module


_EXPORT_GROUPS = {
    "composition": ("center_group", "dim_overlay", "place_at_safe_edge", "safe_frame_rect", "side_by_side"),
    "computation": ("Computation", "Operand"),
    "continuity": ("grow_branch", "identity_rearrange", "map_ancestry_to_mask", "map_tree_to_sequence",
                   "restore_semantic_focus", "section_transition", "semantic_focus"),
    "equations": ("EquationSteps",),
    "focus": ("FocusContext", "focus_on", "restore_focus"),
    "layout": ("assert_no_overlaps", "assert_within_safe_frame", "bounding_box", "bounding_box_overlay",
               "boxes_overlap", "contains", "find_overlaps", "mobjects_overlap", "within_safe_frame"),
    "matrices": ("LabeledMatrix",),
    "probability": ("DistributionEntry", "ProbabilityDistribution", "animate_mass_transfer"),
    "theme": ("ACCENT", "BACKGROUND", "DANGER", "DIM_OPACITY", "FOCUS_RESTORE_OPACITY", "NEUTRAL",
              "PRIMARY", "ROLE_COLORS", "SAFE_MARGINS", "SHADOW", "SPACING", "STROKES", "SUCCESS",
              "SURFACE", "SURFACE_ELEVATED", "TEXT_MUTED", "TEXT_PRIMARY", "TEXT_SECONDARY", "TYPOGRAPHY"),
    "timelines": ("EventTimeline",),
    "narrated_scene": ("NarratedScene",),
    "tokens": ("CandidateToken", "TokenBox", "TokenSequence", "TokenState"),
    "trees": ("StableTree", "TreeNode"),
}
_EXPORTS = {name: module for module, names in _EXPORT_GROUPS.items() for name in names}


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | _EXPORTS.keys())

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
    "SHADOW",
    "SPACING",
    "STROKES",
    "SUCCESS",
    "SURFACE",
    "SURFACE_ELEVATED",
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
    "identity_rearrange",
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
    "NarratedScene",
    "StableTree",
    "TokenBox",
    "TokenSequence",
    "TokenState",
    "TreeNode",
]
