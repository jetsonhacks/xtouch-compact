"""Fixed, typed factory X-TOUCH COMPACT device map (Standard MIDI mode).

This module is the authoritative runtime device profile. It represents the
factory Layer A ("Mixer Control") and Layer B ("Instrument Control") TX
presets and the GLOBAL_CH RX mappings, as documented in the Behringer
X-TOUCH COMPACT Quick Start Guide (V6.0, 2024; TX pages 29-30, RX page 32)
together with the empirical results recorded in
``docs/hardware-observations.md``.

Only the factory mappings are represented; mappings changed with the
X-TOUCH Editor are out of scope. The historical machine-readable
characterization document, ``specs/xtouch-compact-midi.yaml`` (see
``specs/README.md``), remains in the repository as evidence but is no
longer read at runtime and is not required to stay in sync with this
module.

Every structure here is built once at import time and exposed only as a
read-only mapping or frozen dataclass; there is no supported way to mutate
it or substitute an alternate device profile at runtime.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from .controls import Button, Encoder, Fader, FootControl, Layer, MappedControl
from .midi import ControlChange, NoteOff, NoteOn, ProgramChange, RawMidiMessage


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
    """One device-to-host mapping (a factory TX preset entry)."""

    layer: Layer
    midi_channel: int
    address: MidiAddress
    control: MappedControl
    interaction: Interaction


@dataclass(frozen=True, slots=True)
class RxBinding:
    """One host-to-device mapping on the configured Global MIDI Channel."""

    address: MidiAddress
    control: MappedControl
    operation: str


# --- Shared protocol-wide constants ------------------------------------
#
# These are independently justified protocol vectors, not values derived
# from the address tables below. Every fader, encoder, and button on this
# device shares them, per the manufacturer guide and, where noted,
# ``docs/hardware-observations.md``.

FADER_VALUE_MIN = 0
FADER_VALUE_MAX = 127
FADER_TOUCHED_VALUE = 127  # hardware_observation
FADER_RELEASED_VALUE = 0  # hardware_observation
PRESS_VELOCITY = 127  # hardware_observation
RELEASE_VELOCITY = 0  # hardware_observation: note_off velocity 0

# hardware_observation: measured effective values differ from the values
# documented in the manufacturer guide (off=note_off/velocity 0, on=1,
# blink=2). These are the values the device actually honors.
BUTTON_LED_VALUES: Mapping[str, int] = MappingProxyType({"off": 0, "on": 2, "blink": 3})

ENCODER_RING_MODE_VALUES: Mapping[str, int] = MappingProxyType(
    {"single": 0, "pan": 1, "fan": 2, "spread": 3, "trim": 4}
)

ENCODER_RING_POSITION_MIN = 1
ENCODER_RING_POSITION_MAX = 13
ENCODER_RING_DISPLAY_VALUES: Mapping[str, int] = MappingProxyType(
    {
        "all_off": 0,
        "position_offset": 0,
        "blinking_position_offset": 13,
        "all_on": 27,
        "all_blinking": 28,
    }
)

PRESET_LAYER_VALUES: Mapping[str, int] = MappingProxyType({"layer_a": 0, "layer_b": 1})

FOOT_SWITCH_STATUS_LED_NUMBER = 42
FOOT_SWITCH_STATUS_LED_VALUES: Mapping[str, int] = MappingProxyType(
    {"off": 0, "on": 127}
)


# --- Physical iteration order -------------------------------------------
#
# ``Fader``, ``Encoder``, and assignable ``Button`` members are declared in
# the same physical left-to-right / top-to-bottom order the manufacturer
# guide uses to assign sequential MIDI numbers, so zipping enum iteration
# order against a documented base number reproduces the printed tables.

FADERS: tuple[Fader, ...] = tuple(Fader)
ENCODERS: tuple[Encoder, ...] = tuple(Encoder)
ASSIGNABLE_BUTTONS: tuple[Button, ...] = tuple(
    button for button in Button if button not in {Button.LAYER_A, Button.LAYER_B}
)


def _tx_faders(
    layer: Layer, channel: int, position_base: int, touch_base: int
) -> tuple[TxBinding, ...]:
    bindings: list[TxBinding] = []
    for index, fader in enumerate(FADERS):
        for base, interaction in (
            (position_base, Interaction.FADER_POSITION),
            (touch_base, Interaction.FADER_TOUCH),
        ):
            bindings.append(
                TxBinding(
                    layer,
                    channel,
                    MidiAddress(MidiMessageType.CONTROL_CHANGE, base + index, channel),
                    fader,
                    interaction,
                )
            )
    return tuple(bindings)


def _tx_encoders(
    layer: Layer, channel: int, turn_base: int, push_base: int
) -> tuple[TxBinding, ...]:
    bindings: list[TxBinding] = []
    for index, encoder in enumerate(ENCODERS):
        for message_type, base, interaction in (
            (MidiMessageType.CONTROL_CHANGE, turn_base, Interaction.ENCODER_TURN),
            (MidiMessageType.NOTE, push_base, Interaction.ENCODER_PUSH),
        ):
            bindings.append(
                TxBinding(
                    layer,
                    channel,
                    MidiAddress(message_type, base + index, channel),
                    encoder,
                    interaction,
                )
            )
    return tuple(bindings)


def _tx_buttons(layer: Layer, channel: int, note_base: int) -> tuple[TxBinding, ...]:
    return tuple(
        TxBinding(
            layer,
            channel,
            MidiAddress(MidiMessageType.NOTE, note_base + index, channel),
            button,
            Interaction.BUTTON,
        )
        for index, button in enumerate(ASSIGNABLE_BUTTONS)
    )


def _tx_foot_controls(
    layer: Layer, channel: int, expression_number: int, foot_switch_number: int
) -> tuple[TxBinding, ...]:
    return tuple(
        TxBinding(
            layer,
            channel,
            MidiAddress(MidiMessageType.CONTROL_CHANGE, number, channel),
            control,
            Interaction.FOOT_CONTROL,
        )
        for control, number in (
            (FootControl.EXPRESSION_PEDAL, expression_number),
            (FootControl.FOOT_SWITCH, foot_switch_number),
        )
    )


_LAYER_A_CHANNEL = 1
_LAYER_B_CHANNEL = 1

TX_BINDINGS: tuple[TxBinding, ...] = (
    _tx_faders(Layer.A, _LAYER_A_CHANNEL, position_base=1, touch_base=101)
    + _tx_encoders(Layer.A, _LAYER_A_CHANNEL, turn_base=10, push_base=0)
    + _tx_buttons(Layer.A, _LAYER_A_CHANNEL, note_base=16)
    + _tx_foot_controls(
        Layer.A, _LAYER_A_CHANNEL, expression_number=26, foot_switch_number=27
    )
    + _tx_faders(Layer.B, _LAYER_B_CHANNEL, position_base=28, touch_base=111)
    + _tx_encoders(Layer.B, _LAYER_B_CHANNEL, turn_base=37, push_base=55)
    + _tx_buttons(Layer.B, _LAYER_B_CHANNEL, note_base=71)
    + _tx_foot_controls(
        Layer.B, _LAYER_B_CHANNEL, expression_number=63, foot_switch_number=64
    )
)


def _build_tx_index(
    bindings: tuple[TxBinding, ...],
) -> Mapping[MidiAddress, tuple[TxBinding, ...]]:
    mutable: dict[MidiAddress, list[TxBinding]] = {}
    for binding in bindings:
        group = mutable.setdefault(binding.address, [])
        if any(existing.layer is binding.layer for existing in group):
            raise AssertionError(f"ambiguous TX address {binding.address}")
        group.append(binding)
    return MappingProxyType({address: tuple(g) for address, g in mutable.items()})


TX_INDEX: Mapping[MidiAddress, tuple[TxBinding, ...]] = _build_tx_index(TX_BINDINGS)


def _rx_faders(number_base: int) -> tuple[RxBinding, ...]:
    return tuple(
        RxBinding(
            MidiAddress(MidiMessageType.CONTROL_CHANGE, number_base + index),
            fader,
            "position",
        )
        for index, fader in enumerate(FADERS)
    )


def _rx_button_leds(number_base: int) -> tuple[RxBinding, ...]:
    return tuple(
        RxBinding(
            MidiAddress(MidiMessageType.NOTE, number_base + index),
            button,
            "led",
        )
        for index, button in enumerate(ASSIGNABLE_BUTTONS)
    )


def _rx_encoder_rings(behavior_base: int, value_base: int) -> tuple[RxBinding, ...]:
    bindings: list[RxBinding] = []
    for index, encoder in enumerate(ENCODERS):
        for base, operation in (
            (behavior_base, "ring_behavior"),
            (value_base, "ring_value"),
        ):
            bindings.append(
                RxBinding(
                    MidiAddress(MidiMessageType.CONTROL_CHANGE, base + index),
                    encoder,
                    operation,
                )
            )
    return tuple(bindings)


RX_BINDINGS: tuple[RxBinding, ...] = (
    _rx_faders(number_base=1)
    + _rx_button_leds(number_base=0)
    + _rx_encoder_rings(behavior_base=10, value_base=26)
    + (
        RxBinding(
            MidiAddress(MidiMessageType.CONTROL_CHANGE, FOOT_SWITCH_STATUS_LED_NUMBER),
            FootControl.FOOT_SWITCH,
            "status_led",
        ),
    )
)


def _build_rx_index(bindings: tuple[RxBinding, ...]) -> Mapping[MidiAddress, RxBinding]:
    index: dict[MidiAddress, RxBinding] = {}
    for binding in bindings:
        if binding.address in index:
            raise AssertionError(f"duplicate RX address {binding.address}")
        index[binding.address] = binding
    return MappingProxyType(index)


RX_INDEX: Mapping[MidiAddress, RxBinding] = _build_rx_index(RX_BINDINGS)


def _build_rx_control_index(
    bindings: tuple[RxBinding, ...],
) -> Mapping[tuple[MappedControl, str], RxBinding]:
    index: dict[tuple[MappedControl, str], RxBinding] = {}
    for binding in bindings:
        key = (binding.control, binding.operation)
        if key in index:
            raise AssertionError(f"duplicate RX control operation {key}")
        index[key] = binding
    return MappingProxyType(index)


RX_CONTROL_INDEX: Mapping[tuple[MappedControl, str], RxBinding] = (
    _build_rx_control_index(RX_BINDINGS)
)


def classify_rx_message(
    message: RawMidiMessage, global_midi_channel: int
) -> RxBinding | None:
    """Return the RX binding a raw outbound message would address, if any.

    Used only to identify which tracked feedback a diagnostic raw
    ``send()`` affects, so its command history can be invalidated after
    successful transmission -- never to route, rewrite, or reinterpret the
    message itself. Matches strictly on message type, address number, and
    the configured Global MIDI Channel; a message on another channel or at
    an unmapped address returns ``None``. Layer selection (Program Change)
    has no RX binding and is not covered here; see
    :func:`matches_layer_program_change`.
    """
    if isinstance(message, (NoteOn, NoteOff)):
        if message.midi_channel != global_midi_channel:
            return None
        address = MidiAddress(MidiMessageType.NOTE, message.note_number)
    elif isinstance(message, ControlChange):
        if message.midi_channel != global_midi_channel:
            return None
        address = MidiAddress(MidiMessageType.CONTROL_CHANGE, message.control_number)
    else:
        return None
    return RX_INDEX.get(address)


def matches_layer_program_change(
    message: RawMidiMessage, global_midi_channel: int
) -> bool:
    """Return whether a raw message is a Program Change asserting a layer.

    Layer selection has no ``RxBinding`` entry (see
    :func:`classify_rx_message`), so it is matched independently against
    :data:`PRESET_LAYER_VALUES` on the configured Global MIDI Channel.
    """
    return (
        isinstance(message, ProgramChange)
        and message.midi_channel == global_midi_channel
        and message.program_number in PRESET_LAYER_VALUES.values()
    )
