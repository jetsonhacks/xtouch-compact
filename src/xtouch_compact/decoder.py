"""Pure inbound decoding from MIDI messages to physical-control events."""

from __future__ import annotations

from .controls import Button, Encoder, Fader
from .device_map import (
    FADER_RELEASED_VALUE,
    FADER_TOUCHED_VALUE,
    FADER_VALUE_MAX,
    FADER_VALUE_MIN,
    PRESS_VELOCITY,
    TX_INDEX,
    Interaction,
    MidiAddress,
    MidiMessageType,
    TxBinding,
)
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


class InboundDecoder:
    """Decode factory TX traffic against the fixed factory device map."""

    def decode(self, raw: RawMidiMessage) -> PhysicalControlEvent | None:
        """Return a physical event, or ``None`` for unknown/unsupported traffic."""
        address = _address(raw)
        if address is None:
            return None
        bindings = TX_INDEX.get(address, ())
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
        if not FADER_VALUE_MIN <= raw.value <= FADER_VALUE_MAX:
            return None
        return FaderPositionReported(binding.control, binding.layer, raw.value, raw)
    if binding.interaction is Interaction.FADER_TOUCH:
        if not isinstance(raw, ControlChange) or not isinstance(binding.control, Fader):
            return None
        if raw.value == FADER_TOUCHED_VALUE:
            return FaderTouched(binding.control, binding.layer, raw)
        if raw.value == FADER_RELEASED_VALUE:
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
        if isinstance(raw, NoteOn) and raw.velocity == PRESS_VELOCITY:
            return EncoderPressed(binding.control, binding.layer, raw)
        if isinstance(raw, NoteOff) and raw.velocity == 0:
            return EncoderReleased(binding.control, binding.layer, raw)
        return None
    if binding.interaction is Interaction.BUTTON:
        if not isinstance(binding.control, Button):
            return None
        if isinstance(raw, NoteOn) and raw.velocity == PRESS_VELOCITY:
            return ButtonPressed(binding.control, binding.layer, raw)
        if isinstance(raw, NoteOff) and raw.velocity == 0:
            return ButtonReleased(binding.control, binding.layer, raw)
    return None
