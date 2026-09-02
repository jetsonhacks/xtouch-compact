from pathlib import Path

import pytest

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
    NoteOn,
    ProgramChange,
    StatusLedState,
    XTouchCompactSession,
    load_device_specification,
)

SPEC_PATH = Path(__file__).parents[1] / "specs" / "xtouch-compact-midi.yaml"


class FakeTransport:
    def __init__(self) -> None:
        self.sent: list[object] = []

    def connect(self) -> object:
        return object()

    def receive(self, timeout: float | None = None) -> None:
        return None

    def send(self, message: object) -> None:
        self.sent.append(message)

    def close(self) -> None:
        pass


@pytest.fixture
def ready_session() -> tuple[XTouchCompactSession, FakeTransport]:
    transport = FakeTransport()
    device = XTouchCompactSession(
        transport,
        load_device_specification(SPEC_PATH),
        global_midi_channel=2,
    )
    device.connect()
    device.initialize()
    transport.sent.clear()
    return device, transport


@pytest.mark.parametrize("fader", list(Fader))
@pytest.mark.parametrize("value", [0, 64, 127])
def test_set_fader_resolves_every_rx_address_from_specification(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    fader: Fader,
    value: int,
) -> None:
    device, transport = ready_session
    binding = device._specification.rx_control_index[(fader, "position")]

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


def test_every_assignable_button_led_resolves_from_specification(
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
            device._specification.rx_control_index[(button, "led")].address.number,
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
def test_button_led_states_use_characterized_specification_values(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    state: ButtonLedState,
    velocity: int,
) -> None:
    device, transport = ready_session
    binding = device._specification.rx_control_index[(Button.RECORD, "led")]

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
@pytest.mark.parametrize("mode", list(EncoderRingMode))
def test_every_encoder_supports_every_ring_mode_from_its_rx_binding(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    encoder: Encoder,
    mode: EncoderRingMode,
) -> None:
    device, transport = ready_session
    binding = device._specification.rx_control_index[(encoder, "ring_behavior")]

    device.set_encoder_ring_mode(encoder, mode)

    assert transport.sent == [
        ControlChange(2, binding.address.number, binding.details["values"][mode.value])
    ]


@pytest.mark.parametrize("encoder", list(Encoder))
def test_every_encoder_supports_ring_display_output(
    ready_session: tuple[XTouchCompactSession, FakeTransport], encoder: Encoder
) -> None:
    device, transport = ready_session
    binding = device._specification.rx_control_index[(encoder, "ring_value")]

    device.set_encoder_ring_value(encoder, EncoderRingDisplay.off())

    assert transport.sent == [ControlChange(2, binding.address.number, 0)]


@pytest.mark.parametrize(
    ("display", "encoded"),
    [
        (EncoderRingDisplay.off(), 0),
        (EncoderRingDisplay.at(1), 1),
        (EncoderRingDisplay.at(7), 7),
        (EncoderRingDisplay.at(13), 13),
        (EncoderRingDisplay.blinking_at(1), 14),
        (EncoderRingDisplay.blinking_at(13), 26),
        (EncoderRingDisplay.all_on(), 27),
        (EncoderRingDisplay.all_blinking(), 28),
    ],
)
def test_encoder_ring_display_encodings_come_from_specification(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    display: EncoderRingDisplay,
    encoded: int,
) -> None:
    device, transport = ready_session
    binding = device._specification.rx_control_index[(Encoder.CHANNEL_1, "ring_value")]

    device.set_encoder_ring_value(Encoder.CHANNEL_1, display)

    assert transport.sent == [ControlChange(2, binding.address.number, encoded)]


@pytest.mark.parametrize("position", [0, 14])
def test_encoder_ring_display_rejects_invalid_positions_before_transport(
    ready_session: tuple[XTouchCompactSession, FakeTransport], position: int
) -> None:
    device, transport = ready_session

    with pytest.raises(ValueError, match="position must be from 1 through 13"):
        device.set_encoder_ring_value(
            Encoder.CHANNEL_1, EncoderRingDisplay.at(position)
        )

    assert transport.sent == []


def test_encoder_ring_display_rejects_invalid_kind() -> None:
    with pytest.raises(TypeError, match="EncoderRingDisplayKind"):
        EncoderRingDisplay("position", 1)  # type: ignore[arg-type]


def test_layer_selection_uses_same_specification_mapping_as_initialization() -> None:
    specification = load_device_specification(SPEC_PATH)
    transport = FakeTransport()
    device = XTouchCompactSession(
        transport,
        specification,
        global_midi_channel=7,
        startup_layer=Layer.B,
    )

    device.connect()
    device.initialize()
    device.select_layer(Layer.A)

    values = specification.rx_control_index[(None, "preset_layer")].details["values"]
    assert transport.sent == [
        ProgramChange(7, values[Layer.B.value]),
        ProgramChange(7, values[Layer.A.value]),
    ]


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
    binding = device._specification.rx_control_index[
        (FootControl.FOOT_SWITCH, "status_led")
    ]

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
def test_semantic_output_requires_ready_session(operation: object) -> None:
    transport = FakeTransport()
    device = XTouchCompactSession(
        transport,
        load_device_specification(SPEC_PATH),
        global_midi_channel=2,
    )

    with pytest.raises(RuntimeError, match="unasserted"):
        operation(device)  # type: ignore[operator]

    assert transport.sent == []
