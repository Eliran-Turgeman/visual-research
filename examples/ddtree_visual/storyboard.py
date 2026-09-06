"""Storyboard data for the DDTree visual explainer episode.

Single source of truth consumed by the scene.  Each beat specifies the
viewer's question, visible state, single perceptual change, narration
text, and a target duration range.  Beat indices correspond 1-to-1 to
narration blocks, so the storyboard cannot silently drift from what is
rendered.

All toy numerics are computed from the authoritative algorithm module
in ``examples/ddtree_dflash/algorithm.py``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# Import the authoritative algorithm and toy marginals.
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "ddtree_dflash")
)
from algorithm import Q1, Q2, Q3, Prefix, best_first_prefixes  # noqa: E402

# ── Beat dataclass ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Beat:
    """One atomic story beat in the episode."""

    index: int
    viewer_question: str
    visible_state: str
    single_change: str
    continuity_link: str
    narration: str
    duration_range: tuple[float, float]


# ── Computed data ─────────────────────────────────────────────────────────

NODE_BUDGET = 7
PREFIXES: tuple[Prefix, ...] = tuple(
    best_first_prefixes([Q1, Q2, Q3], budget=NODE_BUDGET)
)

# Vanilla DFlash failure scenario
VANILLA_PATH = ("the", "model", "works")
TARGET_FIRST_CHOICE = "a"

# Flatten order (BFS by subtree): root + 7 prefixes
FLATTEN_ORDER = (
    "root",
    "the",
    "a",
    "the-model",
    "a-model",
    "the-model-works",
    "the-system",
    "a-model-works",
)
FLATTEN_TOKENS = (
    "well",
    "the",
    "a",
    "model",
    "model",
    "works",
    "system",
    "works",
)
FLATTEN_POSITION_IDS = (0, 1, 1, 2, 2, 3, 2, 3)

# Visibility mask (ancestor-only attention)
VISIBILITY_MASK = [
    [1, 0, 0, 0, 0, 0, 0, 0],
    [1, 1, 0, 0, 0, 0, 0, 0],
    [1, 0, 1, 0, 0, 0, 0, 0],
    [1, 1, 0, 1, 0, 0, 0, 0],
    [1, 0, 1, 0, 1, 0, 0, 0],
    [1, 1, 0, 1, 0, 1, 0, 0],
    [1, 1, 0, 0, 0, 0, 1, 0],
    [1, 0, 1, 0, 1, 0, 0, 1],
]

# Verification walk — target choices at each depth
VERIFICATION_PATH = ("root", "a", "a-model")
TARGET_CHOICES = (("a", True), ("model", True), ("runs", False))
COMMITTED_TOKENS = ("a", "model")
BONUS_TOKEN = "runs"

# The bonus token inherited from the previous DFlash episode
PRIOR_BONUS = "well"


# ── Beats ─────────────────────────────────────────────────────────────────

BEATS: tuple[Beat, ...] = (
    Beat(
        index=0,
        viewer_question="What goes wrong with one draft path?",
        visible_state="Committed ribbon with bonus 'well'; three Q columns",
        single_change=(
            "Argmax path 'the model works' appears; target rejects at "
            "position one; .35 mass for 'a' highlighted as wasted"
        ),
        continuity_link="Ribbon + distributions persist from DFlash episode",
        narration=(
            "DFlash gave us three marginals from one parallel pass. "
            "Taking the argmax at each position yields 'the', 'model', "
            "'works'. But the target model picks 'a' at the very first "
            "position, so the entire speculative path fails. "
            "That thirty-five percent mass for 'a' is wasted."
        ),
        duration_range=(8.0, 12.0),
    ),
    Beat(
        index=1,
        viewer_question="Why not keep the runner-up?",
        visible_state="Distributions with 'a' highlighted; failed path fading",
        single_change=(
            "Tree root appears for bonus 'well'; 'the' and 'a' become "
            "the first two depth-one branches"
        ),
        continuity_link="Distributions dim; tree starts growing in lower half",
        narration=(
            "Instead of betting on one path, DDTree keeps alternatives. "
            "The objective is expected matched depth, which equals the sum "
            "of every node's prefix mass. A max-heap seeded with the best "
            "depth-one token selects the highest-mass prefixes. "
            "First pop: 'the' at point five five. "
            "Second pop: 'a' at point three five. "
            "Breadth beats the deeper candidate the-model at point three three."
        ),
        duration_range=(10.0, 14.0),
    ),
    Beat(
        index=2,
        viewer_question="How are deeper masses computed?",
        visible_state="Tree with root, 'the', 'a'; distributions dimmed",
        single_change=(
            "'the-model' grows from 'the': .55 × .60 = .330 shown as "
            "parent mass times marginal"
        ),
        continuity_link="Tree keeps growing; first visible product",
        narration=(
            "Third pop: the-model. Its mass is the parent's mass times "
            "the marginal. Point five five times point six zero equals "
            "point three three zero. The product means deeper nodes can "
            "never outrank their parent."
        ),
        duration_range=(7.0, 11.0),
    ),
    Beat(
        index=3,
        viewer_question="Does the 'a' branch get deeper too?",
        visible_state="Tree with four nodes so far",
        single_change=(
            "'a-model' grows: .35 × .60 = .210; both depth-two "
            "branches now visible"
        ),
        continuity_link="Same tree; fourth node added",
        narration=(
            "Fourth pop: a-model at point two one zero. "
            "Point three five times point six zero. "
            "Both major branches now extend to depth two."
        ),
        duration_range=(6.0, 10.0),
    ),
    Beat(
        index=4,
        viewer_question="How does the budget fill?",
        visible_state="Tree with five, then six, then seven nodes",
        single_change=(
            "Three final selections: the-model-works (.172), "
            "the-system (.165), a-model-works (.109); budget complete"
        ),
        continuity_link="Same tree; final three nodes appear in order",
        narration=(
            "Fifth: the-model-works, point three three zero times point "
            "five two, about point one seven two. Sixth: the-system at "
            "point one six five. Seventh: a-model-works at point one zero "
            "nine. Seven pops fill the budget. These are the seven "
            "highest-mass prefixes under the factorized draft distribution."
        ),
        duration_range=(9.0, 13.0),
    ),
    Beat(
        index=5,
        viewer_question="How does the target model see this tree?",
        visible_state="Completed 7-node tree",
        single_change=(
            "Tree nodes straighten into flat token sequence; "
            "position IDs from depth, not array index; "
            "identity preserved: same objects move"
        ),
        continuity_link="Tree nodes are the flat tokens — identity preserved",
        narration=(
            "The target model receives a flat token array, not a tree. "
            "The same node objects slide into a horizontal sequence. "
            "Position IDs come from tree depth: both 'the' and 'a' share "
            "position one because they are alternative continuations at "
            "the same depth."
        ),
        duration_range=(8.0, 12.0),
    ),
    Beat(
        index=6,
        viewer_question="How does the target know which nodes are related?",
        visible_state="Flat sequence with position IDs",
        single_change=(
            "Ancestry cells light up row by row; each node sees "
            "root, its ancestors, and itself"
        ),
        continuity_link="Flat sequence persists; mask appears below",
        narration=(
            "Tree attention restores the structure. Each node may attend "
            "to the committed context, its ancestors, and itself, but "
            "never to a sibling branch. Node 'the-model-works' sees "
            "root, 'the', 'the-model', and itself. One target forward "
            "pass computes the correct continuation for every prefix "
            "in parallel."
        ),
        duration_range=(9.0, 13.0),
    ),
    Beat(
        index=7,
        viewer_question="Which path does the target choose?",
        visible_state="Flat sequence with mask; target decision indicator",
        single_change=(
            "Target lights root → a → model; misses on 'runs' "
            "at a-model because 'a-model-runs' is not in the tree"
        ),
        continuity_link="Same flat sequence; path turns green, then stops",
        narration=(
            "Verification walks the tree using the target's own decoding "
            "rule. At the root it picks 'a'. At 'a' it picks 'model'. "
            "At 'a-model' it picks 'runs', but that child is not in our "
            "tree, so the walk stops. "
            "The drafter's scores never chose this path; the target did."
        ),
        duration_range=(9.0, 13.0),
    ),
    Beat(
        index=8,
        viewer_question="What gets committed?",
        visible_state="Verified path highlighted; committed ribbon",
        single_change=(
            "Accepted nodes 'a' and 'model' move into ribbon as green; "
            "'runs' appears as new bonus token in yellow"
        ),
        continuity_link="Ribbon grows; 'runs' becomes next bonus token",
        narration=(
            "The matched tokens 'a' and 'model' join the committed "
            "context. 'Runs' becomes the next bonus token, ready for "
            "the following DFlash pass. "
            "Two speculative tokens were accepted instead of zero. "
            "Speed comes from proposals. Correctness still comes from "
            "the target."
        ),
        duration_range=(8.0, 12.0),
    ),
)

BEAT_COUNT = len(BEATS)
