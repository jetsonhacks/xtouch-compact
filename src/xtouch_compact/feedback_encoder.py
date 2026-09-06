"""Fixed-map-backed semantic feedback message construction."""

from __future__ import annotations

from typing import cast

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

_POSITIONED_KINDS = frozenset(
    {EncoderRingDisplayKind.POSITION, EncoderRingDisplayKind.BLINKING_POSITION}
)


class SemanticFeedbackEncoder:
    """Build typed MIDI from semantic controls through the fixed RX map."""

    def __init__(self, *, global_midi_channel: int) -> None:
        self._global_midi_channel = global_midi_channel

    @property
    def global_midi_channel(self) -> int:
        """The configured RX channel, for matching raw diagnostic output."""
        return self._global_midi_channel

    def fader(self, fader: Fader, value: int) -> ControlChange:
        return self._control_change(self._rx_binding(fader, "position"), value)

    def button_led(self, button: Button, state: ButtonLedState) -> NoteOn:
        binding = self._rx_binding(button, "led")
        return NoteOn(
            self._global_midi_channel,
            _address_number(binding),
            BUTTON_LED_VALUES[state.value],
        )

    def encoder_ring_mode(
        self, encoder: Encoder, mode: EncoderRingMode
    ) -> ControlChange:
        binding = self._rx_binding(encoder, "ring_behavior")
        return self._control_change(binding, ENCODER_RING_MODE_VALUES[mode.value])

    def encoder_ring_value(
        self, encoder: Encoder, display: EncoderRingDisplay
    ) -> ControlChange:
        binding = self._rx_binding(encoder, "ring_value")
        if display.kind in _POSITIONED_KINDS:
            value = self._ring_position_value(display)
        else:
            value = ENCODER_RING_DISPLAY_VALUES[display.kind.value]
        return self._control_change(binding, value)

    def layer(self, layer: Layer) -> ProgramChange:
        return ProgramChange(
            self._global_midi_channel, PRESET_LAYER_VALUES[layer.value]
        )

    def foot_switch_led(self, state: StatusLedState) -> ControlChange:
        binding = self._rx_binding(FootControl.FOOT_SWITCH, "status_led")
        return self._control_change(binding, FOOT_SWITCH_STATUS_LED_VALUES[state.value])

    @staticmethod
    def _ring_position_value(display: EncoderRingDisplay) -> int:
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
            if display.kind is EncoderRingDisplayKind.POSITION
            else "blinking_position_offset"
        )
        return position + ENCODER_RING_DISPLAY_VALUES[offset_name]

    @staticmethod
    def _rx_binding(control: MappedControl, operation: str) -> RxBinding:
        try:
            return RX_CONTROL_INDEX[(control, operation)]
        except (KeyError, TypeError) as error:
            raise UnsupportedOperationError(
                f"{control!r} has no {operation.replace('_', ' ')} RX mapping"
            ) from error

    def _control_change(self, binding: RxBinding, value: int) -> ControlChange:
        return ControlChange(self._global_midi_channel, _address_number(binding), value)


def _address_number(binding: RxBinding) -> int:
    # No RX binding is addressed by Program Change, so every one has a number.
    return cast(int, binding.address.number)
