"""Validate and index host-to-device RX mappings and semantic encodings."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from ._specification_common import (
    MidiAddress,
    MidiMessageType,
    RxBinding,
    SpecificationError,
    _enum_member,
    _freeze,
    _integer,
    _mapping,
    _message_type,
)
from .controls import Button, Encoder, Fader, FootControl, MappedControl


def _rx_mapping(
    index: dict[MidiAddress, RxBinding],
    details_value: object,
    location: str,
    operation: str,
    control: MappedControl | None = None,
) -> None:
    details = _mapping(details_value, location)
    message_type = _message_type(details.get("type"), f"{location}.type")
    number_value = details.get("number")
    number = None
    if message_type is not MidiMessageType.PROGRAM_CHANGE:
        number = _integer(number_value, f"{location}.number", 0, 127)
    elif number_value is not None:
        raise SpecificationError(f"{location}.number is invalid for Program Change")
    address = MidiAddress(message_type, number)
    if address in index:
        raise SpecificationError(f"{location} duplicates RX address {address}")
    index[address] = RxBinding(address, control, operation, _freeze(details))


def validate_semantic_values(document: dict[str, Any]) -> None:
    """Validate machine-readable feedback encodings used by the public API."""
    receive = _mapping(document.get("receive"), "receive")
    ring = _mapping(
        receive.get("encoder_ring_value_semantics"),
        "receive.encoder_ring_value_semantics",
    )
    position_min = _integer(
        ring.get("position_min"),
        "receive.encoder_ring_value_semantics.position_min",
        1,
        127,
    )
    position_max = _integer(
        ring.get("position_max"),
        "receive.encoder_ring_value_semantics.position_max",
        position_min,
        127,
    )
    ring_values = _mapping(
        ring.get("encoded_values"),
        "receive.encoder_ring_value_semantics.encoded_values",
    )
    if set(ring_values) != {
        "all_off",
        "position_offset",
        "blinking_position_offset",
        "all_on",
        "all_blinking",
    }:
        raise SpecificationError("encoder ring encoded values are incomplete")
    for name, value in ring_values.items():
        _integer(
            value,
            f"receive.encoder_ring_value_semantics.encoded_values.{name}",
            0,
            127,
        )
    for offset_name in ("position_offset", "blinking_position_offset"):
        if ring_values[offset_name] + position_max > 127:
            raise SpecificationError(
                f"encoder ring {offset_name} exceeds the 7-bit value range"
            )

    button = _mapping(
        receive.get("button_led_value_semantics"),
        "receive.button_led_value_semantics",
    )
    button_values = _mapping(
        button.get("encoded_values"),
        "receive.button_led_value_semantics.encoded_values",
    )
    if set(button_values) != {"off", "on", "blink"}:
        raise SpecificationError("button LED encoded values are incomplete")
    for name, value in button_values.items():
        _integer(
            value,
            f"receive.button_led_value_semantics.encoded_values.{name}",
            0,
            127,
        )

    status = _mapping(receive.get("status_leds"), "receive.status_leds")
    foot_switch = _mapping(status.get("foot_switch"), "receive.status_leds.foot_switch")
    foot_values = _mapping(
        foot_switch.get("encoded_values"),
        "receive.status_leds.foot_switch.encoded_values",
    )
    if set(foot_values) != {"off", "on"}:
        raise SpecificationError("foot-switch LED encoded values are incomplete")
    for name, value in foot_values.items():
        _integer(
            value,
            f"receive.status_leds.foot_switch.encoded_values.{name}",
            0,
            127,
        )


def build_rx_index(document: dict[str, Any]) -> Mapping[MidiAddress, RxBinding]:
    """Validate RX mappings and index them by typed MIDI address."""
    receive = _mapping(document.get("receive"), "receive")
    if receive.get("channel") != "GLOBAL_CH":
        raise SpecificationError("receive.channel must remain GLOBAL_CH")
    index: dict[MidiAddress, RxBinding] = {}
    _rx_mapping(
        index, receive.get("operation_mode"), "receive.operation_mode", "operation_mode"
    )
    _rx_mapping(
        index, receive.get("preset_layer"), "receive.preset_layer", "preset_layer"
    )
    groups: tuple[tuple[str, type[MappedControl], str], ...] = (
        ("faders", Fader, "position"),
        ("button_leds", Button, "led"),
    )
    for group, enum_type, operation in groups:
        mappings = _mapping(receive.get(group), f"receive.{group}")
        expected = {
            member.value
            for member in enum_type
            if member not in {Button.LAYER_A, Button.LAYER_B}
        }
        if set(mappings) != expected:
            raise SpecificationError(
                f"receive.{group} does not match physical controls"
            )
        for physical_id, details in mappings.items():
            _rx_mapping(
                index,
                details,
                f"receive.{group}.{physical_id}",
                operation,
                _enum_member(enum_type, physical_id, f"receive.{group}"),
            )
    rings = _mapping(receive.get("encoder_rings"), "receive.encoder_rings")
    if set(rings) != {member.value for member in Encoder}:
        raise SpecificationError(
            "receive.encoder_rings does not match physical controls"
        )
    for physical_id, operations_value in rings.items():
        operations = _mapping(operations_value, f"receive.encoder_rings.{physical_id}")
        if set(operations) != {"behavior", "value"}:
            raise SpecificationError(
                f"receive.encoder_rings.{physical_id} has invalid operations"
            )
        control = _enum_member(Encoder, physical_id, "receive.encoder_rings")
        for operation, details in operations.items():
            _rx_mapping(
                index,
                details,
                f"receive.encoder_rings.{physical_id}.{operation}",
                f"ring_{operation}",
                control,
            )
    status_leds = _mapping(receive.get("status_leds"), "receive.status_leds")
    for foot_control in (FootControl.FOOT_SWITCH, FootControl.EXPRESSION_PEDAL):
        _rx_mapping(
            index,
            status_leds.get(foot_control.value),
            f"receive.status_leds.{foot_control.value}",
            "status_led",
            foot_control,
        )
    for required_section in ("button_led_value_semantics", "layer_leds"):
        _mapping(receive.get(required_section), f"receive.{required_section}")
    return MappingProxyType(index)
