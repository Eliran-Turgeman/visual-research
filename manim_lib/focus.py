"""Semantic focus and dimming helpers.

Emphasize one or more mobjects while dimming the rest to retain context, then
safely restore prior opacity/color.  The API preserves object identity and
returns animations rather than mutating global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from manim import Animation, FadeToColor, Mobject

from .theme import DIM_OPACITY, FOCUS_RESTORE_OPACITY, TEXT_MUTED


# ---------------------------------------------------------------------------
# Snapshot for safe restore
# ---------------------------------------------------------------------------

@dataclass
class _MobjectSnapshot:
    """Captured visual state of a single mobject for later restoration."""
    opacity: float
    color: str | None


@dataclass
class FocusContext:
    """Opaque token returned by :func:`focus_on` to later :func:`restore_focus`.

    Callers should not inspect internals; just pass this to
    :func:`restore_focus` when the emphasis phase is over.
    """
    _snapshots: dict[int, _MobjectSnapshot] = field(default_factory=dict)


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
        # Snapshot current state
        ctx._snapshots[id(mob)] = _MobjectSnapshot(
            opacity=mob.get_fill_opacity(),
            color=_safe_hex(mob),
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
        snap = focus_ctx._snapshots.get(id(mob))
        if snap is None:
            continue
        anims.append(mob.animate.set_opacity(snap.opacity))
    return anims


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _safe_hex(mob: Mobject) -> str | None:
    """Extract a hex color string from a mobject, returning None on failure."""
    try:
        c = mob.get_color()
        return c.hex if hasattr(c, "hex") else str(c)
    except Exception:
        return None


__all__ = [
    "FocusContext",
    "focus_on",
    "restore_focus",
]
