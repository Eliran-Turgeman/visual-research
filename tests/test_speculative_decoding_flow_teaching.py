"""The executed flow must describe its depicted block-parallel drafter."""

from manim import Text, tempconfig
import pytest

from manim_lib.layout import contains
from manim_lib.tokens import TokenBox, TokenState

from test_ddtree_displayed_state import _load_scene


@pytest.fixture(scope="module")
def executed_flow(tmp_path_factory):
    module = _load_scene("speculative_decoding_flow")
    output = tmp_path_factory.getbasetemp() / "flow_teaching"

    class RecordedFlow(module.SpeculativeDecodingFlow):
        def setup(self):
            super().setup()
            self.snapshots = []
            self.model_label_fits = {}

        def _model(self, name, detail, color):
            model = super()._model(name, detail, color)
            self.model_label_fits[name] = contains(model[1], model[3])
            return model

        def play(self, *animations, **kwargs):
            super().play(*animations, **kwargs)
            family = self.get_mobject_family_members()
            self.snapshots.append({
                "block": len(self._review_blocks),
                "text": [mob.original_text for mob in family if isinstance(mob, Text)],
                "proposals": [
                    mob.token for mob in family
                    if isinstance(mob, TokenBox) and mob.state is TokenState.SPECULATIVE
                ],
            })

    with pytest.MonkeyPatch.context() as patch, tempconfig({
        "dry_run": True,
        "skip_animations": True,
        "media_dir": str(output),
        "verbosity": "ERROR",
        "progress_bar": "none",
    }):
        patch.setenv("MANIM_TTS_PROVIDER", "none")
        patch.delenv("MANIM_TIMELINE_PATH", raising=False)
        scene = RecordedFlow()
        scene.review_timeline_path = output / "timeline.json"
        scene.render()
    return scene


def test_executed_flow_explicitly_identifies_block_parallel_drafting(executed_flow):
    scene = executed_flow
    assert len(scene._review_blocks) == 8
    assert "block drafting" in scene._review_blocks[4]["text"]
    assert "autoregressive drafting" in scene._review_blocks[4]["text"]
    assert "block-drafting pass" in scene._review_blocks[5]["text"]
    assert any(
        "Block drafter" in snapshot["text"]
        for snapshot in scene.snapshots if snapshot["block"] == 4
    )
    assert scene.model_label_fits["Block drafter"]


def test_parallel_proposal_picture_is_preserved(executed_flow):
    proposal_states = [
        snapshot["proposals"] for snapshot in executed_flow.snapshots
        if snapshot["block"] == 5
    ]
    assert proposal_states == [["can", "reason", "fast"]]


def test_all_accepted_call_reduction_is_not_claimed_as_guaranteed_latency(
    executed_flow,
):
    blocks = executed_flow._review_blocks
    assert "all-accepted example" in blocks[6]["text"]
    assert "Drafting still takes time" in blocks[7]["text"]
    assert "not a guaranteed latency reduction" in blocks[7]["text"]
    assert any(
        "3 target calls" in text and "1 verification call" in text
        for snapshot in executed_flow.snapshots if snapshot["block"] == 7
        for text in snapshot["text"]
    )
