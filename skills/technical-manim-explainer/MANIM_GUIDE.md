# Manim Implementation Guide

These are house conventions for technical explainers, not an API reference.
Use semantic objects, stable layouts, and animations whose visual meaning
matches the technical operation.

## Object and animation semantics

- Use `MathTex` for mathematics, `Tex` for LaTeX prose, and `Text` when LaTeX
  is unnecessary.
- Group related objects with `VGroup` and move, scale, or align the group.
- `Create` and `Write` introduce a new concept.
- `Transform`, `ReplacementTransform`, and `TransformMatchingTex` communicate
  continuity or equivalence. Prefer `TransformMatchingTex` for derivations with
  shared terms.
- `MoveToTarget` communicates a planned relocation while preserving identity.
- `FadeOut` means an object leaves the current state; do not use it merely to
  avoid implementing a meaningful transform.
- Use `AnimationGroup` for coordinated actions and `LaggedStart` when sequence
  or accumulation matters. Avoid animating many unrelated things at once.

An equation derivation should normally transform shared terms in place. Do not
make one equation disappear and introduce an unrelated-looking replacement.

## Layout

Prefer `next_to`, `align_to`, `arrange`, and `arrange_in_grid` over chains of
hard-coded `.shift()` calls. Establish stable regions, such as context at the
top, the mechanism in the center, and a small conclusion at the bottom.

Conceptual identity implies spatial stability. A request, token, tree node, or
matrix tile should remain in the same location while its state changes unless
movement itself is the point. Build at final scale where possible and check
frame boundaries after labels are added.

## Trees

- Increase depth in one consistent direction, normally downward.
- Give siblings predictable spacing and preserve existing node positions during
  expansion.
- Add new nodes and edges without recomputing the entire layout when that would
  move established nodes.
- Put scores and probabilities beside the node or edge they describe; never
  leave association to guesswork. `TreeNode` auto-shrinks its label to stay
  inside the circle and accepts a configurable `score_direction` (for example
  `DOWN` instead of the default `RIGHT`) so a score can be moved out of a
  crowded neighbor's way instead of colliding with it; call `set_score` again
  to move or update a score in place without rebuilding the node.
- Highlight the active path, frontier, accepted branch, or pruned subtree
  instead of moving the whole tree.
- Use color and stroke changes for transient state, and explain their meaning
  the first time.

For speculative decoding and DDTree, maintain stable token-node identity across
proposal, verification, acceptance, and rejection.

## Token sequences

- Draw tokens as fixed-height boxes with text centered inside.
- Keep sequence order in one direction and use stable spacing.
- Distinguish states consistently: neutral context, speculative candidate,
  accepted token, rejected token, and current focus.
- Display candidate probability close to its token; align multiple candidates
  in a compact row or column.
- For autoregressive generation, append one token at a time and keep the prefix
  fixed.
- Do not use unexplained colors. Add a short legend only when several states
  coexist.

## Matrices and tensors

- Use fixed-size cells so changing values do not change geometry.
- Label rows, columns, axes, and tensor dimensions outside the data region.
- Use translucent overlays for cells, rows, columns, or tiles.
- Show shape annotations near the object, for example `Q: N x d`.
- Progress through matrix operations by highlighting the current operands and
  destination, not by displaying a full derivation at once.
- For memory movement, use distinct stable regions for memory levels and move a
  labeled tile or data packet between them. Keep compute and storage visually
  distinct.

## Equations

Introduce one relation at a time. Keep equations large enough to read and move
secondary annotations away from the expression. Prefer
`TransformMatchingTex` so matching terms retain continuity. For long
derivations, keep the important invariant or current line visible and retire
completed detail. Verify generated LaTeX before rendering the full scene.

## Camera

Use camera movement only to communicate focus, scale, spatial relationship, or
a transition to a genuinely different region. Do not pan or zoom merely to add
motion. Prefer a stable camera and local emphasis for most explainers.

## Voiceover synchronization

Use `manim-voiceover` when the selected speech service is available. Keep each
voiceover block to one semantic unit and place its corresponding animations
inside that block. Use the block's duration to budget animation and pauses.

For final narration, prefer the repository's OpenRouter service with
`microsoft/mai-voice-2` and `en-US-Harper:MAI-Voice-2`. Keep the voice near its
default speed and use style controls sparingly; clear scripting and meaningful
pauses matter more than exaggerated delivery. Use silent mode or gTTS only for
draft timing.

Do not attach a 30-60 second paragraph to one block. Do not stretch a trivial
fade for the duration of a long explanation. Instead, split the narration and
add meaningful progressive emphasis, intermediate states, or annotations.
Silent fallback should preserve the same block boundaries and approximate
timing so it remains useful for development.

## Anti-patterns

- walls of text or PowerPoint-like slides disguised as animation;
- recreating objects that should transform;
- too many simultaneous animations;
- teleporting objects or changing layout without conceptual meaning;
- excessive camera movement;
- arbitrary hard-coded coordinates;
- tiny labels and low-contrast annotations;
- distinctions encoded visually but never explained;
- decorative animation with no explanatory purpose;
- narration describing a state before it appears or after it has disappeared.

---

## Visual art direction

These principles govern the cinematic visual identity of every explainer.  Use
the design system in `manim_lib.theme`, `manim_lib.focus`, and
`manim_lib.composition` to implement them consistently.

### Stage and background

Use the near-black background (`theme.BACKGROUND`, `#1a1a2e`).  The dark stage
maximizes perceived contrast and lets color carry meaning instead of decoration.
Do not use white, gray, or colored backgrounds.

### Semantic color roles

Every color on screen must serve a semantic purpose.  Use the five role colors
from `manim_lib.theme`:

| Role        | When to use                                     |
|-------------|--------------------------------------------------|
| `PRIMARY`   | Main subject, active element, current step       |
| `ACCENT`    | Secondary callout, supporting highlight, annotation |
| `SUCCESS`   | Accepted, correct, verified                      |
| `DANGER`    | Rejected, error, pruned, failed                  |
| `NEUTRAL`   | Inactive context, background structure, borders  |

Each role has `.base`, `.light`, and `.dim` tonal variants.  Use `.light` for
emphasis on the dark stage, `.dim` for de-emphasized but still-visible context,
and `.base` for the default weight.  Never introduce ad-hoc hex colors—if a new
semantic need arises, extend the theme.

### Typography hierarchy

Use exactly three levels—heading, body, caption—from `theme.TYPOGRAPHY`.  A
heading introduces a concept; body text is the primary explanatory level;
captions annotate, label, or provide secondary detail.  Do not create
intermediate sizes.  Prefer `Text` for labels and `MathTex` for mathematics;
avoid `Tex` prose unless LaTeX formatting is genuinely needed.

### Stroke hierarchy

Use `theme.STROKES`: heavy for primary structure, normal for secondary edges,
hairline for guides and connectors.  Consistent stroke weight communicates
visual depth without shadow effects.

### Spacing vocabulary

Use the five named constants from `theme.SPACING` (`xs`, `sm`, `md`, `lg`,
`xl`) for all `buff`, gap, and margin values.  Consistent spacing replaces
magic numbers and makes layouts predictable across scenes.

### Center-weighted composition

Default to a single evolving picture centered on the frame.  Use
`composition.center_group()` to stack elements vertically or
`composition.side_by_side()` for explicit comparisons.  Use
`composition.place_at_safe_edge()` instead of `.to_edge()` to respect safe
margins.  Avoid multi-panel grid layouts unless genuinely comparing two or more
independent things.

### When panels are justified

Panels (titled rectangular regions) are acceptable only when the scene genuinely
requires comparison of two or more independent structures—never to organize
sequential content.  If you can present the content as one evolving picture,
do that instead.

### Focus and dimming

Use `focus.focus_on()` to semantically dim context and `focus.restore_focus()`
afterward.  Use `composition.dim_overlay()` only for full-frame context push
(such as temporarily bringing a detail to the foreground).  Never dim for
decoration.

### The "earn your place" rule

Every visible element—every label, every border, every color, every animation
step—must earn its place.  Ask: "Does removing this hurt understanding?"  If
not, remove it.  Decorative animation, ornamental borders, gratuitous panels,
and redundant labels all fail this test.

---

## Hard gates before calling a draft done

These are non-negotiable checks, not suggestions. A scene fails review if any
of them fail, regardless of how correct the underlying technical content is.

1. **Narrated computations must be visible, not just their answer.** If
   narration describes computing something (a product, a sum, a lookup, a
   comparison), the animation must show the operands, the operation, the
   result, and what the result means, in that order. A number that simply
   appears (or is only ever shown pre-computed) fails this gate even if the
   narration says the right words. Use `manim_lib.computation.Computation` /
   `Operand` to build the equation and interpretation as separate, reusable
   mobjects instead of hand-writing a one-off `Text`/`MathTex` per scene: it
   keeps the displayed (possibly rounded) value and the exact value both
   available, and gives you addressable operand/result submobjects for
   `TransformFromCopy`-style hookups (for example, connecting a computed
   result directly to the node or cell it produces).
2. **Draft review must sample the start, middle, and end of every narration
   block**, not only the final frame of a scene. A block that looks fine at
   its last frame can still have raced, overlapping, or empty intermediate
   states; check at least one frame near the beginning and one near the
   middle of each `with self.narrate(...)` block in addition to its end.
   This is a required step before calling a draft done, not an optional
   nicety: any scene whose narration bookkeeping follows the
   `DDTreeDFlashExplainer.narrate`/`_write_review_timeline` pattern (record
   each block's actual rendered start/end and text, then write them to
   `media/review/<scene>/timeline.json` after a successful `construct()`)
   can be reviewed with the repository's general-purpose extraction script,
   independent of which TTS provider (or the silent fallback) produced the
   render:

   ```powershell
   .\.venv\Scripts\python.exe scripts\extract_narration_frames.py `
     media\videos\scene\480p15\<Scene>.mp4 `
     media\review\<scene>\timeline.json `
     media\review\<scene>\frames
   ```

   It extracts near-start/mid/near-end JPEGs for every block (clamped inside
   the block and the scene, never on an exact boundary), writes an
   `index.json` mapping each frame back to its block's timestamp and
   narration text, and assembles contact-sheet images for a quick full-render
   skim. Run it against a silent `-ql` draft while iterating and again on the
   final render before calling the explainer done.
3. **Collision, overflow, and readability are checked, not eyeballed.** Before
   treating a layout as final, validate it with
   `manim_lib.layout` (`bounding_box`, `boxes_overlap`, `mobjects_overlap`,
   `find_overlaps`, `contains`, `within_safe_frame`,
   `assert_within_safe_frame`, `assert_no_overlaps`): confirm labels stay
   inside the shapes that contain them (`contains`), confirm nothing
   unintentionally overlaps a neighbor (`find_overlaps`, mindful that
   intentional containment, such as content inside its own panel, should be
   checked with `contains` rather than flagged as a collision), and confirm
   every on-screen group stays within the safe frame
   (`within_safe_frame`/`assert_within_safe_frame`). These are plain
   functions over mobjects and bounding boxes; write a short throwaway
   validation script per scene rather than trusting a render preview alone,
   and use `bounding_box_overlay` to visualize a suspect region if a
   numeric check alone is hard to interpret. Prefer fixing the root cause
   (spacing, an auto-fit label, a configurable score direction) over shrinking
   text until it happens to fit.
4. **Do a full final playback**, silent draft quality is enough, of the whole
   scene end to end before considering it done. Spot checks catch most
   problems, but only a full playback catches pacing drift, a leftover
   mobject from an earlier section, or a transition that only breaks in
   sequence.
