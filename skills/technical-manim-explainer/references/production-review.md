# Production review: an artifact-grounded loop

Load for rendering, inspection, repair, and handoff. Keep the agent-directed
workflow small: local scripts collect evidence; a reviewer evaluates the
artifact. There is no autonomous approval service.

## Draft is not production

- **Draft:** rough silent motion at low quality by default. Credentials do not
  opt a wrapper into paid narration. Explicit speech drafts are possible when
  provider use is authorized.
- **Production:** explicit non-silent provider and intended delivery quality,
  with media/audio verification and a run-specific manifest.
- **Rendered:** encoding and wrapper checks succeeded; the result is not yet
  reviewed or accepted.
- **Reviewed:** findings and evidence exist for the actual artifact.
- **Accepted:** explicit review requirements pass and the acceptance record is
  bound to that manifest and its current artifact hashes.

See [root commands](../../../README.md#render-a-managed-episode). Direct
Manim remains an escape hatch; it does not automatically provide wrapper
profiles, run isolation, or acceptance evidence.

## Review the artifact, not the agent's description

Keep the teaching contract, run manifest, video, actual narration timeline,
frame index/contact sheets, and review record together. Use the manifest's
run-specific paths rather than a mutable "latest" video or scene timeline.
Preserve exact source revision and dirty-tree status; never serialize secrets
or the entire environment.

Inspect:

1. The first and last video frames.
2. Near-start, middle, and near-end of every narration block.
3. Frames just before and after each major visual transition, plus its
   intermediate motion. Narration boundaries and visual events need not match.
4. The entire rough cut to judge causal continuity and pacing.
5. The **entire final video with audio** to judge speech, timing, drift,
   transients, omissions, and the closing state.

Contact sheets make sampling efficient but cannot replace playback. Geometry
tests cannot establish legibility or understanding, and an audio stream cannot
establish intelligible speech. If playback or listening is unavailable, say
what remains unreviewed and leave acceptance pending.

## Bounded review → repair → validate

Before iterating, set a small attempt/time/spend budget appropriate to the
episode; a practical starting policy is at most **two repair rounds** after
the initial review. This is an agent work policy, not an automatic CLI loop or
a guarantee that two rounds suffice.

For each round:

1. **Review without editing.** Record the timestamp/beat, artifact evidence,
   violated criterion, severity, and a concrete expected correction. Separate
   source/algorithm errors from layout/audio defects and teaching weaknesses.
2. **Repair narrowly.** Fix the highest-impact root cause, preserving working
   object identity, valid speech clips, and unaffected beats. Do not rewrite
   the episode from an ungrounded impression that it could be "better."
3. **Validate.** Rerun affected example/semantic/geometry checks. Render changed
   output, refresh timeline/frame evidence, and recheck the finding plus
   neighboring transitions for regressions.
4. **Decide from evidence.** Stop when requirements pass, or stop at the
   declared budget/no-progress condition with explicit unresolved findings.
   Escalate a source conflict or missing capability rather than weakening
   the rubric or relabeling a silent draft as a final.

Review the complete final audiovisual result after the last artifact-changing
repair, even when the targeted checks passed. A script-generated statement
that the agent is confident is not review evidence.

## Acceptance and handoff

Bind the review record to the render manifest and video/timeline hashes.
Changing source and rerendering, remuxing audio, trimming the MP4, or editing a
hashed timeline invalidates the old binding. Generate fresh review evidence;
do not copy approval flags to the new run. Keep review records separate from
the retained render manifest to avoid circular hashes; do not modify that
manifest after binding review evidence to it.

Use three distinct assessments:

- **Technical:** exact claims, assumptions, numerical examples, and visual
  operations match the pinned sources.
- **Production:** no unintended overlap/clipping, readable intended-size text,
  stable identity, honest scales, causal transitions, synchronized intelligible
  audio, and reproducible artifacts.
- **Teaching/learner:** the artifact establishes the objective and addresses
  the misconception; inspect the transfer questions and expected answers.
  Record any actual learner results separately. Teaching review is not proof
  of learning improvement.

An automated validator can check files, hashes, schemas, and declared evidence;
it cannot certify that someone watched the video or learned from it. Never
populate human approval or playback attestations for actions not performed.
When the artifact passes machine checks but full review is unavailable, deliver
it as **rendered, acceptance pending**, with the missing review stated plainly.

## Reproducible local review commands

From the repository root, replace uppercase paths with the matching run's
actual files. Output record paths must be new; frame directories must be
empty. These commands inspect existing media and make no speech/API requests.

```powershell
python scripts\review_production.py --help
python scripts\review_production.py inspect PATH_TO_MANIFEST `
  --output review.json --frames-dir review-frames
```

`inspect` performs technical checks only. `--frames-dir` produces the frame
evidence required for later acceptance; omitting it is useful for diagnostics
but cannot yield an acceptable record by itself. The frame index includes
hashes and provenance for actual verified JPEGs, not just requested timestamps.
The render manifest remains unchanged with status `rendered`.

For a canonical episode, bind its teaching validation to the same timeline:

```powershell
python scripts\validate_teaching.py examples\ddtree_full\teaching.json `
  --timeline PATH_TO_RENDERED_TIMELINE --check-sources `
  --output teaching-validation.json
```

After real full playback, listening, and teaching review, the reviewer supplies
`human-review.json`. This is an attributed attestation, not cryptographic
reviewer authentication. Its required fields are:

| Field | Required evidence |
|---|---|
| `schema_version`, `run_id` | Version `1` and exact matching run ID |
| `review_sha256` | SHA-256 of the original technical `review.json` bytes |
| `reviewer`, `reviewed_at` | Nonblank reviewer; timezone-qualified ISO timestamp after technical review and not in the future |
| `decision` | `"accept"` only after review supports acceptance |
| `confirmations` | Explicit `watched_full_video`, `visual_quality`, `synchronization`, and `teaching_correctness`; production also requires `listened_full_audio`, all true only when actually confirmed |
| `audiovisual_notes`, `teaching_notes` | Nonblank observations grounded in this artifact |
| `findings` | Explicit `[]` when none, otherwise the structured findings below |
| `teaching_contract_sha256` | Exact contract-byte hash when attaching teaching evidence |

Use `(Get-FileHash -Algorithm SHA256 review.json).Hash.ToLowerInvariant()` and
the same command on the contract to obtain current hashes. Do not author
confirmation flags for a human who has not performed those actions, or use
generic agent confidence as notes.

Each finding has `id`, `time_seconds`, `severity` (`blocker`, `major`, `minor`,
or `info`), `description`, `expected_behavior`, and `status` (`open` or
`resolved`). An open blocker/major prevents acceptance. Resolved findings also
need `resolution`, `resolved_by`, and `resolved_at` between the technical and
human reviews. A repair that changed media requires fresh technical/frame
evidence; an explanation of a resolved finding does not excuse stale hashes.

```powershell
python scripts\review_production.py accept PATH_TO_MANIFEST `
  --record review.json --evidence human-review.json `
  --teaching-contract examples\ddtree_full\teaching.json `
  --teaching-validation teaching-validation.json `
  --output review.accepted.json
python scripts\review_production.py verify PATH_TO_MANIFEST --record review.accepted.json
```

The teaching flags attach the optional machine-readable contract evidence;
explicit teaching review is required regardless. The acceptance action
requires the attached envelope to have status `passed`, a matching run ID,
the exact contract and reviewed-timeline hashes, and
`validation.valid: true` with no errors. A raw validator report, a legacy
envelope without the managed run ID, or validation of another timeline is
insufficient. The acceptance action preserves `review.json` and refuses to
overwrite an existing accepted output.
If `--output` is omitted, its default is `RECORD_STEM.accepted.json`.

Both `accept` and `verify` independently rerun `teaching.validate_contract`
against the actual bound contract and timeline. Semantic, beat, or shape errors
are rejected even if a supplied envelope claims `valid: true`. The accepted
record retains the result under `teaching.recomputed_validation`, including
source/event omissions. Recomputing deterministic checks does not establish
source entailment, perceptual fidelity, or human comprehension; those evidence
limits and explicit review requirements remain.

Keep the accepted record, original technical review, human evidence, teaching
files when supplied, video, timeline, index, and JPEGs. `verify` rechecks their
bindings, frame coverage, actual media decoding/durations, and declared human
evidence. Missing or stale files fail verification; never delete evidence
merely because the accepted JSON exists.

Draft runs can also have explicit acceptance records for their draft scope.
That does **not** make a silent accepted draft a narrated production delivery.
Select the intended profile/accounting scope explicitly when reporting results.

## Standalone frame extraction

For a direct-Manim run or targeted investigation:

```powershell
python scripts\extract_narration_frames.py `
  PATH_TO_VIDEO PATH_TO_TIMELINE NEW_EMPTY_FRAME_DIRECTORY --max-frames 512
```

The extractor adds first/final usable frames and before/after samples around
all block boundaries and declared visual events to three samples per block.
Duplicate times retain their provenance. It fails explicitly when the frame
plan exceeds the chosen cap or media/frames are missing or corrupt, rather
than silently skipping required evidence. Split investigation deliberately or
raise the cap knowingly; do not claim complete review from a truncated plan.

Valid legacy timelines are supported. Present IDs must be nonblank; omit
optional absent fields rather than writing `null`. Indices must be sequential
from zero, timestamps finite and ordered, and durations positive/consistent.
Standalone extraction is not acceptance and does not create a managed render
manifest for a direct-Manim video.
