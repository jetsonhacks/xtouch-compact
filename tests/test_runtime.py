from collections.abc import Callable

import pytest

from tests.helpers import make_session
from xtouch_compact import (
    Button,
    ButtonLedState,
    ControlChange,
    DeviceSpecification,
    DiscoveryError,
    Encoder,
    EncoderRingDisplay,
    EncoderRingMode,
    Fader,
    FaderOwner,
    Layer,
    NoteOn,
    ProgramChange,
    SessionState,
    StatusLedState,
    TransportConnectionError,
    XTouchCompactSession,
)


class RuntimeTransport:
    def __init__(self, connect_results: list[object]) -> None:
        self.connect_results = list(connect_results)
        self.connected = False
        self.endpoint: object | None = None
        self.incoming: list[object] = []
        self.sent: list[object] = []
        self.actions: list[tuple[str, object | None]] = []
        self.open_resources = 0
        self.fail_receive = False
        self.send_failure: tuple[Callable[[object], bool], BaseException] | None = None

    def connect(self) -> object:
        result = self.connect_results.pop(0)
        self.actions.append(("connect", result))
        if isinstance(result, BaseException):
            raise result
        self.connected = True
        self.endpoint = result
        self.open_resources += 1
        return result

    def receive(self, timeout: float | None = None) -> object | None:
        if self.fail_receive:
            self.fail_receive = False
            raise TransportConnectionError("device disappeared during receive")
        return self.incoming.pop(0) if self.incoming else None

    def send(self, message: object) -> None:
        self.actions.append(("send", message))
        failure = self.send_failure
        if failure is not None and failure[0](message):
            self.send_failure = None
            raise failure[1]
        self.sent.append(message)

    def close(self) -> None:
        self.actions.append(("close", self.endpoint))
        if self.connected:
            self.open_resources -= 1
        self.connected = False
        self.endpoint = None


def runtime_session(
    specification: DeviceSpecification, transport: RuntimeTransport
) -> XTouchCompactSession:
    return make_session(specification, transport)


def ready_runtime_session(
    specification: DeviceSpecification,
    connect_results: list[object] | None = None,
) -> tuple[XTouchCompactSession, RuntimeTransport]:
    transport = RuntimeTransport(connect_results or [(24, 0)])
    session = runtime_session(specification, transport)
    session.connect()
    session.initialize()
    transport.actions.clear()
    transport.sent.clear()
    return session, transport


def test_device_absent_at_startup_leaves_session_retryable(
    specification: DeviceSpecification,
) -> None:
    missing = DiscoveryError("no matching device")
    transport = RuntimeTransport([missing, (31, 0)])
    session = runtime_session(specification, transport)

    with pytest.raises(DiscoveryError, match="no matching"):
        session.connect()

    assert session.state is SessionState.DISCONNECTED
    assert transport.open_resources == 0

    session.connect()
    assert session.state is SessionState.STARTUP_LAYER_UNASSERTED
    session.initialize()
    assert session.state is SessionState.READY
    assert transport.endpoint == (31, 0)


def test_keyboard_interrupt_during_connect_leaves_session_retryable(
    specification: DeviceSpecification,
) -> None:
    transport = RuntimeTransport([KeyboardInterrupt(), (31, 0)])
    session = runtime_session(specification, transport)

    with pytest.raises(KeyboardInterrupt):
        session.connect()

    assert session.state is SessionState.DISCONNECTED
    assert transport.open_resources == 0

    session.connect()
    session.initialize()
    assert session.state is SessionState.READY
    assert transport.endpoint == (31, 0)


def test_keyboard_interrupt_during_reconnect_leaves_disconnected(
    specification: DeviceSpecification,
) -> None:
    session, transport = ready_runtime_session(specification, [(24, 0), (31, 0)])
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    transport.send_failure = (
        lambda message: isinstance(message, ProgramChange),
        KeyboardInterrupt(),
    )

    with pytest.raises(KeyboardInterrupt):
        session.reconnect()

    assert session.state is SessionState.DISCONNECTED
    assert transport.open_resources == 0
    assert session.button_feedback_state(Button.PLAY).desired is ButtonLedState.ON


def test_connection_loss_during_send_preserves_desired_feedback(
    specification: DeviceSpecification,
) -> None:
    session, transport = ready_runtime_session(specification, [(24, 0), (31, 0)])
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    transport.send_failure = (
        lambda message: isinstance(message, NoteOn),
        TransportConnectionError("device disappeared during send"),
    )

    with pytest.raises(TransportConnectionError, match="during send"):
        session.set_button_led(Button.PLAY, ButtonLedState.BLINK)

    feedback = session.button_feedback_state(Button.PLAY)
    assert session.state is SessionState.DISCONNECTED
    assert feedback.desired is ButtonLedState.BLINK
    assert feedback.last_sent is None
    assert transport.open_resources == 0

    session.reconnect()
    assert session.state is SessionState.READY
    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.BLINK


def test_connection_loss_during_receive_resets_live_fader_state(
    specification: DeviceSpecification,
) -> None:
    session, transport = ready_runtime_session(specification, [(24, 0), (31, 0)])
    transport.incoming.append(ControlChange(1, 101, 127))
    session.receive_input()
    session.set_fader(Fader.CHANNEL_1, 70)
    assert session.fader_state(Fader.CHANNEL_1).owner is FaderOwner.HUMAN
    transport.fail_receive = True

    with pytest.raises(TransportConnectionError, match="during receive"):
        session.receive_input()

    state = session.fader_state(Fader.CHANNEL_1)
    assert session.state is SessionState.DISCONNECTED
    assert state.owner is FaderOwner.APPLICATION
    assert not state.touched
    assert state.desired_value is None
    assert state.observed_value is None
    assert transport.open_resources == 0

    session.reconnect()
    assert session.fader_state(Fader.CHANNEL_1).owner is FaderOwner.APPLICATION
    assert session.fader_state(Fader.CHANNEL_1).desired_value is None
    assert ControlChange(2, 1, 70) not in transport.sent


def test_reconnect_uses_new_endpoint_initializes_then_restores_feedback(
    specification: DeviceSpecification,
) -> None:
    session, transport = ready_runtime_session(specification, [(24, 0), (31, 0)])
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    session.set_encoder_ring_mode(Encoder.CHANNEL_1, EncoderRingMode.PAN)
    session.set_encoder_ring_value(Encoder.CHANNEL_1, EncoderRingDisplay.at(7))
    session.select_layer(Layer.B)
    session.set_foot_switch_led(StatusLedState.ON)
    session.set_fader(Fader.CHANNEL_1, 88)
    transport.actions.clear()
    transport.sent.clear()

    session.reconnect()

    sends = [value for action, value in transport.actions if action == "send"]
    assert session.state is SessionState.READY
    assert transport.endpoint == (31, 0)
    assert sends[0] == ProgramChange(2, 1)
    assert sum(isinstance(message, ProgramChange) for message in sends) == 1
    assert any(isinstance(message, NoteOn) for message in sends[1:])
    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.ON
    assert session.encoder_feedback_state(Encoder.CHANNEL_1).last_sent_mode is (
        EncoderRingMode.PAN
    )
    assert session.status_feedback_state().last_sent is StatusLedState.ON
    assert session.fader_state(Fader.CHANNEL_1).desired_value is None
    assert ControlChange(2, 1, 88) not in sends


@pytest.mark.parametrize(
    ("failure_match", "failure"),
    [
        (
            lambda message: isinstance(message, ProgramChange),
            TransportConnectionError("initialization failed"),
        ),
        (
            lambda message: isinstance(message, NoteOn),
            RuntimeError("feedback restoration failed"),
        ),
    ],
)
def test_failed_reconnect_never_reports_ready(
    specification: DeviceSpecification,
    failure_match: Callable[[object], bool],
    failure: Exception,
) -> None:
    session, transport = ready_runtime_session(specification, [(24, 0), (31, 0)])
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    transport.send_failure = (failure_match, failure)

    with pytest.raises(type(failure), match=str(failure)):
        session.reconnect()

    assert session.state is SessionState.DISCONNECTED
    assert transport.open_resources == 0
    assert session.button_feedback_state(Button.PLAY).desired is ButtonLedState.ON
    assert session.button_feedback_state(Button.PLAY).last_sent is None


def test_ambiguous_rediscovery_remains_an_explicit_failure(
    specification: DeviceSpecification,
) -> None:
    ambiguity = DiscoveryError("multiple bidirectional ports match")
    session, transport = ready_runtime_session(specification, [(24, 0), ambiguity])

    with pytest.raises(DiscoveryError, match="multiple"):
        session.reconnect()

    assert session.state is SessionState.DISCONNECTED
    assert transport.open_resources == 0


def test_repeated_reconnect_and_close_cycles_do_not_leak_resources(
    specification: DeviceSpecification,
) -> None:
    session, transport = ready_runtime_session(
        specification, [(24, 0), (31, 0), (32, 1)]
    )
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    transport.sent.clear()

    session.reconnect()
    assert transport.open_resources == 1
    assert sum(isinstance(message, NoteOn) for message in transport.sent) == 1
    transport.sent.clear()
    session.reconnect()
    assert transport.open_resources == 1
    assert transport.endpoint == (32, 1)
    assert sum(isinstance(message, NoteOn) for message in transport.sent) == 1

    session.close()
    session.close()
    assert session.state is SessionState.DISCONNECTED
    assert transport.open_resources == 0
