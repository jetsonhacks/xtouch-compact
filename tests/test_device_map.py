"""Structural invariants for the fixed factory device map.

Static typing proves the shape of :mod:`xtouch_compact.device_map`; it does
not prove the table is correct. These tests check completeness (every
supported physical control is represented on every required surface),
protocol ranges, and address/key uniqueness. A handful of numbers are
also checked against literal values taken directly from the manufacturer
guide and ``docs/hardware-observations.md``, independent of the map, so a
mistake copied into both the map and a test derived from it cannot pass
silently.
"""

from __future__ import annotations

import pytest

from xtouch_compact import Button, Encoder, Fader, FootControl, Layer
from xtouch_compact.device_map import (
    ASSIGNABLE_BUTTONS,
    BUTTON_LED_VALUES,
    ENCODER_RING_DISPLAY_VALUES,
    ENCODER_RING_MODE_VALUES,
    ENCODER_RING_POSITION_MAX,
    ENCODER_RING_POSITION_MIN,
    FOOT_SWITCH_STATUS_LED_VALUES,
    PRESET_LAYER_VALUES,
    RX_BINDINGS,
    RX_CONTROL_INDEX,
    RX_INDEX,
    TX_BINDINGS,
    TX_INDEX,
    Interaction,
    MidiAddress,
    MidiMessageType,
    RxBinding,
    TxBinding,
    _build_rx_control_index,
    _build_rx_index,
    _build_tx_index,
)


def _tx_bindings(interaction: Interaction) -> list:
    return [binding for binding in TX_BINDINGS if binding.interaction is interaction]


class TestTxCompleteness:
    def test_every_fader_has_position_and_touch_on_both_layers(self) -> None:
        for layer in Layer:
            controls = {
                binding.control
                for binding in _tx_bindings(Interaction.FADER_POSITION)
                if binding.layer is layer
            }
            assert controls == set(Fader)
            controls = {
                binding.control
                for binding in _tx_bindings(Interaction.FADER_TOUCH)
                if binding.layer is layer
            }
            assert controls == set(Fader)

    def test_every_encoder_has_turn_and_push_on_both_layers(self) -> None:
        for layer in Layer:
            controls = {
                binding.control
                for binding in _tx_bindings(Interaction.ENCODER_TURN)
                if binding.layer is layer
            }
            assert controls == set(Encoder)
            controls = {
                binding.control
                for binding in _tx_bindings(Interaction.ENCODER_PUSH)
                if binding.layer is layer
            }
            assert controls == set(Encoder)

    def test_every_assignable_button_is_mapped_on_both_layers(self) -> None:
        for layer in Layer:
            controls = {
                binding.control
                for binding in _tx_bindings(Interaction.BUTTON)
                if binding.layer is layer
            }
            assert controls == set(ASSIGNABLE_BUTTONS)
        assert Button.LAYER_A not in ASSIGNABLE_BUTTONS
        assert Button.LAYER_B not in ASSIGNABLE_BUTTONS

    def test_both_foot_controls_are_mapped_on_both_layers(self) -> None:
        for layer in Layer:
            controls = {
                binding.control
                for binding in _tx_bindings(Interaction.FOOT_CONTROL)
                if binding.layer is layer
            }
            assert controls == set(FootControl)


class TestRxCompleteness:
    def test_every_fader_has_a_position_rx_mapping(self) -> None:
        for fader in Fader:
            assert (fader, "position") in RX_CONTROL_INDEX

    def test_every_assignable_button_has_an_led_rx_mapping(self) -> None:
        for button in ASSIGNABLE_BUTTONS:
            assert (button, "led") in RX_CONTROL_INDEX
        for button in (Button.LAYER_A, Button.LAYER_B):
            assert (button, "led") not in RX_CONTROL_INDEX

    def test_every_encoder_has_ring_behavior_and_ring_value_rx_mappings(self) -> None:
        for encoder in Encoder:
            assert (encoder, "ring_behavior") in RX_CONTROL_INDEX
            assert (encoder, "ring_value") in RX_CONTROL_INDEX

    def test_foot_switch_has_a_status_led_rx_mapping_but_expression_pedal_does_not(
        self,
    ) -> None:
        assert (FootControl.FOOT_SWITCH, "status_led") in RX_CONTROL_INDEX
        assert (FootControl.EXPRESSION_PEDAL, "status_led") not in RX_CONTROL_INDEX


class TestAddressRanges:
    def test_every_tx_address_is_within_midi_ranges(self) -> None:
        for binding in TX_BINDINGS:
            address = binding.address
            assert address.midi_channel is not None
            assert 1 <= address.midi_channel <= 16
            if address.message_type is not MidiMessageType.PROGRAM_CHANGE:
                assert address.number is not None
                assert 0 <= address.number <= 127

    def test_every_rx_address_is_within_midi_ranges(self) -> None:
        for binding in RX_BINDINGS:
            address = binding.address
            if address.message_type is not MidiMessageType.PROGRAM_CHANGE:
                assert address.number is not None
                assert 0 <= address.number <= 127

    def test_protocol_values_stay_within_seven_bit_range(self) -> None:
        for mapping in (
            BUTTON_LED_VALUES,
            ENCODER_RING_MODE_VALUES,
            ENCODER_RING_DISPLAY_VALUES,
            PRESET_LAYER_VALUES,
            FOOT_SWITCH_STATUS_LED_VALUES,
        ):
            for value in mapping.values():
                assert 0 <= value <= 127

    def test_encoder_ring_position_offsets_stay_within_seven_bit_range(self) -> None:
        for offset_name in ("position_offset", "blinking_position_offset"):
            assert (
                ENCODER_RING_DISPLAY_VALUES[offset_name] + ENCODER_RING_POSITION_MAX
                <= 127
            )
        assert 1 <= ENCODER_RING_POSITION_MIN <= ENCODER_RING_POSITION_MAX <= 13


class TestAddressUniqueness:
    def test_tx_addresses_are_unambiguous_within_each_layer(self) -> None:
        for bindings in TX_INDEX.values():
            layers = [binding.layer for binding in bindings]
            assert len(layers) == len(set(layers))

    def test_rx_addresses_are_unique(self) -> None:
        addresses = [binding.address for binding in RX_BINDINGS]
        assert len(addresses) == len(set(addresses))
        assert len(RX_INDEX) == len(addresses)

    def test_rx_control_operations_are_unique(self) -> None:
        keys = [(binding.control, binding.operation) for binding in RX_BINDINGS]
        assert len(keys) == len(set(keys))
        assert len(RX_CONTROL_INDEX) == len(keys)


class TestAmbiguityGuards:
    """The index builders raise at construction time on a duplicate address
    or control/operation key, rather than silently letting one entry shadow
    another. These are exercised directly, against crafted duplicates, since
    the real tables (already proven unique above) never trigger them."""

    def test_build_tx_index_rejects_two_bindings_on_same_layer_and_address(
        self,
    ) -> None:
        address = MidiAddress(MidiMessageType.CONTROL_CHANGE, 1, 1)
        duplicate = (
            TxBinding(Layer.A, 1, address, Fader.CHANNEL_1, Interaction.FADER_POSITION),
            TxBinding(Layer.A, 1, address, Fader.CHANNEL_2, Interaction.FADER_POSITION),
        )

        with pytest.raises(AssertionError, match="ambiguous TX address"):
            _build_tx_index(duplicate)

    def test_build_rx_index_rejects_two_bindings_on_the_same_address(self) -> None:
        address = MidiAddress(MidiMessageType.CONTROL_CHANGE, 1)
        duplicate = (
            RxBinding(address, Fader.CHANNEL_1, "position"),
            RxBinding(address, Fader.CHANNEL_2, "position"),
        )

        with pytest.raises(AssertionError, match="duplicate RX address"):
            _build_rx_index(duplicate)

    def test_build_rx_control_index_rejects_two_bindings_for_same_control_operation(
        self,
    ) -> None:
        duplicate = (
            RxBinding(
                MidiAddress(MidiMessageType.CONTROL_CHANGE, 1),
                Fader.CHANNEL_1,
                "position",
            ),
            RxBinding(
                MidiAddress(MidiMessageType.CONTROL_CHANGE, 2),
                Fader.CHANNEL_1,
                "position",
            ),
        )

        with pytest.raises(AssertionError, match="duplicate RX control operation"):
            _build_rx_control_index(duplicate)


class TestLiteralProtocolVectors:
    """Values copied directly from the manufacturer guide, independent of the map."""

    def test_layer_a_fader_1_position_and_touch(self) -> None:
        binding = RX_CONTROL_INDEX[(Fader.CHANNEL_1, "position")]
        assert binding.address == MidiAddress(MidiMessageType.CONTROL_CHANGE, 1)
        tx = [
            b
            for b in TX_BINDINGS
            if b.layer is Layer.A
            and b.control is Fader.CHANNEL_1
            and b.interaction is Interaction.FADER_POSITION
        ][0]
        assert tx.address.number == 1
        touch = [
            b
            for b in TX_BINDINGS
            if b.layer is Layer.A
            and b.control is Fader.CHANNEL_1
            and b.interaction is Interaction.FADER_TOUCH
        ][0]
        assert touch.address.number == 101

    def test_layer_b_master_fader_position_and_touch(self) -> None:
        tx = [
            b
            for b in TX_BINDINGS
            if b.layer is Layer.B
            and b.control is Fader.MAIN
            and b.interaction is Interaction.FADER_POSITION
        ][0]
        assert tx.address.number == 36
        touch = [
            b
            for b in TX_BINDINGS
            if b.layer is Layer.B
            and b.control is Fader.MAIN
            and b.interaction is Interaction.FADER_TOUCH
        ][0]
        assert touch.address.number == 119

    def test_layer_b_encoder_16_push_note(self) -> None:
        tx = [
            b
            for b in TX_BINDINGS
            if b.layer is Layer.B
            and b.control is Encoder.POSITION_16
            and b.interaction is Interaction.ENCODER_PUSH
        ][0]
        assert tx.address.number == 70

    def test_layer_b_last_button_note(self) -> None:
        tx = [
            b
            for b in TX_BINDINGS
            if b.layer is Layer.B
            and b.control is Button.PLAY
            and b.interaction is Interaction.BUTTON
        ][0]
        assert tx.address.number == 109

    def test_button_led_numbers_span_zero_to_thirty_eight(self) -> None:
        numbers = {
            RX_CONTROL_INDEX[(button, "led")].address.number
            for button in ASSIGNABLE_BUTTONS
        }
        assert numbers == set(range(39))

    def test_foot_switch_status_led_number_is_forty_two(self) -> None:
        binding = RX_CONTROL_INDEX[(FootControl.FOOT_SWITCH, "status_led")]
        assert binding.address.number == 42
