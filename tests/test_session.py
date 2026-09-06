import pytest

from tests.helpers import FakeTransport, SessionFactory
from xtouch_compact import (
    Button,
    ButtonPressed,
    ControlChange,
    Layer,
    LifecycleError,
    NoteOn,
    ProgramChange,
    SessionConfigurationError,
    SessionState,
    XTouchCompactSession,
)


def test_post_connect_layer_initialization_is_explicit_session_policy(
    build_session: SessionFactory,
) -> None:
    device_session, transport = build_session(startup_layer=Layer.B)

    device_session.connect()
    assert device_session.state is SessionState.STARTUP_LAYER_UNASSERTED
    assert transport.sent == []

    device_session.initialize()
    assert device_session.state is SessionState.READY
    assert transport.sent == [ProgramChange(2, 1)]


def test_receive_pipeline_decodes_message_and_preserves_raw_input(
    build_session: SessionFactory,
) -> None:
    device_session, _ = build_session(FakeTransport([NoteOn(1, 54, 127)]), ready=True)

    received = device_session.receive_input()

    assert received is not None
    assert received.message == NoteOn(1, 54, 127)
    assert isinstance(received.physical_event, ButtonPressed)
    assert received.physical_event.button is Button.PLAY


def test_receive_returns_the_decoded_event(build_session: SessionFactory) -> None:
    session, _ = build_session(FakeTransport([NoteOn(1, 54, 127)]), ready=True)
    event = session.receive()
    assert isinstance(event, ButtonPressed)
    assert event.button is Button.PLAY


@pytest.mark.parametrize("method", ["receive", "receive_input"])
def test_receive_returns_none_when_transport_has_no_message(
    ready_session: tuple[XTouchCompactSession, FakeTransport], method: str
) -> None:
    session, _ = ready_session
    assert getattr(session, method)(timeout=0) is None


def test_initialize_twice_rejects_without_sending(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    with pytest.raises(LifecycleError, match="unasserted"):
        session.initialize()
    assert session.state is SessionState.READY
    assert transport.sent == []


def test_decoder_none_does_not_fail_receive_pipeline(
    build_session: SessionFactory,
) -> None:
    raw = ControlChange(2, 1, 64)
    device_session, _ = build_session(FakeTransport([raw]), ready=True)

    received = device_session.receive_input()

    assert received is not None
    assert received.message == raw
    assert received.physical_event is None


def test_inbound_program_change_is_preserved_as_unsupported_device_input(
    build_session: SessionFactory,
) -> None:
    raw = ProgramChange(2, 0)
    device_session, _ = build_session(FakeTransport([raw]), ready=True)

    received = device_session.receive_input()

    assert received is not None
    assert received.message == raw
    assert received.physical_event is None


def test_session_blocks_input_until_layer_is_asserted_and_resets_on_close(
    build_session: SessionFactory,
) -> None:
    device_session, transport = build_session()
    device_session.connect()

    with pytest.raises(LifecycleError, match="unasserted"):
        device_session.receive()

    device_session.close()
    assert device_session.state is SessionState.DISCONNECTED
    assert transport.closed


@pytest.mark.parametrize("channel", [0, 17, True])
def test_session_validates_global_midi_channel(channel: object) -> None:
    with pytest.raises(SessionConfigurationError, match="global_midi_channel"):
        XTouchCompactSession(
            FakeTransport(),
            global_midi_channel=channel,  # type: ignore[arg-type]
        )


def test_session_validates_startup_layer() -> None:
    with pytest.raises(SessionConfigurationError, match="startup_layer"):
        XTouchCompactSession(
            FakeTransport(),
            global_midi_channel=2,
            startup_layer="layer_a",  # type: ignore[arg-type]
        )


def test_open_constructs_a_disconnected_session() -> None:
    transport = FakeTransport()
    session = XTouchCompactSession.open(
        global_midi_channel=2,
        transport=transport,
    )

    assert session.state is SessionState.DISCONNECTED
    assert not transport.connected


def test_open_context_manager_connects_initializes_and_closes() -> None:
    transport = FakeTransport()
    session = XTouchCompactSession.open(
        global_midi_channel=2,
        startup_layer=Layer.B,
        transport=transport,
    )

    with session as entered:
        assert entered is session
        assert session.state is SessionState.READY
        assert transport.sent == [ProgramChange(2, 1)]

    assert session.state is SessionState.DISCONNECTED
    assert transport.closed


def test_open_defaults_to_alsa_transport_without_connecting() -> None:
    session = XTouchCompactSession.open(global_midi_channel=2)

    assert session.state is SessionState.DISCONNECTED


def test_open_rejects_port_name_with_a_custom_transport() -> None:
    with pytest.raises(SessionConfigurationError, match="port_name"):
        XTouchCompactSession.open(
            global_midi_channel=2,
            transport=FakeTransport(),
            port_name="MIDI 1",
        )


def test_ready_methods_report_disconnected_versus_unasserted(
    build_session: SessionFactory,
) -> None:
    device_session, _ = build_session()

    with pytest.raises(LifecycleError, match="disconnected"):
        device_session.receive()

    device_session.connect()
    with pytest.raises(LifecycleError, match="unasserted"):
        device_session.receive()


def test_double_connect_is_a_lifecycle_error(build_session: SessionFactory) -> None:
    device_session, _ = build_session()
    device_session.connect()
    with pytest.raises(LifecycleError):
        device_session.connect()


def test_session_is_connecting_and_rejects_reentry_during_transport_connect() -> None:
    """A caller-supplied transport runs inside connect(), so CONNECTING is visible.

    It is the state that makes a re-entrant connect() raise instead of
    recursing, and that reports "still connecting" rather than a misleading
    "unasserted" for a ready-only method called from that window.
    """
    observed: dict[str, object] = {}

    class ReentrantTransport(FakeTransport):
        session: XTouchCompactSession

        def connect(self) -> object:
            observed["state"] = self.session.state
            with pytest.raises(LifecycleError, match="still connecting"):
                self.session.receive()
            with pytest.raises(LifecycleError, match="already connected"):
                self.session.connect()
            return super().connect()

    transport = ReentrantTransport()
    session = XTouchCompactSession(transport, global_midi_channel=2)
    transport.session = session

    session.connect()

    assert observed["state"] is SessionState.CONNECTING
    assert session.state is SessionState.STARTUP_LAYER_UNASSERTED


def test_close_is_idempotent_and_session_is_reusable(
    build_session: SessionFactory,
) -> None:
    device_session, _ = build_session()
    device_session.connect()
    device_session.initialize()
    device_session.close()
    device_session.close()
    assert device_session.state is SessionState.DISCONNECTED
    device_session.connect()
    device_session.initialize()
    assert device_session.state is SessionState.READY


def test_context_manager_closes_on_exception(build_session: SessionFactory) -> None:
    device_session, _ = build_session()
    with pytest.raises(ValueError, match="boom"), device_session:
        raise ValueError("boom")
    assert device_session.state is SessionState.DISCONNECTED


def test_context_manager_closes_when_initialization_fails(
    build_session: SessionFactory,
) -> None:
    class InitializationFailureTransport(FakeTransport):
        def send(self, message: object) -> None:
            raise ValueError("initialization failed")

    device_session, transport = build_session(InitializationFailureTransport())

    with pytest.raises(ValueError, match="initialization failed"), device_session:
        pass

    assert device_session.state is SessionState.DISCONNECTED
    assert transport.connected is False


def test_context_manager_connect_interrupt_leaves_disconnected(
    build_session: SessionFactory,
) -> None:
    class InterruptTransport(FakeTransport):
        def connect(self) -> object:
            raise KeyboardInterrupt

    device_session, transport = build_session(InterruptTransport())

    with pytest.raises(KeyboardInterrupt), device_session:
        pass

    assert device_session.state is SessionState.DISCONNECTED
    assert transport.connected is False
