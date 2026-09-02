"""Specification-backed semantic feedback message construction."""

from __future__ import annotations

from collections.abc import Mapping

from ._specification_common import _as_int
from .controls import Button, Encoder, Fader, FootControl, Layer, MappedControl
from .errors import SpecificationError, UnsupportedOperationError
from .feedback import (
    ButtonLedState,
    EncoderRingDisplay,
    EncoderRingDisplayKind,
    EncoderRingMode,
    StatusLedState,
)
from .midi import ControlChange, NoteOn, ProgramChange
from .specification import DeviceSpecification, MidiMessageType, RxBinding


class SemanticFeedbackEncoder:
    """Build typed MIDI from semantic controls through the RX specification."""

    def __init__(
        self, specification: DeviceSpecification, *, global_midi_channel: int
    ) -> None:
        self._specification = specification
        self._global_midi_channel = global_midi_channel

    def fader(self, fader: Fader, value: int) -> ControlChange:
        binding = self._rx_binding(fader, "position", MidiMessageType.CONTROL_CHANGE)
        return self._control_change(binding, value)

    def button_led(self, button: Button, state: ButtonLedState) -> NoteOn:
        binding = self._rx_binding(button, "led", MidiMessageType.NOTE)
        values = self._semantic_values("button_led_value_semantics")
        try:
            value = values[state.value]
        except (AttributeError, KeyError) as error:
            raise UnsupportedOperationError(
                f"unsupported button LED state {state!r}"
            ) from error
        return NoteOn(
            self._global_midi_channel,
            self._address_number(binding),
            _as_int(value),
        )

    def encoder_ring_mode(
        self, encoder: Encoder, mode: EncoderRingMode
    ) -> ControlChange:
        binding = self._rx_binding(
            encoder, "ring_behavior", MidiMessageType.CONTROL_CHANGE
        )
        values = self._mapping(binding.details.get("values"), "ring mode values")
        try:
            value = values[mode.value]
        except (AttributeError, KeyError) as error:
            raise UnsupportedOperationError(
                f"unsupported encoder ring mode {mode!r}"
            ) from error
        return self._control_change(binding, _as_int(value))

    def encoder_ring_value(
        self, encoder: Encoder, display: EncoderRingDisplay
    ) -> ControlChange:
        binding = self._rx_binding(
            encoder, "ring_value", MidiMessageType.CONTROL_CHANGE
        )
        semantics = self._document_mapping("encoder_ring_value_semantics")
        values = self._mapping(semantics.get("encoded_values"), "ring values")
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
            minimum = _as_int(semantics["position_min"])
            maximum = _as_int(semantics["position_max"])
            position = display.position
            if position is None or not minimum <= position <= maximum:
                raise UnsupportedOperationError(
                    f"encoder ring position must be from {minimum} through {maximum}"
                )
            offset_name = (
                "position_offset"
                if kind is EncoderRingDisplayKind.POSITION
                else "blinking_position_offset"
            )
            value = position + _as_int(values[offset_name])
        else:
            try:
                value = _as_int(values[kind.value])
            except KeyError as error:
                raise UnsupportedOperationError(
                    f"unsupported encoder ring display {display!r}"
                ) from error
        return self._control_change(binding, value)

    def layer(self, layer: Layer) -> ProgramChange:
        binding = self._specification.rx_control_index[(None, "preset_layer")]
        values = binding.details["values"]
        if not isinstance(values, Mapping):
            raise SpecificationError("preset-layer values are unavailable")
        try:
            value = values[layer.value]
        except (AttributeError, KeyError) as error:
            raise UnsupportedOperationError(f"unsupported layer {layer!r}") from error
        return ProgramChange(self._global_midi_channel, _as_int(value))

    def foot_switch_led(self, state: StatusLedState) -> ControlChange:
        binding = self._rx_binding(
            FootControl.FOOT_SWITCH, "status_led", MidiMessageType.CONTROL_CHANGE
        )
        values = self._mapping(
            binding.details.get("encoded_values"), "status LED values"
        )
        try:
            value = values[state.value]
        except (AttributeError, KeyError) as error:
            raise UnsupportedOperationError(
                f"unsupported status LED state {state!r}"
            ) from error
        return self._control_change(binding, _as_int(value))

    def _rx_binding(
        self,
        control: MappedControl,
        operation: str,
        message_type: MidiMessageType,
    ) -> RxBinding:
        try:
            binding = self._specification.rx_control_index[(control, operation)]
        except (KeyError, TypeError) as error:
            raise UnsupportedOperationError(
                f"{control!r} has no {operation.replace('_', ' ')} RX mapping"
            ) from error
        if binding.address.message_type is not message_type:
            raise SpecificationError(
                f"{control!r} has an invalid {operation} RX mapping"
            )
        return binding

    def _control_change(self, binding: RxBinding, value: int) -> ControlChange:
        return ControlChange(
            self._global_midi_channel,
            self._address_number(binding),
            value,
        )

    @staticmethod
    def _address_number(binding: RxBinding) -> int:
        if binding.address.number is None:
            raise SpecificationError(
                f"{binding.operation} RX mapping has no MIDI number"
            )
        return binding.address.number

    def _document_mapping(self, section: str) -> Mapping[str, object]:
        receive = self._mapping(self._specification.document.get("receive"), "receive")
        return self._mapping(receive.get(section), f"receive.{section}")

    def _semantic_values(self, section: str) -> Mapping[str, object]:
        details = self._document_mapping(section)
        return self._mapping(details.get("encoded_values"), f"{section} encoded values")

    @staticmethod
    def _mapping(value: object, name: str) -> Mapping[str, object]:
        if not isinstance(value, Mapping):
            raise SpecificationError(f"{name} are unavailable")
        return value
