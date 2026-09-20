import numpy as np
import pytest
from manim import Circle, Square

from manim_lib.policy import (
    ConfidenceGate,
    ConfidenceRegion,
    DataPacket,
    DecisionAggregator,
    DecisionRouter,
    PacketStatus,
)


def _finish(animation):
    animation.begin()
    animation.interpolate(1)
    animation.finish()


def test_confidence_gate_exact_geometry_survives_transform_and_update():
    gate = ConfidenceGate(
        thresholds=[0.25, 0.8],
        region_names=["reject", "review", "accept"],
        value=0.25,
        width=5,
    )
    assert gate.selected_region == "review"
    marker_points = gate.marker.get_all_points() - gate.marker.get_center()
    gate.scale(1.7).shift(np.array([2.0, -1.0, 0.0]))
    transformed_points = gate.marker.get_all_points() - gate.marker.get_center()
    marker_id = id(gate.marker)
    gate.set_value(0.8)
    assert gate.selected_region == "accept"
    assert id(gate.marker) == marker_id
    assert gate.marker.get_center()[0] == pytest.approx(gate.position_for_value(0.8)[0])
    assert gate.marker.get_all_points() - gate.marker.get_center() == pytest.approx(
        transformed_points
    )
    assert transformed_points == pytest.approx(marker_points * 1.7)


def test_confidence_gate_animated_update_reaches_exact_endpoint():
    gate = ConfidenceGate(
        [
            ConfidenceRegion("low", 0, 0.5, "#ff0000"),
            ConfidenceRegion("high", 0.5, 1, "#00ff00"),
        ]
    ).shift(np.array([-1.0, 0.5, 0]))
    _finish(gate.animate.set_value(1).build())
    assert gate.value == 1
    assert gate.selected_region == "high"
    assert gate.marker.get_center()[0] == pytest.approx(gate.track.get_end()[0])


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_confidence_gate_rejects_invalid_value_before_mutation(value):
    gate = ConfidenceGate(thresholds=[0.5], region_names=["no", "yes"], value=0.4)
    marker = gate.marker.get_all_points().copy()
    with pytest.raises(ValueError):
        gate.set_value(value)
    assert gate.value == 0.4
    assert gate.selected_region == "no"
    assert gate.marker.get_all_points() == pytest.approx(marker)


@pytest.mark.parametrize(
    "regions",
    [
        [("a", 0, 0.4), ("b", 0.5, 1)],
        [("a", 0.2, 1)],
        [("a", 0, 0.8), ("b", 0.7, 1)],
    ],
)
def test_confidence_gate_rejects_invalid_regions(regions):
    with pytest.raises(ValueError):
        ConfidenceGate(regions)


def test_decision_router_selects_existing_route_without_replacing_objects():
    decision = Circle().shift(np.array([-2, 0, 0]))
    allow = Square().shift(np.array([2, 1, 0]))
    deny = Square().shift(np.array([2, -1, 0]))
    router = DecisionRouter(decision, {"allow": allow, "deny": deny})
    identities = {
        "decision": id(router.decision_point),
        "allow": id(router.destinations["allow"]),
        "edge": id(router.route_edges["allow"]),
    }
    router.select_route("allow").select_route("deny")
    assert router.selected_route == "deny"
    assert id(router.decision_point) == identities["decision"]
    assert id(router.destinations["allow"]) == identities["allow"]
    assert id(router.route_edges["allow"]) == identities["edge"]
    assert router.route_highlights["deny"].get_stroke_opacity() == pytest.approx(1)
    assert router.route_highlights["deny"].get_fill_opacity() == pytest.approx(0)
    assert router.route_highlights["allow"].get_fill_opacity() == pytest.approx(0)
    with pytest.raises(KeyError):
        router.select_route("unknown")
    assert router.selected_route == "deny"


def test_decision_aggregator_keeps_named_operands_and_does_not_normalize():
    aggregator = DecisionAggregator(
        {"quality": 0.5, "cost": 2.0},
        {"quality": 4.0, "cost": -0.25},
    )
    assert set(aggregator.terms) == {"quality", "cost"}
    assert aggregator.weights == {"quality": 4.0, "cost": -0.25}
    assert aggregator.result == pytest.approx(1.5)
    input_id = id(aggregator.input_mobjects["quality"])
    result_id = id(aggregator.result_mobject)
    aggregator.set_input("quality", 0.75)
    assert aggregator.result == pytest.approx(2.5)
    assert aggregator.result_mobject.get_value() == pytest.approx(2.5)
    assert id(aggregator.input_mobjects["quality"]) == input_id
    assert id(aggregator.result_mobject) == result_id


def test_decision_aggregator_validates_before_mutation():
    aggregator = DecisionAggregator({"a": 1}, {"a": 2})
    old = aggregator.result
    with pytest.raises(ValueError):
        aggregator.set_input("a", float("nan"))
    assert aggregator.input_values["a"] == 1
    assert aggregator.result == old
    with pytest.raises(KeyError):
        aggregator.set_input("missing", 2)
    with pytest.raises(ValueError):
        DecisionAggregator({"a": 1}, {"b": 1})


def test_data_packet_preserves_identity_and_geometry_when_status_changes():
    packet = DataPacket("request-7", "Request", {"query": "short"}, status="pending")
    body_id = id(packet.body)
    badge_id = id(packet.status_badge)
    label_id = id(packet.status_label)
    packet.scale(1.4).shift(np.array([1.0, 2.0, 0.0]))
    badge_center = packet.status_badge.get_center().copy()
    packet.set_status(PacketStatus.SUCCESS)
    assert packet.packet_id == "request-7"
    assert packet.status is PacketStatus.SUCCESS
    assert packet.status_label.text == "SUCCESS"
    assert id(packet.body) == body_id
    assert id(packet.status_badge) == badge_id
    assert id(packet.status_label) == label_id
    assert packet.status_badge.get_center() == pytest.approx(badge_center)
    with pytest.raises(ValueError):
        packet.set_status("invented")
    assert packet.status is PacketStatus.SUCCESS


def test_data_packet_payload_preview_is_compact():
    packet = DataPacket("p", "Payload", "abcdefghijklmnopqrstuvwxyz", preview_length=10)
    assert packet.payload_preview.text.endswith("…")
    assert len(packet.payload_preview.text) == 10
