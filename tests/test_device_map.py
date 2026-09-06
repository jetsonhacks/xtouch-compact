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
    classify_rx_message,
    matches_layer_program_change,
)
from xtouch_compact.midi import ControlChange, NoteOn, ProgramChange


@pytest.mark.parametrize("layer", list(Layer))
@pytest.mark.parametrize(
    ("interaction", "controls"),
    [
        (Interaction.FADER_POSITION, set(Fader)),
        (Interaction.FADER_TOUCH, set(Fader)),
        (Interaction.ENCODER_TURN, set(Encoder)),
        (Interaction.ENCODER_PUSH, set(Encoder)),
        (Interaction.BUTTON, set(Button) - {Button.LAYER_A, Button.LAYER_B}),
        (Interaction.FOOT_CONTROL, set(FootControl)),
    ],
)
def test_tx_completeness(layer, interaction, controls) -> None:
    bindings = [
        b for b in TX_BINDINGS if b.layer is layer and b.interaction is interaction
    ]
    assert {b.control for b in bindings} == controls
    assert len(bindings) == len(controls)


def test_rx_completeness() -> None:
    buttons = set(Button) - {Button.LAYER_A, Button.LAYER_B}
    assert set(ASSIGNABLE_BUTTONS) == buttons
    expected = (
        {(fader, "position") for fader in Fader}
        | {(button, "led") for button in buttons}
        | {
            (encoder, op)
            for encoder in Encoder
            for op in ("ring_behavior", "ring_value")
        }
        | {(FootControl.FOOT_SWITCH, "status_led")}
    )
    assert set(RX_CONTROL_INDEX) == expected


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


# Literal first/last addresses from Quick Start Guide V6.0 pp. 29–30.
# These expectations do not read the runtime's bases, enum order, or YAML.
@pytest.mark.parametrize("layer", [Layer.A, Layer.B])
@pytest.mark.parametrize(
    ("interaction", "first", "last", "a_numbers", "b_numbers", "message_type"),
    [
        (
            "fader_position",
            Fader.CHANNEL_1,
            Fader.MAIN,
            (1, 9),
            (28, 36),
            "control_change",
        ),
        (
            "fader_touch",
            Fader.CHANNEL_1,
            Fader.MAIN,
            (101, 109),
            (111, 119),
            "control_change",
        ),
        (
            "encoder_turn",
            Encoder.CHANNEL_1,
            Encoder.POSITION_16,
            (10, 25),
            (37, 52),
            "control_change",
        ),
        (
            "encoder_push",
            Encoder.CHANNEL_1,
            Encoder.POSITION_16,
            (0, 15),
            (55, 70),
            "note",
        ),
        ("button", Button.UPPER_TOP_1, Button.PLAY, (16, 54), (71, 109), "note"),
        (
            "foot_control",
            FootControl.EXPRESSION_PEDAL,
            FootControl.FOOT_SWITCH,
            (26, 27),
            (63, 64),
            "control_change",
        ),
    ],
)
def test_tx_protocol_boundaries(
    layer, interaction, first, last, a_numbers, b_numbers, message_type
) -> None:
    numbers = a_numbers if layer is Layer.A else b_numbers
    for control, number in zip((first, last), numbers, strict=True):
        bindings = [
            b
            for b in TX_BINDINGS
            if b.layer is layer
            and b.control is control
            and b.interaction is Interaction(interaction)
        ]
        assert len(bindings) == 1
        binding = bindings[0]
        assert binding.address == MidiAddress(MidiMessageType(message_type), number, 1)
        assert binding.midi_channel == 1


# RX MIDI DATA, p. 32. Button RX notes differ from TX notes above.
@pytest.mark.parametrize(
    ("operation", "first", "last", "numbers", "message_type"),
    [
        ("position", Fader.CHANNEL_1, Fader.MAIN, (1, 9), "control_change"),
        ("led", Button.UPPER_TOP_1, Button.PLAY, (0, 38), "note"),
        (
            "ring_behavior",
            Encoder.CHANNEL_1,
            Encoder.POSITION_16,
            (10, 25),
            "control_change",
        ),
        (
            "ring_value",
            Encoder.CHANNEL_1,
            Encoder.POSITION_16,
            (26, 41),
            "control_change",
        ),
        (
            "status_led",
            FootControl.FOOT_SWITCH,
            FootControl.FOOT_SWITCH,
            (42, 42),
            "control_change",
        ),
    ],
)
def test_rx_protocol_boundaries(operation, first, last, numbers, message_type) -> None:
    for control, number in zip((first, last), numbers, strict=True):
        assert RX_CONTROL_INDEX[(control, operation)].address == MidiAddress(
            MidiMessageType(message_type), number
        )


def test_classify_rx_message_matches_a_tracked_address_on_the_right_channel() -> None:
    binding = RX_CONTROL_INDEX[(Button.PLAY, "led")]

    result = classify_rx_message(NoteOn(2, binding.address.number, 0), 2)

    assert result is binding


def test_classify_rx_message_ignores_the_wrong_channel() -> None:
    binding = RX_CONTROL_INDEX[(Button.PLAY, "led")]

    assert classify_rx_message(NoteOn(5, binding.address.number, 0), 2) is None
    assert (
        classify_rx_message(
            ControlChange(
                5, RX_CONTROL_INDEX[(Fader.CHANNEL_1, "position")].address.number, 0
            ),
            2,
        )
        is None
    )


def test_classify_rx_message_ignores_an_unmapped_address() -> None:
    assert classify_rx_message(NoteOn(2, 100, 0), 2) is None


def test_classify_rx_message_ignores_program_change() -> None:
    """Layer selection has no RX binding; see matches_layer_program_change."""
    assert classify_rx_message(ProgramChange(2, 0), 2) is None


@pytest.mark.parametrize("program_number", sorted(PRESET_LAYER_VALUES.values()))
def test_matches_layer_program_change_accepts_every_preset_value_on_channel(
    program_number: int,
) -> None:
    assert matches_layer_program_change(ProgramChange(2, program_number), 2)


def test_matches_layer_program_change_rejects_wrong_channel_and_value() -> None:
    assert not matches_layer_program_change(ProgramChange(5, 0), 2)
    assert not matches_layer_program_change(NoteOn(2, 0, 0), 2)
