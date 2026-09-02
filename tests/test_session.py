from pathlib import Path

import pytest

from xtouch_compact import (
    ButtonPressed,
    ControlChange,
    Layer,
    NoteOn,
    ProgramChange,
    SessionState,
    XTouchCompactSession,
    load_device_specification,
)

SPEC_PATH = Path(__file__).parents[1] / "specs" / "xtouch-compact-midi.yaml"


class FakeTransport:
    def __init__(self, messages: list[object] | None = None) -> None:
        self.messages = list(messages or [])
        self.connected = False
        self.closed = False
        self.sent: list[object] = []

    def connect(self) -> object:
        self.connected = True
        return object()

    def receive(self, timeout: float | None = None) -> object | None:
        return self.messages.pop(0) if self.messages else None

    def send(self, message: object) -> None:
        self.sent.append(message)

    def close(self) -> None:
        self.closed = True
        self.connected = False


def session(transport: FakeTransport, layer: Layer = Layer.A) -> XTouchCompactSession:
    return XTouchCompactSession(
        transport,
        load_device_specification(SPEC_PATH),
        global_midi_channel=2,
        startup_layer=layer,
    )


def test_post_connect_layer_initialization_is_explicit_session_policy() -> None:
    transport = FakeTransport()
    device_session = session(transport, Layer.B)

    device_session.connect()
    assert device_session.state is SessionState.STARTUP_LAYER_UNASSERTED
    assert transport.sent == []

    device_session.initialize()
    assert device_session.state is SessionState.READY
    assert transport.sent == [ProgramChange(2, 1)]


def test_receive_pipeline_decodes_message_and_preserves_raw_input() -> None:
    transport = FakeTransport([NoteOn(1, 54, 127)])
    device_session = session(transport)
    device_session.connect()
    device_session.initialize()

    received = device_session.receive_input()

    assert received is not None
    assert received.message == NoteOn(1, 54, 127)
    assert isinstance(received.physical_event, ButtonPressed)


def test_decoder_none_does_not_fail_receive_pipeline() -> None:
    raw = ControlChange(2, 1, 64)
    transport = FakeTransport([raw])
    device_session = session(transport)
    device_session.connect()
    device_session.initialize()

    received = device_session.receive_input()

    assert received is not None
    assert received.message == raw
    assert received.physical_event is None


def test_inbound_program_change_is_preserved_as_unsupported_device_input() -> None:
    raw = ProgramChange(2, 0)
    transport = FakeTransport([raw])
    device_session = session(transport)
    device_session.connect()
    device_session.initialize()

    received = device_session.receive_input()

    assert received is not None
    assert received.message == raw
    assert received.physical_event is None


def test_session_blocks_input_until_layer_is_asserted_and_resets_on_close() -> None:
    transport = FakeTransport()
    device_session = session(transport)
    device_session.connect()

    with pytest.raises(RuntimeError, match="unasserted"):
        device_session.receive()

    device_session.close()
    assert device_session.state is SessionState.DISCONNECTED
    assert transport.closed


@pytest.mark.parametrize("channel", [0, 17])
def test_session_validates_global_midi_channel(channel: int) -> None:
    with pytest.raises(ValueError, match="midi_channel"):
        XTouchCompactSession(
            FakeTransport(),
            load_device_specification(SPEC_PATH),
            global_midi_channel=channel,
        )
