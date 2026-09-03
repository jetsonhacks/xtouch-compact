"""Validate and index device-to-host TX mappings."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

from ._specification_common import (
    Interaction,
    MidiAddress,
    MidiMessageType,
    TxBinding,
    _enum_member,
    _freeze,
    _integer,
    _mapping,
    _message_type,
)
from .controls import Button, Encoder, Fader, FootControl, Layer, MappedControl
from .errors import SpecificationError


def _tx_control(group: str, physical_id: str, location: str) -> MappedControl:
    enum_type = cast(
        "type[MappedControl]",
        {
            "faders": Fader,
            "encoders": Encoder,
            "buttons": Button,
            "foot_controls": FootControl,
        }[group],
    )
    return _enum_member(enum_type, physical_id, location)


def _tx_interaction(group: str, action: str, location: str) -> Interaction:
    try:
        return {
            ("faders", "position"): Interaction.FADER_POSITION,
            ("faders", "touch"): Interaction.FADER_TOUCH,
            ("encoders", "turn"): Interaction.ENCODER_TURN,
            ("encoders", "push"): Interaction.ENCODER_PUSH,
            ("buttons", "button"): Interaction.BUTTON,
            ("foot_controls", "value"): Interaction.FOOT_CONTROL,
        }[(group, action)]
    except KeyError as error:
        raise SpecificationError(f"{location} has unsupported interaction") from error


def _validate_tx_details(
    details: dict[str, Any], interaction: Interaction, location: str
) -> tuple[MidiMessageType, int]:
    message_type = _message_type(details.get("type"), f"{location}.type")
    number = _integer(details.get("number"), f"{location}.number", 0, 127)
    expected_type = (
        MidiMessageType.NOTE
        if interaction in {Interaction.ENCODER_PUSH, Interaction.BUTTON}
        else MidiMessageType.CONTROL_CHANGE
    )
    if message_type is not expected_type:
        raise SpecificationError(
            f"{location} must use {expected_type.value}, found {message_type.value}"
        )
    for field in (
        "value_min",
        "value_max",
        "touched_value",
        "released_value",
        "press_velocity",
    ):
        if field in details:
            _integer(details[field], f"{location}.{field}", 0, 127)
    if (
        "value_min" in details
        and "value_max" in details
        and details["value_min"] > details["value_max"]
    ):
        raise SpecificationError(f"{location} has an inverted value range")
    return message_type, number


def build_tx_index(
    document: dict[str, Any],
) -> Mapping[MidiAddress, tuple[TxBinding, ...]]:
    """Validate TX mappings and index them by typed MIDI address."""
    transmit = _mapping(document.get("transmit"), "transmit")
    if set(transmit) != {layer.value for layer in Layer}:
        raise SpecificationError("transmit must define exactly layer_a and layer_b")
    expected_ids = {
        "faders": {member.value for member in Fader},
        "encoders": {member.value for member in Encoder},
        "buttons": {
            member.value
            for member in Button
            if member not in {Button.LAYER_A, Button.LAYER_B}
        },
        "foot_controls": {member.value for member in FootControl},
    }
    mutable_index: dict[MidiAddress, list[TxBinding]] = {}
    expected_actions = {
        "faders": {"position", "touch"},
        "encoders": {"turn", "push"},
        "buttons": {"button"},
        "foot_controls": {"value"},
    }
    for layer in Layer:
        layer_data = _mapping(transmit[layer.value], f"transmit.{layer.value}")
        midi_channel = _integer(
            layer_data.get("midi_channel"),
            f"transmit.{layer.value}.midi_channel",
            1,
            16,
        )
        for group, group_ids in expected_ids.items():
            group_data = _mapping(
                layer_data.get(group), f"transmit.{layer.value}.{group}"
            )
            if set(group_data) != group_ids:
                raise SpecificationError(
                    f"transmit.{layer.value}.{group} does not match physical controls"
                )
            for physical_id, operations_value in group_data.items():
                operations = (
                    operations_value
                    if group in {"faders", "encoders"}
                    else {next(iter(expected_actions[group])): operations_value}
                )
                operations = _mapping(
                    operations,
                    f"transmit.{layer.value}.{group}.{physical_id}",
                )
                if set(operations) != expected_actions[group]:
                    raise SpecificationError(
                        f"transmit.{layer.value}.{group}.{physical_id} "
                        "has missing or unexpected operations"
                    )
                for action, details_value in operations.items():
                    location = f"transmit.{layer.value}.{group}.{physical_id}.{action}"
                    details = _mapping(details_value, location)
                    interaction = _tx_interaction(group, action, location)
                    message_type, number = _validate_tx_details(
                        details, interaction, location
                    )
                    address = MidiAddress(message_type, number, midi_channel)
                    binding = TxBinding(
                        layer=layer,
                        midi_channel=midi_channel,
                        address=address,
                        control=_tx_control(group, physical_id, location),
                        interaction=interaction,
                        details=_freeze(details),
                    )
                    layer_bindings = mutable_index.setdefault(address, [])
                    if any(existing.layer is layer for existing in layer_bindings):
                        raise SpecificationError(
                            f"{location} duplicates TX address {address}"
                        )
                    layer_bindings.append(binding)
    return MappingProxyType(
        {address: tuple(bindings) for address, bindings in mutable_index.items()}
    )
