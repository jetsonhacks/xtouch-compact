"""Shared immutable values and validation primitives for the device schema."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from .controls import Layer, MappedControl
from .errors import SpecificationError

__all__ = [
    "DeviceSpecification",
    "Interaction",
    "MidiAddress",
    "MidiMessageType",
    "RxBinding",
    "TxBinding",
]


class MidiMessageType(Enum):
    NOTE = "note"
    CONTROL_CHANGE = "control_change"
    PROGRAM_CHANGE = "program_change"


class Interaction(Enum):
    FADER_POSITION = "fader_position"
    FADER_TOUCH = "fader_touch"
    ENCODER_TURN = "encoder_turn"
    ENCODER_PUSH = "encoder_push"
    BUTTON = "button"
    FOOT_CONTROL = "foot_control"


@dataclass(frozen=True, slots=True)
class MidiAddress:
    message_type: MidiMessageType
    number: int | None
    midi_channel: int | None = None


@dataclass(frozen=True, slots=True)
class TxBinding:
    layer: Layer
    midi_channel: int
    address: MidiAddress
    control: MappedControl
    interaction: Interaction
    details: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class RxBinding:
    address: MidiAddress
    control: MappedControl | None
    operation: str
    details: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class DeviceSpecification:
    """The complete frozen document and its separate TX and RX indexes."""

    document: Mapping[str, object]
    tx_index: Mapping[MidiAddress, tuple[TxBinding, ...]]
    rx_index: Mapping[MidiAddress, RxBinding]
    rx_control_index: Mapping[tuple[MappedControl | None, str], RxBinding]


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _mapping(value: object, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SpecificationError(f"{location} must be a mapping")
    return value


def _integer(value: object, location: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpecificationError(f"{location} must be an integer")
    if not minimum <= value <= maximum:
        raise SpecificationError(f"{location} must be from {minimum} through {maximum}")
    return value


def _as_int(value: object) -> int:
    """Narrow one already-loaded detail value to ``int`` for encode/decode use.

    Unlike :func:`_integer`, this runs after specification load, against a
    single ``details`` entry rather than a YAML document location, so it has
    no bounds and no dotted location string for its error message.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpecificationError(f"expected an integer detail value, got {value!r}")
    return value


def _message_type(value: object, location: str) -> MidiMessageType:
    try:
        return MidiMessageType(value)
    except ValueError as error:
        raise SpecificationError(
            f"{location} has unsupported MIDI type {value!r}"
        ) from error


def _enum_member(
    enum_type: type[MappedControl], value: str, location: str
) -> MappedControl:
    try:
        return enum_type(value)
    except ValueError as error:
        raise SpecificationError(f"{location} has unknown control {value!r}") from error
