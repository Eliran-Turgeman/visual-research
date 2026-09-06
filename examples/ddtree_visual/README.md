# DDTree Visual Explainer — Standalone Episode

A focused visual episode that continues directly from the DFlash episode
and teaches how DDTree turns cheap parallel draft marginals into a
multi-path verification tree.

## Teaching target

By the end, an engineer with rusty math should understand:
1. Why a single argmax path wastes useful draft probability.
2. How DDTree spends a fixed node budget on highest-mass prefixes
   under factorized DFlash marginals.
3. How the same tree nodes are flattened and verified with
   ancestor-only attention in one target pass.
4. Why only the **target's** chosen path is committed.

## Visual thesis

The same three probability columns from DFlash remain on screen.
A failed single path exposes unused probability; that probability
physically flows into alternative branches.  Seven best-first
selections grow one persistent tree.  The exact same node objects
straighten into a flat target input; tree edges light corresponding
ancestry cells; then the target lights one path and those nodes
move into the committed ribbon.

## Files

| File | Role |
|------|------|
| `storyboard.py` | Beat sheet / narration text / computed algorithm data |
| `scene.py` | Cinematic Manim scene (one continuous visual world) |
| `README.md` | This file |

## Rendering

```bash
# Silent review animatic (480p, no TTS)
manim render -ql scene.py DDTreeVisualExplainer

# With OpenRouter TTS
OPENROUTER_API_KEY=... manim render -qm scene.py DDTreeVisualExplainer

# Extract review frames
python scripts/extract_narration_frames.py \
    media/videos/scene/480p15/DDTreeVisualExplainer.mp4 \
    media/review/ddtree_visual/timeline.json \
    media/review/ddtree_visual/
```

## Dependencies

- Shared marginals and algorithm from `examples/ddtree_dflash/algorithm.py`
- Visual design system from `manim_lib/`
- Narration base class: `manim_lib/narrated_scene.py`
- Continuity from DFlash episode: same semantic colors, same distributions

## Semantic colors

| Role | Color |
|------|-------|
| Committed / accepted | `SUCCESS.base` (green) |
| Speculative / draft | `PRIMARY.base` (blue) |
| Target decisions | `ACCENT.base` (orange) |
| Bonus token | `#e8d44d` (yellow) |
| Rejected | `DANGER.base` (red) |
