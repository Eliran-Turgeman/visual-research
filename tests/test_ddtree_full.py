"""The full episode uses algorithm-derived data and the real scene geometry."""

from itertools import product
from math import prod

import pytest
from manim import DOWN, Scene, VGroup

from examples.ddtree_full.scene import (
    DDTreeFullExplainer, DDTreePicture, FLAT_POSITIONS, FrontierView, PrefixNode,
    anchor_annotation, text,
)
from examples.ddtree_full.storyboard import (
    ACCEPTED, BEATS, BONUS, BUDGET, BY_KEY, DEPTHS, INDEX, MARGINALS,
    MASK, ORDER, PARENTS, PREFIXES, SELECTIONS, TARGET_CHOICES, VANILLA, WORDS,
    ancestry,
)
from manim_lib import (
    ACCENT, SUCCESS, Computation, Operand, assert_no_overlaps, assert_within_safe_frame,
)


def test_selected_prefixes_are_the_true_top_seven_of_all_39_prefixes():
    candidates = [
        (path, prod(MARGINALS[i][word] for i, word in enumerate(path)))
        for depth in range(1, 4)
        for path in product(*(tuple(q) for q in MARGINALS[:depth]))
    ]
    assert len(candidates) == 39
    expected = sorted(candidates, key=lambda entry: -entry[1])[:BUDGET]
    assert [prefix.path for prefix in PREFIXES] == [path for path, _ in expected]
    assert [prefix.mass for prefix in PREFIXES] == pytest.approx([mass for _, mass in expected])
    assert sum(prefix.mass for prefix in PREFIXES) == pytest.approx(1.8858)


def test_lazy_frontier_matches_every_pop_and_offers_no_more_than_two_candidates():
    for step in SELECTIONS:
        assert step.before[0].key == step.chosen.key
        assert step.before[0].mass == pytest.approx(step.chosen.mass)
        before_paths = {item.path for item in step.before}
        after_paths = {item.path for item in step.after}
        assert step.chosen.path not in after_paths
        assert len(after_paths - before_paths) <= 2
        assert len(after_paths) == len(step.after)
        for item in step.after:
            assert item.mass == pytest.approx(
                prod(MARGINALS[i][word] for i, word in enumerate(item.path))
            )
    assert SELECTIONS[1].before[0].path == ("a",)
    assert SELECTIONS[1].before[0].mass > SELECTIONS[1].before[1].mass


def test_budget_excludes_root_and_depth_is_not_flat_array_index():
    assert len(PREFIXES) == BUDGET == 7
    assert len(ORDER) == BUDGET + 1
    assert DEPTHS["the"] == DEPTHS["a"] == 1
    assert INDEX["the"] != INDEX["a"]
    assert all(prefix.parent in ORDER for prefix in PREFIXES)
    assert all(DEPTHS[prefix.key] == DEPTHS[prefix.parent] + 1 for prefix in PREFIXES)


def test_mask_exactly_encodes_self_and_ancestors_without_sibling_leakage():
    for key in ORDER:
        visible = {ORDER[column] for column, bit in enumerate(MASK[INDEX[key]]) if bit}
        assert visible == set(ancestry(key))
    assert ancestry("a-model-works") == ("root", "a", "a-model", "a-model-works")
    assert MASK[7][INDEX["the"]] == 0
    assert MASK[7][INDEX["the-model"]] == 0
    assert sum(sum(row) for row in MASK) == 22


def test_target_walk_emits_first_missing_target_token_and_reuses_two_drafts():
    key = "root"
    matches = []
    while key in TARGET_CHOICES:
        chosen = TARGET_CHOICES[key]
        children = [child for child in ORDER if PARENTS[child] == key]
        matching = next((child for child in children if WORDS[child] == chosen), None)
        if matching is None:
            assert chosen == BONUS
            break
        matches.append(matching)
        key = matching
    assert tuple(matches) == ACCEPTED
    assert [WORDS[key] for key in matches] == ["a", "model"]
    assert VANILLA[0] != TARGET_CHOICES["root"]


def test_tree_labels_and_scores_are_legible_external_objects_without_collisions():
    picture = DDTreePicture()
    for node in picture.nodes.values():
        node.attach_mass()
        assert node.word.font_size >= 25
        assert node.mass.font_size >= 19
        assert_within_safe_frame(node, margin=0.35)
        assert_no_overlaps([node.dot, node.word, node.mass])
    assert_no_overlaps(list(picture.nodes.values()))


def test_frontier_rows_fit_for_every_selection_without_shrinking():
    for i, step in enumerate(SELECTIONS):
        frontier = FrontierView(step.before, i)
        assert_within_safe_frame(frontier, margin=0.35)
        for row in frontier.rows.values():
            assert_no_overlaps(list(row))


def test_distribution_columns_share_bar_baselines_and_do_not_overlap():
    p = DDTreePicture()
    assert_within_safe_frame(p.dist_group, margin=0.35)
    assert_no_overlaps(p.distributions)
    for dist in p.distributions:
        left_edges = [entry.bar.get_left()[0] for entry in dist.entries.values()]
        assert left_edges == pytest.approx([left_edges[0]] * len(left_edges))


def test_tree_to_flat_layout_preserves_actual_node_and_word_objects():
    p = DDTreePicture()
    for key, node in p.nodes.items():
        node.attach_mass()
        marker, word, mass = node.dot, node.word, node.mass
        original_point = marker.get_center().copy()
        node.to_flat()
        assert node.dot is marker and node.word is word and node.mass is mass
        assert node.dot.get_center() == pytest.approx(FLAT_POSITIONS[key])
        assert_within_safe_frame(node, margin=0.35)
        node.to_tree()
        assert node.dot.get_center() == pytest.approx(original_point)
    for node in p.nodes.values():
        node.to_flat()
    assert_no_overlaps([VGroup(node.dot, node.word) for node in p.nodes.values()])
    assert_within_safe_frame(p.matrix, margin=0.35)
    assert_no_overlaps([p.matrix, p.slot_ids, p.position_ids])


def test_all_visible_numeric_products_match_the_chosen_prefixes():
    for prefix in PREFIXES:
        if prefix.depth == 1:
            continue
        calculation = Computation(
            Operand("parent", BY_KEY[prefix.parent].mass),
            Operand("marginal", MARGINALS[prefix.depth - 1][prefix.token]),
        )
        assert calculation.exact_result == pytest.approx(prefix.mass)
        equation = calculation.build_equation(font_size=36).move_to((-0.8, -3.05, 0))
        assert_within_safe_frame(equation, margin=0.35)


def test_complete_objective_sum_fits_and_displays_1886_not_one_probability():
    computation = Computation(
        *[Operand(p.key, p.mass, tex=f"{p.mass:.4f}".rstrip("0")) for p in PREFIXES],
        operator="+", exact_result=sum(p.mass for p in PREFIXES),
    )
    equation = computation.build_equation(font_size=32).move_to((0, -3, 0))
    assert computation.result_display == "1.886"
    assert equation[-2].tex_string == r"\approx"
    assert_within_safe_frame(equation, margin=0.35)


def test_final_old_anchor_is_not_marked_as_an_accepted_speculative_node():
    root, accepted = PrefixNode("root"), PrefixNode("a")
    root.output_at(-3.3)
    accepted.output_at(-1.5)
    assert root.dot.get_fill_color().to_hex().lower() == ACCENT.base.lower()
    assert accepted.dot.get_fill_color().to_hex().lower() == SUCCESS.light.lower()
    assert root.mass not in root.submobjects


def test_final_anchor_arrow_never_crosses_the_word_or_caption():
    node = PrefixNode("a")
    node.output_at(3.1)
    word = text(BONUS, 26, serif=True).next_to(node.dot, DOWN, buff=0.18)
    label, arrow = anchor_annotation(word)
    assert_no_overlaps([node.dot, word, arrow, label])
    assert_within_safe_frame(VGroup(node.dot, word, arrow, label), margin=0.35)


def test_relayout_keeps_visible_words_separated_throughout_both_transitions():
    picture = DDTreePicture()
    scene = Scene()
    scene.add(*picture.nodes.values())
    for key, node in picture.nodes.items():
        if key != "root":
            node.attach_mass()
        node.mass.set_opacity(0)
    for flat in (True, False):
        animation = picture.relayout(flat=flat)
        animation._setup_scene(scene)
        animation.begin()
        for step in range(161):
            animation.interpolate(step / 160)
            visible = []
            for key, node in picture.nodes.items():
                parts = VGroup(node.dot, node.word)
                if key != "root" and node.mass.get_fill_opacity() > 0.15:
                    parts.add(node.mass)
                visible.append(parts)
            assert_no_overlaps(
                visible, labels=[f"{key} (flat={flat}, step={step})" for key in ORDER],
            )
            for group in visible:
                assert_within_safe_frame(group, margin=0.35)
        animation.finish()


def test_full_episode_has_no_unqualified_target_acceptance_objective():
    assert len(BEATS) == 27
    assert 650 <= sum(len(beat.narration.split()) for beat in BEATS) <= 850
    assert "draft-model proxy" in BEATS[15].narration
    assert "greedy toy example" in BEATS[22].narration
    assert "target's distribution" in BEATS[25].narration


def test_episode_refuses_a_different_narration_provider(monkeypatch):
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "gtts")
    scene = DDTreeFullExplainer()
    with pytest.raises(ValueError, match="MAI"):
        scene.setup()


def test_missing_key_does_not_silently_create_an_unnarrated_final(monkeypatch):
    monkeypatch.setenv("MANIM_TTS_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    scene = DDTreeFullExplainer()
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        scene.setup()
