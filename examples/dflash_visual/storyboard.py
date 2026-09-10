"""Storyboard data for the DFlash visual explainer episode.

This is the single source of truth consumed by the scene. Each beat
specifies the viewer's question, the visible state description, the
single change that happens, a continuity link back to the previous
beat, narration text, and a target duration range in seconds.

The scene imports BEATS and mirrors it: beat indices correspond to
narration blocks, so the storyboard cannot silently drift from
what is rendered.
"""

from dataclasses import dataclass


def greedy_choice(distribution: dict[str, float]) -> str:
    """Argmax, with insertion order standing in for a fixed vocabulary tie-break."""
    return max(distribution, key=distribution.get)


@dataclass(frozen=True)
class GreedyVerification:
    """One causal target pass: n proposals and n+1 target next-token choices."""

    proposals: tuple[str, ...]
    target_choices: tuple[str, ...]
    accepted_count: int

    @property
    def accepted_mask(self) -> tuple[bool, ...]:
        return tuple(i < self.accepted_count for i in range(len(self.proposals)))

    @property
    def bonus_token(self) -> str:
        return self.target_choices[self.accepted_count]

    @property
    def committed_tokens(self) -> tuple[str, ...]:
        return self.proposals[:self.accepted_count] + (self.bonus_token,)


def verify_greedy(
    proposals: tuple[str, ...], target_choices: tuple[str, ...],
) -> GreedyVerification:
    """Keep only the matching prefix, then the target's choice at its boundary.

    Mirrors dflash_generate's cumprod/sum and posterior[acceptance_length]
    in z-lab/dflash, revision 44947fbf71114e241c96de194f4b382b5dd330d0,
    dflash/model.py. This episode uses its temperature=0 (argmax) regime.
    Target choice i must be conditioned on context + proposals[:i].
    """
    if len(target_choices) != len(proposals) + 1:
        raise ValueError("Need one target choice per proposal plus the bonus position")
    accepted_count = 0
    for proposal, target in zip(proposals, target_choices):
        if proposal != target:
            break
        accepted_count += 1
    return GreedyVerification(proposals, target_choices, accepted_count)


# Illustrative probabilities, not model measurements or acceptance rates.
Q1 = {"the": 0.55, "a": 0.35, "this": 0.10}
Q2 = {"model": 0.60, "system": 0.30, "code": 0.10}
Q3 = {"works": 0.52, "runs": 0.28, "fails": 0.20}
DRAFT_MARGINALS = (Q1, Q2, Q3)
CANDIDATE_PATH = tuple(greedy_choice(q) for q in DRAFT_MARGINALS)

# Keys are suffixes after the fixed context "We see". The final two rows
# use the wrong draft prefix: their predictions must not survive the miss.
TARGET_CONDITIONALS = {
    (): {"the": 0.70, "a": 0.30},
    ("the",): {"model": 0.20, "system": 0.80},
    ("the", "model"): {"works": 0.90, "fails": 0.10},
    ("the", "model", "works"): {"well": 0.60, "now": 0.40},
}
TARGET_CHOICES = tuple(
    greedy_choice(TARGET_CONDITIONALS[CANDIDATE_PATH[:i]])
    for i in range(len(CANDIDATE_PATH) + 1)
)
VERIFICATION = verify_greedy(CANDIDATE_PATH, TARGET_CHOICES)
VERIFICATION_RESULT = VERIFICATION.accepted_mask
BONUS_TOKEN = VERIFICATION.bonus_token


@dataclass(frozen=True)
class Beat:
    """One atomic story beat in the episode."""
    index: int
    viewer_question: str
    visible_state: str
    single_change: str
    continuity_link: str
    narration: str
    duration_range: tuple[float, float]  # (min_seconds, max_seconds)


BEATS: tuple[Beat, ...] = (
    # --- Act 1: Setup – Why does drafting matter? ---
    Beat(
        index=0,
        viewer_question="Why is autoregressive decoding slow?",
        visible_state="Token ribbon with committed context 'We see'",
        single_change="Empty slots appear one-by-one to the right of context",
        continuity_link="Ribbon introduced; stays on screen for the entire episode",
        narration=(
            "A large language model generates tokens one at a time. "
            "Each new token requires a full forward pass through the target model. "
            "These empty slots represent the future tokens we need."
        ),
        duration_range=(6.0, 9.0),
    ),
    Beat(
        index=1,
        viewer_question="What does a normal drafter do?",
        visible_state="Ribbon with context + empty slots; small drafter box below",
        single_change="Slots fill sequentially: slot 1, then 2, then 3",
        continuity_link="Same ribbon; drafter box appears and feeds slots one-by-one",
        narration=(
            "A standard draft model fills these slots one at a time, "
            "just like the target. It's faster per step, but still sequential. "
            "Each prediction waits for the previous one."
        ),
        duration_range=(6.0, 9.0),
    ),
    Beat(
        index=2,
        viewer_question="How does DFlash do it differently?",
        visible_state="Ribbon resets: empty slots become masked block [M][M][M]",
        single_change="All three mask tokens light up simultaneously in one pass",
        continuity_link="Same ribbon; sequential slots transform into mask tokens",
        narration=(
            "DFlash replaces this with parallel prediction. "
            "Instead of filling slots one by one, it masks the entire future block "
            "and predicts all positions in a single forward pass."
        ),
        duration_range=(7.0, 10.0),
    ),
    # --- Act 2: Mechanism – How DFlash works ---
    Beat(
        index=3,
        viewer_question="Where does the draft model get its context?",
        visible_state="Ribbon + masks; target model box with hidden-state arrows",
        single_change="Hidden feature streams flow from target box into draft stack",
        continuity_link="Masks remain; target model appears above, streams descend",
        narration=(
            "The key insight: DFlash borrows hidden features from the last target pass. "
            "These rich representations are projected and injected as keys and values "
            "into every layer of the small draft model."
        ),
        duration_range=(7.0, 11.0),
    ),
    Beat(
        index=4,
        viewer_question="What comes out of the draft pass?",
        visible_state="Draft stack with masks fed in; probability columns grow",
        single_change="Each mask unfolds into a probability distribution column",
        continuity_link="Masks flow into draft; distributions emerge from each mask",
        narration=(
            "One draft pass produces a probability distribution for each masked "
            "position. These bars are toy probabilities, not measurements. "
            "Each column ranks possible tokens for its own position."
        ),
        duration_range=(8.0, 12.0),
    ),
    Beat(
        index=5,
        viewer_question="Why are these marginals, not conditionals?",
        visible_state="Three distribution columns side by side",
        single_change="Brief annotation: 'q2 does not depend on y1' highlighted",
        continuity_link="Same distributions; annotation appears then dims",
        narration=(
            "These marginals share the context, but not the chosen draft tokens. "
            "Position two doesn't condition on position one's choice. "
            "The drafter predicts all three before any within-block choice is made."
        ),
        duration_range=(7.0, 11.0),
    ),
    # --- Act 3: Verification – Why correctness is preserved ---
    Beat(
        index=6,
        viewer_question="How do we pick tokens from these distributions?",
        visible_state="Distributions with top candidates highlighted",
        single_change="One candidate path 'the model works' emerges as a ribbon",
        continuity_link="Candidates emerge from their columns into the ribbon slots",
        narration=(
            "This example uses greedy decoding: temperature zero. "
            "Choose the largest probability in each column: 'the', 'model', 'works'. "
            "These are proposals, not yet committed output."
        ),
        duration_range=(7.0, 11.0),
    ),
    Beat(
        index=7,
        viewer_question="How does the target verify these proposals?",
        visible_state="Candidate ribbon; target model processes all positions at once",
        single_change="Target argmax row appears; first match and first miss are marked",
        continuity_link="Same candidate ribbon; target output appears alongside",
        narration=(
            "One causal target pass predicts next tokens along this draft path. "
            "'The' matches. But the target chooses 'system', not 'model'. "
            "The accepted prefix stops before that first mismatch."
        ),
        duration_range=(10.0, 14.0),
    ),
    Beat(
        index=8,
        viewer_question="Can a later matching token still be accepted?",
        visible_state="Target 'works' matches the third proposal, after the miss",
        single_change="Rejected model and unused works are marked red, then removed",
        continuity_link="Same comparison row; the accepted prefix stays fixed",
        narration=(
            "Even this later 'works' match cannot be kept. "
            "The target computed it after 'the model', not 'the system'. "
            "Discard the entire suffix from the mismatch onward."
        ),
        duration_range=(9.0, 13.0),
    ),
    Beat(
        index=9,
        viewer_question="What happens to accepted and rejected tokens?",
        visible_state="Accepted prefix plus an empty slot at the first miss",
        single_change="The prefix turns green; target system fills the first-miss slot",
        continuity_link="Same ribbon; tokens visibly transform state",
        narration=(
            "Commit 'the', then the target's own 'system' at the first miss. "
            "This target token guarantees progress, even with zero draft matches. "
            "If every proposal matches, the bonus goes after the whole block."
        ),
        duration_range=(11.0, 15.0),
    ),
    Beat(
        index=10,
        viewer_question="Why does this preserve target output semantics?",
        visible_state="Target-only greedy tokens align beneath the committed tokens",
        single_change="Baseline the then system matches the committed output",
        continuity_link="Compare the same committed prefix, without moving it",
        narration=(
            "Target-only greedy decoding also chooses 'the', then 'system'. "
            "Same target, same causal prefix, same tie-breaking: same greedy output. "
            "That is the correctness argument. The bonus guarantees progress, "
            "not a proof of distributional equivalence for sampling."
        ),
        duration_range=(12.0, 17.0),
    ),
    # --- Act 4: Closing bridge ---
    Beat(
        index=11,
        viewer_question="What if we could verify multiple paths at once?",
        visible_state="Updated committed ribbon; brief tree silhouette appears",
        single_change="Tree silhouette fades in beside the ribbon, then dims",
        continuity_link="Ribbon with new committed tokens stays; tree is a teaser",
        narration=(
            "DFlash made the draft parallel, but we verified just one path. "
            "DDTree explores several likely continuations in one target pass. "
            "That's the next episode."
        ),
        duration_range=(7.0, 10.0),
    ),
)

# The scene uses len(BEATS) to verify narration block count matches.
BEAT_COUNT = len(BEATS)
