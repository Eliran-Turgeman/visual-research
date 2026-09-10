# Teaching contract: evidence before animation

Load at research/storyboard time. Keep the contract short enough to guide
implementation and review; it is not a second script or an elaborate prompt.

## Minimum content

- **Audience and prerequisites:** what the viewer already knows, what needs
  establishing, and what is out of scope.
- **Objective:** one observable mechanism-level ability, such as tracing a
  target-driven walk, rather than "understand DDTree."
- **Misconception:** the tempting wrong interpretation the picture must rule
  out, such as confusing draft mass with target acceptance probability.
- **Claims and provenance:** stable claim IDs, precise statements and
  assumptions, source IDs, and exact locations.
- **Worked example and beats:** small inputs, independently checked operations,
  expected states, and the narration/visual beats that establish each claim.
- **Transfer:** one or two short unseen variations with expected answers.
- **Separate rubrics:** technical correctness, production quality, and learner
  understanding. Never average away a fatal technical error with good polish.

## Contract files and local validation

The canonical examples keep their compact versioned contract in
`examples\ddtree_full\teaching.json` and
`examples\speculative_decoding_timeline\teaching.json`. These cover all 27 and
6 teaching beats respectively. The other supplied contracts also have complete
narration mappings: DFlash 12, DDTree visual 9, combined DDTree 30, and
speculative-decoding flow 8. Mapping completeness is not source entailment,
perceptual approval, or learner evidence. Inspect warnings and unresolved
claims instead of treating an older provisional mapping as a continuing
scene defect.

From the repository root:

```powershell
python scripts\validate_teaching.py --help
python scripts\validate_teaching.py examples\ddtree_full\teaching.json --check-sources --json
python scripts\validate_teaching.py examples\ddtree_full\teaching.json `
  --timeline PATH_TO_RENDERED_TIMELINE --check-sources `
  --output teaching-validation.json --json
```

Replace the timeline placeholder with the path from the actual render
manifest. Use `--root` to specify a different repository root if needed.
The validator uses only the standard library; no render, model, or paid API
request is involved. Exit `0` means no hard errors, `1` means validation
errors, and `2` means bad input. Inspect warnings even with exit `0`.

`--output` requires a timeline and writes an evidence envelope with
`status: "passed"` or `"failed"`, exact contract/timeline paths and raw-byte
SHA-256 hashes, the timeline's run ID when present, and the full validation
report. It does not overwrite either input. Preserve that artifact with the
matching run; the `--json` stdout remains the raw report, not this envelope.
Malformed or unreadable inputs return `2` without a successful validation
artifact; semantic failures write a failed artifact and return `1`.

Validation checks contract structure, supplied source hashes, worked
calculations, and timeline mappings when provided. A duration-budget excess
produces a `duration_review` warning: explain or repair the pacing, rather than
automatically cutting a useful explanation to satisfy a timer.
Missing source, timeline, or visual-event evidence is recorded in
`omitted_checks`, not counted as a passed check. Source-content SHA-256 checks
normalize CRLF to LF over UTF-8; the bound output artifact's contract/timeline
hashes instead identify the exact raw parsed bytes.
Unresolved source support also produces warnings and `claim_support` omissions.
For example, a generic parallel-drafter assumption or unquantified speedup claim
must not become verified evidence merely because all narration beats map.

The result separates errors, warnings, deterministic checks, and evidence
limits. A source hash proves identity/drift, not that a source entails a claim.
Claim entailment requires human review; audiovisual fidelity, human
comprehension, and production acceptance are not established by this command.
The version-1 schema and `load_contract` / `validate_contract` interfaces are
documented in `manim_lib\teaching.py`.

## Source provenance

For each source retain title, author/organization, URL or repository path,
version/date or full commit hash, access date, and equation/section/function
location. A mutable `main` URL alone is not a reproducible citation. If the
paper version was not resolved, mark it unresolved rather than guessing.

For each claim record what that location actually supports and its limits:
an equation may support an objective under a draft distribution but not a
wall-clock speedup or a claim about target acceptance. Keep measured results,
paper-reported results, toy values, and design choices distinct. Resolve paper
versus implementation disagreements explicitly.

The [DDTree episode](../../../examples/ddtree_full/README.md) records an exact
official implementation revision and relevant code locations. Its toy
distributions do not become benchmark results merely because they are
source-consistent.

## Rubrics and transfer

| Rubric | Evidence | What it cannot establish alone |
|---|---|---|
| Technical | Source/claim trace, independently computed example, focused tests, semantic review | Whether viewers can follow the presentation |
| Production | Geometry checks, sampled frames, transitions, complete audiovisual playback, reproducibility | Whether viewers learned the mechanism |
| Learner | Predicted misconception, unseen questions, expected answers, recorded learner responses when available | Broad or causal learning improvement from a tiny convenience sample |

Useful transfer questions change a value, assumption, or outcome instead of
asking the viewer to repeat the narrator:

1. **Timeline:** if three draft steps cost `0.8` target-pass units each and all
   candidates still match, does one speculative round beat three serial target
   passes? **Expected answer:** no; `3 × 0.8 + 1 = 3.4 > 3`. Batched verification
   alone does not guarantee a speedup.
2. **DDTree:** if the target chooses a token absent from the current node's
   children, is that token rejected as invalid? **Expected answer:** no. The
   target token is emitted; the missing child stops reuse of the precomputed
   branch and the token becomes the next anchor.

A reviewer can check that the artifact teaches enough to answer these
questions. That is a **teaching review**, not a measured learner study. Record
actual learner responses separately if collected; otherwise say "learner
outcomes untested." Do not use a model answering from the script as evidence
that a viewer learned from the video.

## Keep evidence close to the decision

Load the relevant source excerpt and contract claim when checking a beat.
Keep raw papers, tool logs, and long transcripts out of routine repair context.
When a claim or prerequisite changes, update the affected example, narration,
transfer answer, and technical checks together before rendering again.

These workflow choices follow vendor engineering advice about scoped
evaluation and useful context, not established evidence of this video's
educational effect. See [measurement references](measurement.md#references-and-evidence-boundaries).
