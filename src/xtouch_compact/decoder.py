"""Pure inbound decoding from MIDI messages to physical-control events."""

from __future__ import annotations

from typing import cast

from .controls import Button, Encoder, Fader
from .device_map import (
    FADER_RELEASED_VALUE,
    FADER_TOUCHED_VALUE,
    PRESS_VELOCITY,
    RELEASE_VELOCITY,
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
from .midi import ControlChange, NoteOff, NoteOn, RawMidiMessage


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
    """Return the TX lookup address, or ``None`` if the map keys no such address."""
    if isinstance(raw, ControlChange):
        return MidiAddress(
            MidiMessageType.CONTROL_CHANGE,
            raw.control_number,
            raw.midi_channel,
        )
    if isinstance(raw, (NoteOn, NoteOff)):
        return MidiAddress(MidiMessageType.NOTE, raw.note_number, raw.midi_channel)
    # Program Change selects a preset layer host-to-device only; the device
    # never transmits one.
    return None


def _decode_binding(
    binding: TxBinding, raw: RawMidiMessage
) -> PhysicalControlEvent | None:
    layer = binding.layer

    if binding.interaction is Interaction.FADER_POSITION:
        message = cast(ControlChange, raw)
        fader = cast(Fader, binding.control)
        return FaderPositionReported(fader, layer, message.value, message)

    if binding.interaction is Interaction.FADER_TOUCH:
        message = cast(ControlChange, raw)
        fader = cast(Fader, binding.control)
        if message.value == FADER_TOUCHED_VALUE:
            return FaderTouched(fader, layer, message)
        if message.value == FADER_RELEASED_VALUE:
            return FaderReleased(fader, layer, message)
        return None

    if binding.interaction is Interaction.ENCODER_TURN:
        message = cast(ControlChange, raw)
        encoder = cast(Encoder, binding.control)
        return EncoderPositionReported(encoder, layer, message.value, message)

    if binding.interaction is Interaction.ENCODER_PUSH:
        encoder = cast(Encoder, binding.control)
        if isinstance(raw, NoteOn) and raw.velocity == PRESS_VELOCITY:
            return EncoderPressed(encoder, layer, raw)
        if isinstance(raw, NoteOff) and raw.velocity == RELEASE_VELOCITY:
            return EncoderReleased(encoder, layer, raw)
        return None

    if binding.interaction is Interaction.BUTTON:
        button = cast(Button, binding.control)
        if isinstance(raw, NoteOn) and raw.velocity == PRESS_VELOCITY:
            return ButtonPressed(button, layer, raw)
        if isinstance(raw, NoteOff) and raw.velocity == RELEASE_VELOCITY:
            return ButtonReleased(button, layer, raw)
        return None

    # Foot-control input is mapped but not published as a typed event.
    return None
