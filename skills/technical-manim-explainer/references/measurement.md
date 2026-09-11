# Measurement: cost per accepted result

Load when reporting a completed attempt or comparing workflows. Rendering
faster is useful only if the result still clears the same acceptance bar.

## Record attempts, not just successful runs

Retain run IDs, source revisions, configuration, render wall time, paid usage
and price evidence when available, retries, cache reuse, review outcome, and
repair count. Include rejected and abandoned attempts in the experiment's
cost. Count accepted **deliverables**, not contact sheets or every rerender of
the same episode.

Report:

- accepted results / attempted results;
- known monetary cost and explicit unknown-cost attempts;
- cost per accepted result across the whole comparison;
- render/computation time, separately from API latency where measured;
- human review and correction time, separately from machine time and dollars.

If any required charge is unknown, the total and cost per accepted result are
unknown or a clearly labeled partial lower bound, never a fabricated zero.
With no accepted results, cost per accepted result is undefined. Zero is valid
only when positively established for that cost component; a silent render can
have zero TTS spend without having zero electricity, subscription, or labor
cost. Do not silently assign a share of a subscription to a request.

For example, two attempts costing a known `$0.40` each and yielding one accepted
video cost `$0.80` per accepted result **for those known charges**. An unknown
agent/subscription charge prevents claiming `$0.80` as the all-in cost. Record
eight minutes of human correction separately rather than adding eight minutes
to render seconds or silently converting it to dollars.

## Local report command

From the repository root, replace the uppercase placeholders with actual
manifest/review paths; they are not committed sample artifacts:

```powershell
python scripts\summarize_production.py --help
python scripts\summarize_production.py `
  PATH_TO_MANIFEST `
  --review PATH_TO_ACCEPTED_REVIEW `
  --accounting accounting.json `
  --output production-report.json
```

`accounting.json` is operator-supplied data, not a file the renderer invents.
Use a project-local file with measured/invoice-backed values, for example:

```json
{
  "schema_version": 1,
  "runs": [
    {
      "run_id": "replace-with-actual-run-id",
      "source": "invoice and operator timer",
      "cost": {"amount": 0.42, "currency": "USD", "coverage": "lower_bound"},
      "human_correction_seconds": 120,
      "repair_count": 1
    }
  ]
}
```

The numbers above illustrate the format, not a measured repository run. Omit
unknown fields or use `null`. Use `coverage: "complete"` only for complete
cost coverage; otherwise use `"lower_bound"`. Supply human correction time
separately; the tool neither infers nor monetizes it. Accounting supplements
measurements and must not overwrite an existing manifest measurement.

The command accepts multiple manifest positional arguments and repeated
`--review` flags. Without `--output`, it prints JSON to stdout. No explicit
validated review means **zero verified acceptances**, not proof of rejection.
Select the intended accounting boundary explicitly: accepted records may be
draft or production, and the reporter does not silently filter profiles.
Do not label mixed-profile totals as production-only costs/results.
Each `--review` must point to the durable **accepted** JSON produced by the
acceptance action (for example, `review.accepted.json`), not a technical-only
review. A technical review passed as acceptance evidence is an error. The
report calls `review.verify_acceptance`, validating retained technical, human,
and artifact evidence against the current run and hashes; an encoded MP4 or a
self-claimed manifest status never counts as approval.
Stale or mismatched supplied acceptance evidence fails the report clearly
rather than being silently ignored.

`metrics.render_seconds` measures the managed wrapper's render-plus-validation
elapsed time, not CPU time or total production time. Optional measurements
include video seconds, narration requests, repeated requests, cache hits, and
repair count; unavailable measurements stay unknown. Cost per accepted minute
uses the accepted review's verified `media.video_duration` with
`verified_review` provenance, so no duplicate operator duration is needed.
If a manifest/accounting record also supplies `video_seconds`, it must match
that verified duration within one millisecond; omit rounded estimates instead.
Unverified metadata does not supply accepted duration. Cost per minute remains
unknown when required verified durations or costs are missing.
Duplicate run IDs/manifests, negative or non-finite values, and mixed
currencies are rejected rather than silently normalized.

## Optimize the small workflow first

1. Check sources, examples, geometry, and rough motion before paid narration.
2. Reuse valid unchanged speech clips; repair the smallest faulty beat and
   preserve its neighbors.
3. Review a low-quality draft, then render the requested delivery preset once
   the mechanism and narration are stable.
4. Stop ineffective repair loops at the declared budget and report the blocker.

Manim `-qh` is 1920×1080 at 60 fps; `-qk` is 3840×2160 at 60 fps. The latter
has **four times as many pixels per frame**. Choosing 1080p instead of 4K does
not establish a measured fourfold rendering-time or cost saving; scene
complexity, caches, encoding, and hardware affect runtime.

## Experimental model routing only

Cheap-versus-strong model routing is a possible **future research experiment**,
not a shipped feature or an implemented autonomous API orchestration framework.
A controlled study could compare a smaller model on bounded mechanical work
and a stronger one on source reasoning, but neither that role assignment nor
expected savings is established until measured. The local reporter only
compares supplied observations; it launches no models and batches no API work.

Hold source material, teaching target, acceptance criteria, repair budget,
output quality, and reviewer procedure fixed. Compare baseline and candidate
over more than one task/attempt; label small samples and reviewer limitations.
Measure cost per accepted result and human correction time, not merely token
price or the agent's own score. Keep correctness/production failures and
learner results separate. Do not claim learner improvement from workflow
throughput, visual polish, or a model preference score.

For the reporter's optional `--compare`, every input run must have the same
explicit `task_id` and `episode_id`. Supply cohort identity as
`cohort: {"id": "...", "model": "...", "settings": {...}}` in the accounting
record, preserving stable model/settings and manifest profile/settings within
each cohort. Mixed profiles within one cohort ID are rejected. The output includes sample
sizes and descriptive cohort results; it does not perform model routing,
claim savings, or establish statistical/educational superiority.

## References and evidence boundaries

Official guidance checked **2026-09-10**:

- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
  (2026-01-09): evaluate observable outcomes with task-specific graders and
  inspect failures rather than trusting the agent's final claim.
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
  (2025-09-29): curate relevant context; this motivates stage-specific loading.
- OpenAI, [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices):
  define scoped criteria and calibrate automated judgments with human review.
  This repository does not require or recommend the deprecated hosted Evals
  platform; the durable advice is the evaluation method.
- OpenAI, [Build iterative repair loops with Codex](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex):
  separate review, focused repair, and validation using trustworthy feedback.
  The local workflow adopts that pattern, not its orchestration dependencies.
- OpenAI, [Cost optimization](https://developers.openai.com/api/docs/guides/cost-optimization):
  reduce unnecessary work and compare model cost against maintained quality.
  API batch, flex, or prompt-cache savings are endpoint-specific; do not apply
  them to local Manim rendering, TTS, or coding-agent subscriptions without
  actual support and billing evidence.
- OpenAI, [Text to speech](https://developers.openai.com/api/docs/guides/text-to-speech):
  use model-supported voices/controls and disclose AI-generated speech.

These are vendor engineering recommendations, not controlled evidence that
this repository improves learning. Educational claims require appropriate
learner evidence and a comparison designed to support the claimed conclusion.
