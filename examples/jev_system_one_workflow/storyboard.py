"""Teaching arc and verified toy data for the Jev System One episode."""

from __future__ import annotations

from dataclasses import dataclass


CASE_ID = "CS-1042"
STATE_FIELDS = {
    "message": ("Message", "charged twice; refund", "str"),
    "charges": ("Charges", "2 × $49 captured", "list"),
    "policy": ("Policy", "duplicates refundable", "str"),
}


@dataclass(frozen=True)
class ToyJudgments:
    route: str = "billing"
    route_probabilities: tuple[tuple[str, float], ...] = (
        ("billing", 0.78),
        ("technical", 0.14),
        ("account", 0.08),
    )
    route_confidence: float = 0.67
    urgency: int = 4
    urgency_probabilities: tuple[tuple[str, float], ...] = (
        ("0", 0.01),
        ("1", 0.02),
        ("2", 0.06),
        ("3", 0.21),
        ("4", 0.54),
        ("5", 0.16),
    )
    urgency_confidence: float = 0.61
    refund_requested: float = 0.88


JUDGMENTS = ToyJudgments()
POLICY_THRESHOLDS = {
    "route_confidence": 0.60,
    "urgency": 3,
    "refund_requested": 0.60,
}


def route_support_case(judgments: ToyJudgments = JUDGMENTS) -> str:
    """Apply the exact deterministic policy displayed in the worked example."""
    if (
        judgments.route == "billing"
        and judgments.route_confidence >= POLICY_THRESHOLDS["route_confidence"]
        and judgments.urgency >= POLICY_THRESHOLDS["urgency"]
        and judgments.refund_requested >= POLICY_THRESHOLDS["refund_requested"]
    ):
        return "priority_refund"
    return "manual_review"


@dataclass(frozen=True)
class Beat:
    id: str
    purpose: str
    narration: str


BEATS = (
    Beat(
        "generation-versus-evaluation",
        "Separate producing new text from judging supplied state.",
        "Generation and evaluation are different jobs. A generative model continues text. An evaluator receives something that already exists and returns a judgment about it.",
    ),
    Beat(
        "system-one-role",
        "Define the narrow role of a System One model.",
        "A System One model is the evaluator. Jev, named after Jevons, makes fast, focused judgments. It does not write explanations, generate code, or choose its own next action.",
    ),
    Beat(
        "typed-contract",
        "Establish the machine-facing input and output contract.",
        "Its contract is state plus an atomic typed question, producing a typed value and probability information. The possible answer shape is declared before the call.",
    ),
    Beat(
        "atomic-questions",
        "Show why broad requests are decomposed before evaluation.",
        "Do not ask, analyze this and decide what to do. Split that broad request into narrow judgments a knowledgeable person could make quickly, then compose them in code.",
    ),
    Beat(
        "choice-semantics",
        "Define Choice using a declared finite answer space.",
        "Choice asks which declared option fits best. It returns the selected option, a probability distribution across the options, and confidence derived from that distribution.",
    ),
    Beat(
        "score-and-noul-semantics",
        "Distinguish ordered Score levels from Noul truth likelihood.",
        "Score locates the state on declared ordered levels and also returns probabilities and confidence. Noul asks whether one statement is true and returns its yes probability from zero to one, with no separate confidence.",
    ),
    Beat(
        "shared-state-parallelism",
        "Show independent parallel evaluation over one shared state.",
        "Several questions can share one request. Every question sees the same state, but each is evaluated independently and in parallel. One answer does not become hidden context for another.",
    ),
    Beat(
        "probability-versus-confidence",
        "Separate outcome probability from distribution-shape confidence.",
        "Probability belongs to outcomes or levels. Confidence summarizes the shape of the whole Choice or Score distribution: a clear peak is more confident than a spread-out result.",
    ),
    Beat(
        "calibration-is-aggregate",
        "Prevent per-case certainty interpretations of calibration.",
        "Calibration is checked across groups of predictions. If many comparable answers carry probability zero point eight, about eighty percent should be correct. That is not a promise about one case.",
    ),
    Beat(
        "code-owns-control",
        "Place control flow and side effects outside the model boundary.",
        "The model supplies judgments. Application code owns thresholds, branching, retries, escalation, and side effects. System One is a component inside a normal software workflow, not an autonomous agent.",
    ),
    Beat(
        "support-example-input",
        "Instantiate the theory with one stable support record.",
        "Now apply the contract. Record CS 1042 contains a duplicate charge, the customer's refund request, and the policy. The application asks one Choice, one Score, and one Noul together.",
    ),
    Beat(
        "support-example-route",
        "Trace typed toy outputs through deterministic routing and close with limits.",
        "The toy answers are billing, urgency four, and refund-request likelihood zero point eight eight. Code checks its explicit thresholds and selects priority refund. The schema can be valid while the judgment is wrong, and confidence is not certainty for this case.",
    ),
)

BEAT_IDS = tuple(beat.id for beat in BEATS)
