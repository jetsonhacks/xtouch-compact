"""Fixed-map-backed semantic feedback message construction."""

from __future__ import annotations

from .controls import Button, Encoder, Fader, FootControl, Layer, MappedControl
from .device_map import (
    BUTTON_LED_VALUES,
    ENCODER_RING_DISPLAY_VALUES,
    ENCODER_RING_MODE_VALUES,
    ENCODER_RING_POSITION_MAX,
    ENCODER_RING_POSITION_MIN,
    FOOT_SWITCH_STATUS_LED_VALUES,
    PRESET_LAYER_VALUES,
    RX_CONTROL_INDEX,
    MidiMessageType,
    RxBinding,
)
from .errors import UnsupportedOperationError
from .feedback import (
    ButtonLedState,
    EncoderRingDisplay,
    EncoderRingDisplayKind,
    EncoderRingMode,
    StatusLedState,
)
from .midi import ControlChange, NoteOn, ProgramChange


class SemanticFeedbackEncoder:
    """Build typed MIDI from semantic controls through the fixed RX map."""

    def __init__(self, *, global_midi_channel: int) -> None:
        self._global_midi_channel = global_midi_channel

    def fader(self, fader: Fader, value: int) -> ControlChange:
        binding = self._rx_binding(fader, "position", MidiMessageType.CONTROL_CHANGE)
        return self._control_change(binding, value)

    def button_led(self, button: Button, state: ButtonLedState) -> NoteOn:
        binding = self._rx_binding(button, "led", MidiMessageType.NOTE)
        try:
            value = BUTTON_LED_VALUES[state.value]
        except KeyError as error:
            raise UnsupportedOperationError(
                f"unsupported button LED state {state!r}"
            ) from error
        return NoteOn(self._global_midi_channel, self._address_number(binding), value)

    def encoder_ring_mode(
        self, encoder: Encoder, mode: EncoderRingMode
    ) -> ControlChange:
        binding = self._rx_binding(
            encoder, "ring_behavior", MidiMessageType.CONTROL_CHANGE
        )
        try:
            value = ENCODER_RING_MODE_VALUES[mode.value]
        except KeyError as error:
            raise UnsupportedOperationError(
                f"unsupported encoder ring mode {mode!r}"
            ) from error
        return self._control_change(binding, value)

    def encoder_ring_value(
        self, encoder: Encoder, display: EncoderRingDisplay
    ) -> ControlChange:
        binding = self._rx_binding(
            encoder, "ring_value", MidiMessageType.CONTROL_CHANGE
        )
        try:
            kind = display.kind
        except AttributeError as error:
            raise UnsupportedOperationError(
                f"unsupported encoder ring display {display!r}"
            ) from error
        if kind in {
            EncoderRingDisplayKind.POSITION,
            EncoderRingDisplayKind.BLINKING_POSITION,
        }:
            position = display.position
            if position is None or not (
                ENCODER_RING_POSITION_MIN <= position <= ENCODER_RING_POSITION_MAX
            ):
                raise UnsupportedOperationError(
                    "encoder ring position must be from "
                    f"{ENCODER_RING_POSITION_MIN} through {ENCODER_RING_POSITION_MAX}"
                )
            offset_name = (
                "position_offset"
                if kind is EncoderRingDisplayKind.POSITION
                else "blinking_position_offset"
            )
            value = position + ENCODER_RING_DISPLAY_VALUES[offset_name]
        else:
            try:
                value = ENCODER_RING_DISPLAY_VALUES[kind.value]
            except KeyError as error:
                raise UnsupportedOperationError(
                    f"unsupported encoder ring display {display!r}"
                ) from error
        return self._control_change(binding, value)

    def layer(self, layer: Layer) -> ProgramChange:
        try:
            value = PRESET_LAYER_VALUES[layer.value]
        except (AttributeError, KeyError) as error:
            raise UnsupportedOperationError(f"unsupported layer {layer!r}") from error
        return ProgramChange(self._global_midi_channel, value)

    def foot_switch_led(self, state: StatusLedState) -> ControlChange:
        binding = self._rx_binding(
            FootControl.FOOT_SWITCH, "status_led", MidiMessageType.CONTROL_CHANGE
        )
        try:
            value = FOOT_SWITCH_STATUS_LED_VALUES[state.value]
        except KeyError as error:
            raise UnsupportedOperationError(
                f"unsupported status LED state {state!r}"
            ) from error
        return self._control_change(binding, value)

    def _rx_binding(
        self,
        control: MappedControl,
        operation: str,
        message_type: MidiMessageType,
    ) -> RxBinding:
        try:
            binding = RX_CONTROL_INDEX[(control, operation)]
        except (KeyError, TypeError) as error:
            raise UnsupportedOperationError(
                f"{control!r} has no {operation.replace('_', ' ')} RX mapping"
            ) from error
        assert binding.address.message_type is message_type
        return binding

    def _control_change(self, binding: RxBinding, value: int) -> ControlChange:
        return ControlChange(
            self._global_midi_channel,
            self._address_number(binding),
            value,
        )

    @staticmethod
    def _address_number(binding: RxBinding) -> int:
        number = binding.address.number
        assert number is not None
        return number
