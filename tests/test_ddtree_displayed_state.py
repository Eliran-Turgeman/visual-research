"""Regressions against executed Manim animations, not scene source strings."""

from decimal import Decimal
import importlib.util
from itertools import product
from math import prod
from pathlib import Path
import re
import sys

from manim import MathTex, tempconfig
import numpy as np
import pytest

from manim_lib.layout import assert_no_overlaps, contains, within_safe_frame
from manim_lib.tokens import TokenBox, TokenState


_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _load_scene(example):
    path = _EXAMPLES / example / "scene.py"
    spec = importlib.util.spec_from_file_location(f"{example}_display_test", path)
    module = importlib.util.module_from_spec(spec)
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(path.parent))
        for name in ("algorithm", "storyboard"):
            patch.delitem(sys.modules, name, raising=False)
        try:
            spec.loader.exec_module(module)
        finally:
            for name in ("algorithm", "storyboard"):
                sys.modules.pop(name, None)
    return module


class _RecordDisplayedState:
    def setup(self):
        super().setup()
        self.displayed_equations = []
        self.displayed_tokens = []

    def play(self, *animations, **kwargs):
        super().play(*animations, **kwargs)
        family = self.get_mobject_family_members()
        self.displayed_equations.extend(
            tuple(mob.tex_strings) for mob in family if isinstance(mob, MathTex)
        )
        self.displayed_tokens.append([
            (mob.token, mob.label.text, mob.state, tuple(mob.get_center()))
            for mob in family if isinstance(mob, TokenBox)
        ])


@pytest.fixture(scope="module")
def executed_scenes(tmp_path_factory):
    media = tmp_path_factory.getbasetemp() / "ddtree_display"
    media.mkdir()
    dflash_module = _load_scene("ddtree_dflash")
    visual_module = _load_scene("ddtree_visual")

    class DFlashMath(_RecordDisplayedState, dflash_module.DDTreeDFlashExplainer):
        def construct(self):
            self.marginals_not_conditionals()

    class Visual(_RecordDisplayedState, visual_module.DDTreeVisualExplainer):
        def _beat_1_tree_root_and_depth_one(self):
            super()._beat_1_tree_root_and_depth_one()
            self.depth_one_label_opacities = {
                key: node.label.get_fill_opacity()
                for key, node in self._tree.nodes.items()
            }

        def _beat_5_flatten(self):
            self.nodes_before_flatten = dict(self._tree.nodes)
            self.widths_before_flatten = {
                key: node.circle.width for key, node in self._tree.nodes.items()
            }
            super()._beat_5_flatten()
            self.flat_centers = {
                key: node.circle.get_center().copy()
                for key, node in self._flat_node_refs.items()
            }
            self.flat_widths = {
                key: node.circle.width for key, node in self._flat_node_refs.items()
            }
            self.flat_family = self.get_mobject_family_members()

        def _beat_8_commit(self):
            self.ribbon_positions_before_commit = [
                box.get_center().copy() for box in self._ribbon
            ]
            self.commit_snapshot_start = len(self.displayed_tokens)
            super()._beat_8_commit()

    with pytest.MonkeyPatch.context() as patch, tempconfig({
        "dry_run": True,
        "skip_animations": True,
        "quality": "low_quality",
        "media_dir": str(media),
        "verbosity": "ERROR",
        "progress_bar": "none",
    }):
        patch.setenv("MANIM_TTS_PROVIDER", "none")
        dflash = DFlashMath()
        dflash.render()
        visual = Visual()
        visual.review_timeline_path = media / "timeline.json"
        visual.render()
    return dflash, visual, visual_module


def test_every_revealed_factorization_is_a_valid_prefix_joint(executed_scenes):
    scene, _, module = executed_scenes
    equations = list(dict.fromkeys(
        parts[0] for parts in scene.displayed_equations
        if len(parts) == 1 and parts[0].startswith("Q(")
    ))
    assert len(equations) == 3
    marginals = [module.Q1, module.Q2, module.Q3]
    for equation, depth in zip(equations, (1, 2, 3)):
        lhs, rhs = equation.split("=")
        variables = re.findall(r"y_(\d)", lhs)
        factors = re.findall(r"q_(\d)\(y_(\d)\)", rhs)
        assert variables == [str(i) for i in range(1, depth + 1)]
        assert factors == [(i, i) for i in variables]
        # Marginalize the full joint independently over all suffixes.
        for prefix in product(*marginals[:depth]):
            lhs_mass = sum(
                prod(marginal[token] for marginal, token in zip(marginals, path))
                for suffix in product(*marginals[depth:])
                for path in [prefix + suffix]
            )
            rhs_mass = prod(
                marginals[int(i) - 1][prefix[int(j) - 1]]
                for i, j in factors
            )
            assert lhs_mass == pytest.approx(rhs_mass)


def test_displayed_products_use_exact_or_approximate_relations(executed_scenes):
    _, scene, module = executed_scenes
    equations = list(dict.fromkeys(
        parts for parts in scene.displayed_equations
        if len(parts) == 5 and parts[1] == r"\times"
    ))
    prefixes = [
        prefix for prefix in module.best_first_prefixes(
            [module.Q1, module.Q2, module.Q3], budget=module.NODE_BUDGET,
        ) if prefix.depth > 1
    ]
    assert len(equations) == len(prefixes) == 5
    marginals = [module.Q1, module.Q2, module.Q3]
    for parts, prefix in zip(equations, prefixes):
        parent_mass = prod(
            Decimal(str(marginal[token]))
            for marginal, token in zip(marginals, prefix.path[:-1])
        )
        marginal = Decimal(str(marginals[prefix.depth - 1][prefix.token]))
        exact_mass = parent_mass * marginal
        left, _, right, relation, displayed = parts
        assert Decimal(left) == parent_mass
        assert Decimal(right) == marginal
        assert Decimal(displayed) == exact_mass.quantize(Decimal(".001"))
        assert relation == ("=" if Decimal(displayed) == exact_mass else r"\approx")
        assert scene._node_masses[prefix.key] == pytest.approx(float(exact_mass))


def test_flatten_preserves_nodes_and_executes_both_move_and_scale(executed_scenes):
    _, scene, module = executed_scenes
    assert all(opacity > 0.9 for opacity in scene.depth_one_label_opacities.values())
    assert scene._dist_group not in scene.flat_family
    assert scene._dist_labels not in scene.flat_family
    for key, position in zip(module.FLATTEN_ORDER, scene._flat_positions):
        assert scene._flat_node_refs[key] is scene.nodes_before_flatten[key]
        np.testing.assert_allclose(scene.flat_centers[key], position, atol=1e-6)
        assert scene.flat_widths[key] == pytest.approx(
            scene.widths_before_flatten[key] * 0.85,
        )


def test_narrated_objective_is_expected_depth_under_q_not_target_acceptance(
    executed_scenes,
):
    _, scene, module = executed_scenes
    narration = scene._review_blocks[1]["text"]
    assert "factorized draft distribution Q" in narration
    assert "draft-model proxy" in narration
    assert "not a target acceptance guarantee" in narration
    marginals = [module.Q1, module.Q2, module.Q3]
    paths = {prefix.path for prefix in module.PREFIXES}
    expected_depth = sum(
        prod(q[token] for q, token in zip(marginals, path))
        * sum(path[:depth] in paths for depth in range(1, len(path) + 1))
        for path in product(*marginals)
    )
    assert expected_depth == pytest.approx(sum(
        mass for key, mass in scene._node_masses.items() if key != "root"
    ))
    assert expected_depth != pytest.approx(len(scene._verified_keys))


def test_narrated_flatten_order_matches_real_insertion_order(executed_scenes):
    _, scene, _ = executed_scenes
    assert "insertion order" in scene._review_blocks[5]["text"]
    assert tuple(scene._flat_node_refs) == tuple(scene.nodes_before_flatten)


def test_commit_displays_the_exact_target_sequence_without_old_masks(executed_scenes):
    _, scene, _ = executed_scenes
    visible = [
        mob for mob in scene.get_mobject_family_members()
        if isinstance(mob, TokenBox)
    ]
    visible.sort(key=lambda box: box.get_x())
    assert [box.label.text for box in visible] == ["...", "well", "a", "model", "runs"]
    assert [box.token for box in visible] == [box.label.text for box in visible]
    assert list(scene._ribbon) == visible
    assert [box.state for box in visible] == [
        TokenState.NEUTRAL, TokenState.ACCEPTED,
        TokenState.ACCEPTED, TokenState.ACCEPTED, TokenState.ACTIVE,
    ]
    for box, position in zip(visible, scene.ribbon_positions_before_commit):
        np.testing.assert_allclose(box.get_center(), position, atol=1e-6)
        assert contains(box.box, box.label)
        assert within_safe_frame(box)
        assert box.inner_border.get_fill_opacity() == 0
    assert_no_overlaps(visible)
    # Check the executed transition too: a new bonus may never coexist
    # with an old proposal placeholder in the committed ribbon.
    for snapshot in scene.displayed_tokens[scene.commit_snapshot_start:]:
        if any(token == "runs" for token, _, _, _ in snapshot):
            assert all(token != "?" for token, _, _, _ in snapshot)
