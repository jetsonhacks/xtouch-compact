"""Pure inbound decoding from MIDI messages to physical-control events."""

from __future__ import annotations

from ._specification_common import _as_int
from .controls import Button, Encoder, Fader
from .events import (
    ButtonPressed,
    ButtonReleased,
    EncoderPositionReported,
    EncoderPressed,
    EncoderReleased,
    FaderPositionReported,
    FaderReleased,
    FaderTouched,
    PhysicalControlEvent,
)
from .midi import ControlChange, NoteOff, NoteOn, ProgramChange, RawMidiMessage
from .specification import (
    DeviceSpecification,
    Interaction,
    MidiAddress,
    MidiMessageType,
    TxBinding,
)


class InboundDecoder:
    """Decode factory TX traffic without mutable preset-layer state."""

    def __init__(self, specification: DeviceSpecification) -> None:
        self._tx_index = specification.tx_index

    def decode(self, raw: RawMidiMessage) -> PhysicalControlEvent | None:
        """Return a physical event, or ``None`` for unknown/unsupported traffic."""
        address = _address(raw)
        if address is None:
            return None
        bindings = self._tx_index.get(address, ())
        if len(bindings) != 1:
            return None
        return _decode_binding(bindings[0], raw)


def _address(raw: RawMidiMessage) -> MidiAddress | None:
    if isinstance(raw, ControlChange):
        return MidiAddress(
            MidiMessageType.CONTROL_CHANGE,
            raw.control_number,
            raw.midi_channel,
        )
    if isinstance(raw, (NoteOn, NoteOff)):
        return MidiAddress(MidiMessageType.NOTE, raw.note_number, raw.midi_channel)
    if isinstance(raw, ProgramChange):
        return None
    raise TypeError(f"unsupported MIDI message {type(raw).__name__}")


def _decode_binding(
    binding: TxBinding, raw: RawMidiMessage
) -> PhysicalControlEvent | None:
    if binding.interaction is Interaction.FADER_POSITION:
        if not isinstance(raw, ControlChange) or not isinstance(binding.control, Fader):
            return None
        minimum = _as_int(binding.details["value_min"])
        maximum = _as_int(binding.details["value_max"])
        if not minimum <= raw.value <= maximum:
            return None
        return FaderPositionReported(binding.control, binding.layer, raw.value, raw)
    if binding.interaction is Interaction.FADER_TOUCH:
        if not isinstance(raw, ControlChange) or not isinstance(binding.control, Fader):
            return None
        if raw.value == binding.details["touched_value"]:
            return FaderTouched(binding.control, binding.layer, raw)
        if raw.value == binding.details["released_value"]:
            return FaderReleased(binding.control, binding.layer, raw)
        return None
    if binding.interaction is Interaction.ENCODER_TURN:
        if not isinstance(raw, ControlChange) or not isinstance(
            binding.control, Encoder
        ):
            return None
        return EncoderPositionReported(binding.control, binding.layer, raw.value, raw)
    if binding.interaction is Interaction.ENCODER_PUSH:
        if not isinstance(binding.control, Encoder):
            return None
        if (
            isinstance(raw, NoteOn)
            and raw.velocity == binding.details["press_velocity"]
        ):
            return EncoderPressed(binding.control, binding.layer, raw)
        if isinstance(raw, NoteOff) and raw.velocity == 0:
            return EncoderReleased(binding.control, binding.layer, raw)
        return None
    if binding.interaction is Interaction.BUTTON:
        if not isinstance(binding.control, Button):
            return None
        if (
            isinstance(raw, NoteOn)
            and raw.velocity == binding.details["press_velocity"]
        ):
            return ButtonPressed(binding.control, binding.layer, raw)
        if isinstance(raw, NoteOff) and raw.velocity == 0:
            return ButtonReleased(binding.control, binding.layer, raw)
    return None
