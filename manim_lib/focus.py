"""Semantic focus and dimming helpers.

Emphasize one or more mobjects while dimming the rest to retain context, then
safely restore prior opacity/color.  The API preserves object identity and
returns animations rather than mutating global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from manim import Animation, AnimationGroup, Mobject

from .theme import DIM_OPACITY, FOCUS_RESTORE_OPACITY, TEXT_MUTED


# ---------------------------------------------------------------------------
# Snapshot for safe restore
# ---------------------------------------------------------------------------

@dataclass
class _MobjectSnapshot:
    """Captured opacity state of one family member."""
    mobject: Mobject
    fill_opacity: object
    stroke_opacity: object


@dataclass
class FocusContext:
    """Opaque token returned by :func:`focus_on` to later :func:`restore_focus`.

    Callers should not inspect internals; just pass this to
    :func:`restore_focus` when the emphasis phase is over.
    """
    _snapshots: dict[int, tuple[_MobjectSnapshot, ...]] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def focus_on(
    targets: Mobject | Sequence[Mobject],
    *,
    context: Sequence[Mobject] = (),
    dim_opacity: float = DIM_OPACITY,
    dim_color: str = TEXT_MUTED,
) -> tuple[list[Animation], FocusContext]:
    """Build animations that emphasise *targets* and dim *context* mobjects.

    Returns ``(animations, focus_ctx)`` where *animations* is a list of Manim
    animations ready to be passed to ``self.play()``, and *focus_ctx* is a
    token to pass to :func:`restore_focus` later.

    Object identity is preserved—no mobjects are replaced.
    """
    if isinstance(targets, Mobject):
        targets = [targets]

    ctx = FocusContext()
    anims: list[Animation] = []

    target_ids = {id(t) for t in targets}

    for mob in context:
        if id(mob) in target_ids:
            continue
        ctx._snapshots[id(mob)] = tuple(
            _MobjectSnapshot(
                mobject=member,
                fill_opacity=member.get_fill_opacity(),
                stroke_opacity=member.get_stroke_opacity(),
            )
            for member in mob.family_members_with_points()
        )
        anims.append(mob.animate.set_opacity(dim_opacity))

    return anims, ctx


def restore_focus(
    context: Sequence[Mobject],
    focus_ctx: FocusContext,
) -> list[Animation]:
    """Build animations that restore mobjects dimmed by :func:`focus_on`.

    Only mobjects whose state was previously captured in *focus_ctx* are
    touched; others are left alone.
    """
    anims: list[Animation] = []
    for mob in context:
        snapshots = focus_ctx._snapshots.get(id(mob))
        if snapshots is None:
            continue
        member_anims = [
            snapshot.mobject.animate.set_fill(
                opacity=snapshot.fill_opacity
            ).set_stroke(opacity=snapshot.stroke_opacity)
            for snapshot in snapshots
        ]
        if member_anims:
            anims.append(AnimationGroup(*member_anims))
    return anims


__all__ = [
    "FocusContext",
    "focus_on",
    "restore_focus",
]
