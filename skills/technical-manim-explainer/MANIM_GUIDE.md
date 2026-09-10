# Manim Implementation Guide

These are house conventions for technical explainers, not an API reference.
Use semantic objects, stable layouts, and animations whose visual meaning
matches the technical operation.

For the stage-specific workflow, load the [teaching contract](references/teaching-contract.md)
before storyboarding, [narration guidance](references/narration.md) before
synthesis, and [production review](references/production-review.md) before
acceptance. This guide covers implementation, not an autonomous agent framework.

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

- For a token ribbon, use fixed-height boxes with text centered inside. When
  tokens are events on a timeline, use labeled markers instead: their position
  communicates availability. Choose the representation for the explanation,
  not because every token must be a box.
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

Choose narration explicitly. For final narration, the repository's OpenRouter
reference uses
`microsoft/mai-voice-2` and `en-US-Harper:MAI-Voice-2`. Keep the voice near its
default speed and use style controls sparingly; clear scripting and meaningful
pauses matter more than exaggerated delivery. Audition difficult terms with the
same supported provider/model/voice controls before full synthesis. Use silent
mode for rough motion and explicit gTTS when useful for networked speech drafts.
See the narration reference for cache recovery and AI-voice disclosure.

Do not attach a 30-60 second paragraph to one block. Do not stretch a trivial
fade for the duration of a long explanation. Instead, split the narration and
add meaningful progressive emphasis, intermediate states, or annotations.
Silent fallback should preserve the same block boundaries and approximate
timing so it remains useful for development.

## Continuity primitives

Build visual explanations as one evolving picture.  Use the helpers in
`manim_lib.probability` and `manim_lib.continuity` to connect stages with
identity-preserving animations rather than clearing and rebuilding.

### Probability distributions

Use `ProbabilityDistribution` for any named probability column.  Entries are
keyed, expose `.token_anchor`, `.value_anchor`, `.highlight_anchor`, and
survive across animation phases.

```python
from manim_lib.probability import ProbabilityDistribution, animate_mass_transfer

dist = ProbabilityDistribution({"a": ("A", 0.5), "b": ("B", 0.3)})
self.play(FadeIn(dist))
# Transfer mass from entry into a tree node:
anim = animate_mass_transfer(dist.entries["a"], child_node)
self.play(anim)
```

Do **not** build ad-hoc `Text`/`Rectangle` groups for probability columns.
Do **not** hard-code token names — pass them from the caller's data.

### Branch growth

Use `grow_branch` to add a child node and edge to a `StableTree` with a single
call.  It registers the node/edge immediately and returns animations:

```python
from manim_lib.continuity import grow_branch

anims, edge = grow_branch(tree, "root", "child", child_node, (x, y, 0), label="0.5")
self.play(*anims)
```

Do **not** manually call `tree.add_node` + `tree.connect` + build separate
animations when `grow_branch` covers the case.

### Tree → sequence mapping

Use `map_tree_to_sequence` to transform tree nodes into an ordered token
sequence.  The caller must provide the explicit key-to-index mapping:

```python
from manim_lib.continuity import map_tree_to_sequence

anims = map_tree_to_sequence(tree, {"root": 0, "x": 1, "y": 2}, sequence)
self.play(*anims)
```

The function validates duplicate indices, missing keys, and out-of-range
indices.  Do **not** silently infer ordering — always provide the explicit map.

### Ancestry → mask mapping

Use `map_ancestry_to_mask` to highlight matrix cells corresponding to tree
ancestor relationships, making the connection visible rather than revealing a
matrix independently:

```python
from manim_lib.continuity import map_ancestry_to_mask

parent_map = {"root": None, "A": "root", "B": "root"}
anims, overlays = map_ancestry_to_mask(parent_map, matrix, node_to_index)
self.play(*anims)
```

Pass `include_self=False` if diagonal cells should not be highlighted.  The
function is generic over any tree parent map and `LabeledMatrix`.

### Semantic focus

Use `semantic_focus` / `restore_semantic_focus` for purposeful emphasis with
safe restoration.  This composes `focus_on` with an optional dim overlay:

```python
from manim_lib.continuity import semantic_focus, restore_semantic_focus

anims, ctx, overlay = semantic_focus(target, [target, other], use_overlay=True)
self.play(*anims)
# ... focused phase ...
self.play(*restore_semantic_focus([target, other], ctx, overlay))
```

Do **not** create decorative camera motion for emphasis.

### Section transition

Use `section_transition` when changing chapters while preserving a visual anchor:

```python
from manim_lib.continuity import section_transition

self.play(*section_transition(anchor=tree, others=[dist, label]))
```

The anchor is automatically excluded from the fade/dim list.  Use
`fade_out=False` to dim instead of removing.

### Continuity anti-patterns

- Clearing the scene and rebuilding objects from scratch between stages.
- Revealing a matrix independently instead of connecting it to the structure
  that produces it.
- Using `FadeOut` + `FadeIn` when a `TransformFromCopy` or mass transfer would
  preserve continuity.
- Hard-coding DDTree-specific token names in library calls.
- Inferring tree-to-sequence ordering instead of providing an explicit map.

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

### Build a visual grammar, not decorated slides

The aesthetic target is a crafted visual explanation: abstract ideas should
feel like tangible objects with consistent material, weight, and behavior.
Beauty comes from clarity, rhythm, and transformation—not from adding more
panels, labels, gradients, or camera moves.

Before implementing a scene, define its small visual vocabulary:

- the relationship the final picture must reveal without a headline;
- one hero representation that carries the mechanism;
- only the supporting object types needed to make that relationship visible;
- one visual treatment for inactive context;
- one treatment for the current operation;
- one treatment each for accepted and rejected outcomes when needed.

Reuse those exact treatments throughout the scene. A token must not look like
a plain rectangle in one beat and a glossy card in the next. A probability
must not alternate between text, a bar, and an arbitrary badge unless the
transition itself explains that change of representation.

Design the payoff before choosing library components. Sketch the opening,
mechanism, and payoff compositions; then render a rough silent animation.
Polish cannot rescue a picture that only labels the idea rather than explains
it. Reuse semantic helpers where appropriate, but do not force a concept into
the shape of an existing component.

### Reference: speculative decoding latency

`examples/speculative_decoding_timeline/scene.py` replaces the model-box flowchart with a
single shared clock. The close-up shows one target pass completing before a
token appears. That same picture contracts to reveal a chain of dependent
passes. Below it, short sequential draft steps feed one target interval
spanning all proposed positions. The same outlined token markers become solid
at completion; an endpoint bracket reveals the saved time before a caption.

The representation contract is explicit:

| Visual property | Meaning |
|---|---|
| Horizontal distance | Illustrative elapsed time, identical scale in both lanes |
| Width of a work interval | Duration, including drafting overhead |
| Moving boundary | Progress of the current operation |
| Outline / solid marker | Proposed / accepted token |
| Vertically separated verification rows | Token positions evaluated in one pass, not serial passes |
| Completion guides and bracket | Difference between prefix availability times |

Do not mistake screen animation duration for measured algorithm latency.
Camera reframing and explanatory holds are presentation time; the shared
horizontal geometry represents the declared toy cost model. Keep standard
speculative drafting sequential unless a block-parallel drafter is explicitly
introduced. Mark an all-accepted example as conditional, never a guaranteed
speedup; do not silently omit draft work or imply every proposal is accepted.

### Stage and background

Use the deep blue-black background (`theme.BACKGROUND`, `#0b1020`). The dark stage
maximizes perceived contrast and lets color carry meaning instead of decoration.
Do not use white, gray, or colored backgrounds.

Use `theme.SURFACE` and `theme.SURFACE_ELEVATED` for the bodies of technical
objects. This creates a restrained foreground/background hierarchy while
keeping semantic colors free to communicate meaning. Do not fill every object
with its role color at full opacity; reserve saturated color for the active
edge, current value, or state change.

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

Use three semantic levels—heading, body, caption—with `theme.TYPOGRAPHY` as
the starting scale. A
heading introduces a concept; body text is the primary explanatory level;
captions annotate, label, or provide secondary detail. Keep those roles
consistent. A scene-local type pairing may need optical size adjustments
because serif and sans-serif letters at the same point size have different
visible heights; document that choice instead of adding arbitrary hierarchy
levels. Prefer `Text` for labels and `MathTex` for mathematics;
avoid `Tex` prose unless LaTeX formatting is genuinely needed.

Headings should be short enough to read as a shape, not a sentence. Prefer
sentence case. Keep text blocks narrow; when narration can carry a statement,
show only the exact noun, value, or invariant the viewer needs as an anchor.

### Object craftsmanship

Technical objects should look intentionally designed even when static:

- prefer softly rounded geometry for discrete objects such as tokens, cells,
  slots, and probability tracks;
- separate an object's dark body from its semantic edge or active fill;
- use a faint inner ring or secondary outline only when it clarifies the
  object's boundary at video resolution;
- treat shadows, inner borders, and halos as optional tools, not required
  layers on every object; flat geometry is preferable when it reveals the
  quantity or relationship more directly;
- fit labels inside their containers programmatically;
- align repeated numeric values to a stable track or column so changing a
  value does not cause the whole composition to breathe;
- keep connectors visually behind the objects they connect;
- use low-opacity halos only for current focus, never around every object.

The shared `TokenBox`, `TreeNode`, `LabeledMatrix`, and
`ProbabilityDistribution` are useful when those are the right representations.
Keep new representations scene-local until their semantics recur. Consistent
color and typography do not require identical shapes for different concepts.

### Motion rhythm

Motion has three beats: anticipation, action, and rest. The anticipation may be
as small as dimming context or highlighting operands; the action performs the
technical state change; the rest leaves the result stable long enough to read.

- introduce structure before detail: container/edge first, label/value second;
- show causal dependencies: finish a pass, expose its output, then start the
  dependent pass; preserve operands, tokens, and destinations through the
  operation instead of substituting a flash and a precomputed result;
- use `LaggedStart` for ordered accumulation, with a restrained lag ratio;
- use `TransformFromCopy` when a source contributes to a result;
- keep most state changes between roughly 0.4 and 1.2 seconds;
- save slower motion for a genuinely important conceptual transformation;
- add a short hold after dense changes, not after decorative entrances;
- make the decisive relationship visible before naming it in a caption;
- avoid elastic, bouncy, or spinning motion unless it encodes real behavior.

At any instant, the viewer should know where to look. If three unrelated
regions animate together, the choreography has failed even if each animation
looks polished in isolation.

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

Make the mechanism visually dominant. A useful starting composition gives it
roughly three-quarters of the usable width; this is a design target, not a
reason to stretch data geometry or shrink labels. Retire an opening headline
once the mechanism begins. Change scale only to reveal a dependency or a
comparison, and transform the continuing objects together. Do not solve an
overfull frame by globally shrinking it: remove content, shorten labels, or
split the explanation.

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

## Hard gates for drafts and production

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
   nicety. Record actual rendered start/end timestamps and text, then use
   the repository extraction workflow described in
   [production review](references/production-review.md). Add first/final frames
   and samples on both sides of major visual transitions; block sampling alone
   can miss transient defects. Use the run manifest's matching video/timeline,
   not files from different renders. Contact sheets and their timestamped index
   support review; they do not automatically approve a scene.
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
   functions over mobjects and bounding boxes; add focused repeatable checks
   for the scene rather than trusting a render preview alone,
   and use `bounding_box_overlay` to visualize a suspect region if a
   numeric check alone is hard to interpret. Prefer fixing the root cause
   (spacing, an auto-fit label, a configurable score direction) over shrinking
   text until it happens to fit.
4. **Do full playback at both stages.** Watch the complete silent rough cut
   for visual causality, then watch and listen to the complete final production
   artifact after the last repair. A silent draft is not sufficient to approve
   narrated production. Spot checks miss pacing drift, pronunciation, cutoffs,
   leftover objects, and transitions that only break in sequence. If full
   audiovisual review is unavailable, report it and leave acceptance pending.
5. **The picture must explain, not merely announce.** Review the rough cut
   without audio or its headline. Identify what visibly causes the next state,
   which objects persist, and which geometric relationship delivers the
   conclusion. Reject a model flash followed by a disconnected answer, a
   comparison with mismatched scales or missing overhead, and a final insight
   that exists only in a caption. This is a perceptual review, not a property
   that passing geometry assertions alone can establish.
6. **Bind acceptance to the reviewed artifact.** Use a bounded
   review → repair → validate loop with timestamped findings, separate
   technical/production/teaching criteria, and a review record linked to the
   current manifest and hashes. Neither a successful render nor agent
   confidence establishes acceptance; do not fabricate playback or learner
   evidence.
