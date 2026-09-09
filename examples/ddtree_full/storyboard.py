"""Computed DDTree examples and short narration beats for the full episode."""

from dataclasses import dataclass
from math import prod

from examples.ddtree_dflash.algorithm import Q1, Q2, Q3, Prefix, best_first_prefixes


MARGINALS = (Q1, Q2, Q3)
BUDGET = 7
ANCHOR = "well"
PREFIXES = tuple(best_first_prefixes(list(MARGINALS), budget=BUDGET))
BY_KEY = {prefix.key: prefix for prefix in PREFIXES}
ORDER = ("root", *(prefix.key for prefix in PREFIXES))
INDEX = {key: index for index, key in enumerate(ORDER)}
PARENTS = {"root": None, **{prefix.key: prefix.parent for prefix in PREFIXES}}
DEPTHS = {"root": 0, **{prefix.key: prefix.depth for prefix in PREFIXES}}
WORDS = {"root": ANCHOR, **{prefix.key: prefix.token for prefix in PREFIXES}}
VANILLA = tuple(max(q, key=q.get) for q in MARGINALS)
TARGET_CHOICES = {"root": "a", "a": "model", "a-model": "runs"}
ACCEPTED = ("a", "a-model")
BONUS = "runs"


def ancestry(key: str) -> tuple[str, ...]:
    result = [key]
    while PARENTS[result[-1]] is not None:
        result.append(PARENTS[result[-1]])
    return tuple(reversed(result))


MASK = tuple(
    tuple(int(column in ancestry(row)) for column in ORDER)
    for row in ORDER
)


@dataclass(frozen=True)
class FrontierItem:
    path: tuple[str, ...]
    mass: float

    @property
    def key(self):
        return "-".join(self.path)


@dataclass(frozen=True)
class Selection:
    chosen: Prefix
    before: tuple[FrontierItem, ...]
    after: tuple[FrontierItem, ...]


def frontier_trace() -> tuple[Selection, ...]:
    """Expose lazy sibling/child offers around the existing algorithm's pops.

    Selection order is supplied by best_first_prefixes, not a second search
    implementation. Every displayed frontier must agree with that order.
    """
    ranked = [sorted(q, key=lambda word: -q[word]) for q in MARGINALS]
    pending = [FrontierItem((ranked[0][0],), MARGINALS[0][ranked[0][0]])]
    steps = []
    for chosen in PREFIXES:
        before = tuple(sorted(pending, key=lambda item: -item.mass))
        if before[0].path != chosen.path:
            raise ValueError("Visible frontier disagrees with best-first search")
        pending.remove(before[0])
        depth = chosen.depth
        rank = ranked[depth - 1].index(chosen.token)
        if rank + 1 < len(ranked[depth - 1]):
            sibling = ranked[depth - 1][rank + 1]
            path = (*chosen.path[:-1], sibling)
            pending.append(FrontierItem(
                path, prod(MARGINALS[i][word] for i, word in enumerate(path))
            ))
        if depth < len(MARGINALS):
            child = ranked[depth][0]
            pending.append(FrontierItem(
                (*chosen.path, child), chosen.mass * MARGINALS[depth][child]
            ))
        steps.append(Selection(
            chosen, before, tuple(sorted(pending, key=lambda item: -item.mass))
        ))
    return tuple(steps)


SELECTIONS = frontier_trace()


@dataclass(frozen=True)
class Beat:
    chapter: str
    purpose: str
    narration: str


BEATS = (
    Beat("One path is a bet", "Expose a plausible draft, not a title slide.",
         "A draft can be confident and still miss the target's very first choice."),
    Beat("One path is a bet", "Target choice a invalidates the single proposed chain.",
         "The draft proposes the, model, works. But the target chooses a. "
         "There is no matching first token, so none of this draft chain can be reused."),
    Beat("Where the alternatives come from", "Ground the DFlash input and current anchor.",
         "Start with the committed context and the current anchor, well. "
         "D Flash conditions on target-model features and predicts several future positions in one parallel pass."),
    Beat("Where the alternatives come from", "Reveal three marginals, not an autoregressive chain.",
         "These are toy probabilities for three positions. "
         "Each column is a distribution over tokens. Model and system are alternatives at position two, "
         "not predictions conditioned on whichever token we select at position one."),
    Beat("Where the alternatives come from", "Explain factorization under shared conditioning.",
         "With the shared conditioning fixed, the draft distribution factorizes. "
         "A path's probability is the product of its per-position probabilities. "
         "That makes many alternative prefixes cheap to score."),
    Beat("Spend the budget on prefixes", "Turn the overlooked marginal into the reason to branch.",
         "The runner-up a still has thirty-five percent of the first column's draft probability. "
         "D D Tree keeps such alternatives instead of collapsing every column to a single winner."),
    Beat("Spend the budget on prefixes", "Establish root and a finite speculative-node budget.",
         "Here we can afford seven speculative nodes. The anchor is separate. "
         "A max-heap ranks candidate prefixes by their joint draft probability, not just their last token."),
    Beat("Spend the budget on prefixes", "First pop and lazy child/sibling offers.",
         "Seed the heap with the best first token, the. Pop it at zero point five five. "
         "Then offer its next sibling, a, and its best child, the model."),
    Beat("Spend the budget on prefixes", "A shallower runner-up beats a deeper prefix.",
         "A comes next. Zero point three five beats zero point three three for the model. "
         "The best use of this node is breadth, not more depth."),
    Beat("Spend the budget on prefixes", "Worked product: the-model.",
         "Now select the model. Take the parent's mass, zero point five five, "
         "and multiply by model's marginal, zero point six. The prefix mass is zero point three three."),
    Beat("Spend the budget on prefixes", "Worked product: a-model.",
         "The other branch uses the same marginal. Zero point three five times zero point six "
         "gives zero point two one. A model becomes our fourth speculative node."),
    Beat("Spend the budget on prefixes", "Worked product with honest rounding.",
         "Next, extend the model with works. Zero point three three times zero point five two "
         "is zero point one seven one six, displayed as about zero point one seven two."),
    Beat("Spend the budget on prefixes", "Return to a shallower sibling.",
         "The sixth node is the system. Its mass is zero point five five times zero point three: "
         "zero point one six five. Best-first search can return to a shallower branch."),
    Beat("Spend the budget on prefixes", "Complete the second deep path and exact budget.",
         "Seventh, a model works: zero point two one times zero point five two, "
         "about zero point one zero nine. The seven-node budget is now full."),
    Beat("Why this selection works", "Expose monotonicity and the prefix-closure invariant.",
         "Every extension multiplies by a probability at most one, so a child cannot outrank its parent. "
         "Selecting the highest-mass prefixes therefore keeps their ancestors. No selected branch is disconnected."),
    Beat("Why this selection works", "Qualify the expected matched-depth objective under Q.",
         "For a sequence drawn from the draft distribution, expected matched depth is the sum "
         "of the selected prefix masses. This is a draft-model proxy, not a guarantee about what the target will accept."),
    Beat("One tree, one target input", "Reveal real verification cost, root plus budget.",
         "More nodes cover more possibilities, but they also increase verification work. "
         "Our seven proposals plus the anchor give eight input positions. The budget balances coverage against cost."),
    Beat("One tree, one target input", "Move the same node objects into a flat array.",
         "The target receives a flat array. Watch the same nodes move into slots. "
         "We preserve the parent relationships even though the drawing is no longer a tree."),
    Beat("One tree, one target input", "Separate flat index from positional depth.",
         "Array index is not position in the sentence. The and a share depth one. "
         "Both model nodes share depth two. Actual position IDs add the same committed-prefix offset."),
    Beat("Attention restores the branches", "Construct one mask row from concrete ancestry.",
         "Consider works after a model, in slot seven. It can see the anchor, a, model, and itself. "
         "Those are exactly the four visible entries in its attention row."),
    Beat("Attention restores the branches", "Demonstrate forbidden cross-branch leakage.",
         "It must not see the competing the branch. Those entries stay masked. "
         "All nodes can also see the earlier committed context, which is cached and omitted from this little matrix."),
    Beat("Attention restores the branches", "Complete mask, then compute once across all positions.",
         "Apply that same ancestry rule to every row. One target forward pass now computes "
         "a continuation distribution for every prefix. The mask keeps the alternatives from contaminating one another."),
    Beat("The target chooses the path", "Use cached target choices rather than new model passes.",
         "Now walk using those already-computed target decisions. This is a greedy toy example: "
         "at the anchor, the target chooses a. That child exists, so the walk continues."),
    Beat("The target chooses the path", "Continue down the target-selected branch.",
         "After a, the target chooses model. We accept that child too. "
         "The draft scores bought us coverage; they did not decide which branch to emit."),
    Beat("The target chooses the path", "Stop on a miss without discarding the target token.",
         "After a model, the target chooses runs. We proposed works there, not runs. "
         "The walk stops, but runs is still a valid target token and is emitted as the next anchor."),
    Beat("The target chooses the path", "Clarify target-driven sampling, not draft-ratio acceptance.",
         "With sampling, draw from the target's distribution at each visited prefix instead of taking its argmax. "
         "Membership determines whether we can continue using cached work, not whether the target's token is valid."),
    Beat("Keep alternatives, not guesses", "Move accepted nodes and the unmatched target token into output.",
         "The matched a and model join the output. Runs carries us into the next round. "
         "This tree reused two draft tokens where the single chain reused none. The target still chooses every emitted token."),
)
