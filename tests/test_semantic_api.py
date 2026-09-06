import pytest

from tests.helpers import FakeTransport, SessionFactory
from xtouch_compact import (
    Button,
    ButtonLedState,
    ControlChange,
    Encoder,
    EncoderRingDisplay,
    EncoderRingMode,
    Fader,
    FootControl,
    Layer,
    LifecycleError,
    NoteOn,
    ProgramChange,
    StatusLedState,
    UnsupportedOperationError,
    XTouchCompactSession,
)
from xtouch_compact.device_map import RX_CONTROL_INDEX


@pytest.mark.parametrize("fader", list(Fader))
@pytest.mark.parametrize("value", [0, 64, 127])
def test_set_fader_resolves_every_rx_address_from_device_map(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    fader: Fader,
    value: int,
) -> None:
    device, transport = ready_session
    binding = RX_CONTROL_INDEX[(fader, "position")]

    device.set_fader(fader, value)

    assert transport.sent == [ControlChange(2, binding.address.number, value)]
    assert device.fader_state(fader).desired_value == value
    assert device.fader_state(fader).last_commanded_value == value


@pytest.mark.parametrize("value", [-1, 128, True, 1.5])
def test_set_fader_reuses_typed_midi_value_validation(
    ready_session: tuple[XTouchCompactSession, FakeTransport], value: object
) -> None:
    device, transport = ready_session

    with pytest.raises((TypeError, ValueError), match="value"):
        device.set_fader(Fader.CHANNEL_1, value)  # type: ignore[arg-type]

    assert transport.sent == []


def test_every_assignable_button_led_resolves_from_device_map(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    device, transport = ready_session
    assignable = [
        button for button in Button if button not in {Button.LAYER_A, Button.LAYER_B}
    ]

    for button in assignable:
        device.set_button_led(button, ButtonLedState.ON)

    expected = [
        NoteOn(
            2,
            RX_CONTROL_INDEX[(button, "led")].address.number,
            2,
        )
        for button in assignable
    ]
    assert transport.sent == expected


@pytest.mark.parametrize(
    ("state", "velocity"),
    [
        (ButtonLedState.OFF, 0),
        (ButtonLedState.ON, 2),
        (ButtonLedState.BLINK, 3),
    ],
)
def test_button_led_states_use_characterized_device_map_values(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    state: ButtonLedState,
    velocity: int,
) -> None:
    device, transport = ready_session
    binding = RX_CONTROL_INDEX[(Button.RECORD, "led")]

    device.set_button_led(Button.RECORD, state)

    assert transport.sent == [NoteOn(2, binding.address.number, velocity)]


@pytest.mark.parametrize("button", [Button.LAYER_A, Button.LAYER_B])
def test_layer_indicators_are_not_assignable_button_leds(
    ready_session: tuple[XTouchCompactSession, FakeTransport], button: Button
) -> None:
    device, transport = ready_session

    with pytest.raises(ValueError, match="no led RX mapping"):
        device.set_button_led(button, ButtonLedState.ON)

    assert transport.sent == []


@pytest.mark.parametrize("encoder", list(Encoder))
@pytest.mark.parametrize(
    ("mode", "encoded"),
    [
        (EncoderRingMode.SINGLE, 0),
        (EncoderRingMode.PAN, 1),
        (EncoderRingMode.FAN, 2),
        (EncoderRingMode.SPREAD, 3),
        (EncoderRingMode.TRIM, 4),
    ],
)
def test_every_encoder_supports_every_ring_mode_from_its_rx_binding(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    encoder: Encoder,
    mode: EncoderRingMode,
    encoded: int,
) -> None:
    # Quick Start Guide V6.0, RX MIDI DATA p. 32. Values are independent of
    # the runtime map; address routing is separately checked in test_device_map.
    device, transport = ready_session
    binding = RX_CONTROL_INDEX[(encoder, "ring_behavior")]

    device.set_encoder_ring_mode(encoder, mode)

    assert transport.sent == [ControlChange(2, binding.address.number, encoded)]


@pytest.mark.parametrize("encoder", list(Encoder))
def test_every_encoder_supports_ring_display_output(
    ready_session: tuple[XTouchCompactSession, FakeTransport], encoder: Encoder
) -> None:
    device, transport = ready_session
    binding = RX_CONTROL_INDEX[(encoder, "ring_value")]

    device.set_encoder_ring_value(encoder, EncoderRingDisplay.off())

    assert transport.sent == [ControlChange(2, binding.address.number, 0)]


@pytest.mark.parametrize(
    ("factory_name", "factory_args", "encoded"),
    [
        ("off", (), 0),
        ("at", (1,), 1),
        ("at", (7,), 7),
        ("at", (13,), 13),
        ("blinking_at", (1,), 14),
        ("blinking_at", (13,), 26),
        ("all_on", (), 27),
        ("all_blinking", (), 28),
    ],
)
def test_encoder_ring_display_encodings_come_from_device_map(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    factory_name: str,
    factory_args: tuple[int, ...],
    encoded: int,
) -> None:
    device, transport = ready_session
    binding = RX_CONTROL_INDEX[(Encoder.CHANNEL_1, "ring_value")]
    display = getattr(EncoderRingDisplay, factory_name)(*factory_args)

    device.set_encoder_ring_value(Encoder.CHANNEL_1, display)

    assert transport.sent == [ControlChange(2, binding.address.number, encoded)]


@pytest.mark.parametrize("position", [0, 14])
def test_encoder_ring_display_rejects_invalid_positions_before_transport(
    ready_session: tuple[XTouchCompactSession, FakeTransport], position: int
) -> None:
    device, transport = ready_session

    with pytest.raises(
        UnsupportedOperationError, match="position must be from 1 through 13"
    ):
        device.set_encoder_ring_value(
            Encoder.CHANNEL_1, EncoderRingDisplay.at(position)
        )

    assert transport.sent == []


def test_encoder_ring_display_rejects_invalid_kind() -> None:
    with pytest.raises(TypeError, match="EncoderRingDisplayKind"):
        EncoderRingDisplay("position", 1)  # type: ignore[arg-type]


def test_layer_selection_uses_same_device_map_mapping_as_initialization(
    build_session: SessionFactory,
) -> None:
    device, transport = build_session(global_midi_channel=7, startup_layer=Layer.B)

    device.connect()
    device.initialize()
    device.select_layer(Layer.A)

    # Quick Start Guide V6.0 p. 32: B=1, A=0 on the configured RX channel.
    assert transport.sent == [ProgramChange(7, 1), ProgramChange(7, 0)]


@pytest.mark.parametrize(
    ("state", "encoded"),
    [(StatusLedState.OFF, 0), (StatusLedState.ON, 127)],
)
def test_foot_switch_status_led_uses_its_rx_mapping(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    state: StatusLedState,
    encoded: int,
) -> None:
    device, transport = ready_session
    binding = RX_CONTROL_INDEX[(FootControl.FOOT_SWITCH, "status_led")]

    device.set_foot_switch_led(state)

    assert transport.sent == [ControlChange(2, binding.address.number, encoded)]


@pytest.mark.parametrize(
    "operation",
    [
        lambda device: device.set_fader(Fader.CHANNEL_1, 64),
        lambda device: device.set_button_led(Button.PLAY, ButtonLedState.ON),
        lambda device: device.set_encoder_ring_mode(
            Encoder.CHANNEL_1, EncoderRingMode.PAN
        ),
        lambda device: device.set_encoder_ring_value(
            Encoder.CHANNEL_1, EncoderRingDisplay.at(7)
        ),
        lambda device: device.select_layer(Layer.B),
        lambda device: device.set_foot_switch_led(StatusLedState.ON),
    ],
)
def test_semantic_output_requires_ready_session(
    build_session: SessionFactory, operation: object
) -> None:
    device, transport = build_session()

    with pytest.raises(LifecycleError, match="disconnected"):
        operation(device)  # type: ignore[operator]

    assert transport.sent == []
