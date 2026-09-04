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
  leave association to guesswork.
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
