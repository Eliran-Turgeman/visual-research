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
        visible_state="Token ribbon with committed context 'The model can'",
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
            "One forward pass through the draft model produces an independent "
            "probability distribution for each masked position. "
            "Position one predicts 'the' at fifty-five percent, 'a' at thirty-five. "
            "Position two favors 'model' at sixty percent."
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
            "Crucially, these are independent marginals, not conditional distributions. "
            "Position two's prediction doesn't know what position one actually chose. "
            "This is the price of parallelism: the drafter can't condition on its own "
            "earlier choices within the same block."
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
            "We sample a candidate sequence from these marginals. "
            "For this toy example, the most likely path is 'the', 'model', 'works'. "
            "But because the draft used marginals, this path might not match what "
            "the target model would actually produce."
        ),
        duration_range=(7.0, 11.0),
    ),
    Beat(
        index=7,
        viewer_question="How does the target verify these proposals?",
        visible_state="Candidate ribbon; target model processes all positions at once",
        single_change="Target outputs appear; match/reject comparison per position",
        continuity_link="Same candidate ribbon; target output appears alongside",
        narration=(
            "The target model verifies the entire draft in one forward pass. "
            "It computes the true conditional probability at each position. "
            "Where the draft agrees with the target, the token is accepted. "
            "The first disagreement stops the sequence."
        ),
        duration_range=(8.0, 12.0),
    ),
    Beat(
        index=8,
        viewer_question="What happens to accepted and rejected tokens?",
        visible_state="Candidate ribbon with accept/reject marks",
        single_change="Accepted tokens turn committed green; rejected turn red and fade",
        continuity_link="Same ribbon; tokens visibly transform state",
        narration=(
            "Accepted tokens join the committed context, shown in green. "
            "Even when the draft is wrong, we always get at least one new token "
            "from the target's own distribution at the rejection point. "
            "This is the bonus token, and it's what makes speculative decoding lossless."
        ),
        duration_range=(8.0, 12.0),
    ),
    # --- Act 4: Closing bridge ---
    Beat(
        index=9,
        viewer_question="What if we could verify multiple paths at once?",
        visible_state="Updated committed ribbon; brief tree silhouette appears",
        single_change="Tree silhouette fades in beside the ribbon, then dims",
        continuity_link="Ribbon with new committed tokens stays; tree is a teaser",
        narration=(
            "DFlash gives us cheap parallel drafts, but we verified just one path. "
            "What if we could explore several likely continuations in a single "
            "target pass? That's exactly what DDTree does, and we'll cover it "
            "in the next episode."
        ),
        duration_range=(7.0, 10.0),
    ),
)

# The scene uses len(BEATS) to verify narration block count matches.
BEAT_COUNT = len(BEATS)

# Toy marginals – same values used in the combined example, authoritative
# source for every number shown in this episode.
Q1 = {"the": 0.55, "a": 0.35, "this": 0.10}
Q2 = {"model": 0.60, "system": 0.30, "code": 0.10}
Q3 = {"works": 0.52, "runs": 0.28, "fails": 0.20}

# The candidate path shown in the verification section
CANDIDATE_PATH = ("the", "model", "works")

# Target verification result: True = accepted, False = rejected
# In this toy example all three match (best case for illustration)
VERIFICATION_RESULT = (True, True, True)
BONUS_TOKEN = "well"
