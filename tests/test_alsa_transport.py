import time
from types import SimpleNamespace

import pytest
from alsa_midi import (
    ControlChangeEvent,
    NoteOffEvent,
    NoteOnEvent,
    ProgramChangeEvent,
)
from alsa_midi.exceptions import ALSAError

from xtouch_compact import (
    AlsaSequencerTransport,
    ControlChange,
    DiscoveryError,
    NoteOff,
    NoteOn,
    ProgramChange,
    TransportConnectionError,
    TransportStateError,
    alsa_event_from_midi,
    discover_endpoint,
    midi_from_alsa_event,
)
from xtouch_compact.alsa_transport import (
    _POLL_TIMEOUT_SECONDS,
    _event_input_timeout,
)

READ_WRITE_SUBSCRIPTIONS = 1 | 2 | 32 | 64


def alsa_event(event_type: str, **fields: int) -> SimpleNamespace:
    return SimpleNamespace(type=SimpleNamespace(name=event_type), **fields)


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (alsa_event("NOTEON", channel=0, note=0, velocity=127), NoteOn(1, 0, 127)),
        (
            alsa_event("NOTEOFF", channel=15, note=127, velocity=0),
            NoteOff(16, 127, 0),
        ),
        (
            alsa_event("CONTROLLER", channel=1, param=0, value=127),
            ControlChange(2, 0, 127),
        ),
        (
            alsa_event("PGMCHANGE", channel=1, value=0),
            ProgramChange(2, 0),
        ),
    ],
)
def test_midi_from_alsa_event_preserves_values_and_channel(
    event: object, expected: object
) -> None:
    assert midi_from_alsa_event(event) == expected


@pytest.mark.parametrize(
    "event",
    [
        alsa_event("CLOCK"),
        alsa_event("CONTROLLER", channel=0, param=128, value=0),
        SimpleNamespace(),
    ],
)
def test_midi_from_alsa_event_ignores_unsupported_or_invalid_event(
    event: object,
) -> None:
    assert midi_from_alsa_event(event) is None


@pytest.mark.parametrize(
    ("message", "event_type", "fields"),
    [
        (NoteOn(2, 0, 127), NoteOnEvent, {"channel": 1, "note": 0, "velocity": 127}),
        (
            NoteOff(2, 127, 0),
            NoteOffEvent,
            {"channel": 1, "note": 127, "velocity": 0},
        ),
        (
            ControlChange(2, 0, 127),
            ControlChangeEvent,
            {"channel": 1, "param": 0, "value": 127},
        ),
        (
            ProgramChange(2, 127),
            ProgramChangeEvent,
            {"channel": 1, "value": 127},
        ),
    ],
)
def test_alsa_event_from_midi_preserves_values_and_converts_channel(
    message: object, event_type: type, fields: dict[str, int]
) -> None:
    event = alsa_event_from_midi(message)

    assert isinstance(event, event_type)
    for name, value in fields.items():
        assert getattr(event, name) == value


def port(
    client_name: str = "X-TOUCH COMPACT",
    port_name: str = "X-TOUCH COMPACT MIDI 1",
    capabilities: int = READ_WRITE_SUBSCRIPTIONS,
    *,
    client_id: int = 24,
    port_id: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        client_id=client_id,
        port_id=port_id,
        client_name=client_name,
        name=port_name,
        capability=capabilities,
    )


def test_discovery_reports_no_matching_device() -> None:
    with pytest.raises(DiscoveryError, match="no bidirectional"):
        discover_endpoint([port(client_name="Other")])


def test_discovery_returns_one_bidirectional_matching_device() -> None:
    endpoint = discover_endpoint(
        [port(capabilities=1 | 32), port(client_id=25, port_id=1)]
    )

    assert endpoint.address == (25, 1)
    assert endpoint.client_name == "X-TOUCH COMPACT"


def test_discovery_reports_ambiguity_and_accepts_port_filter() -> None:
    ports = [
        port(port_name="X-TOUCH COMPACT MIDI 1"),
        port(port_name="X-TOUCH COMPACT MIDI 2", port_id=1),
    ]

    with pytest.raises(DiscoveryError, match="multiple bidirectional"):
        discover_endpoint(ports)

    assert discover_endpoint(ports, port_name="MIDI 2").port_id == 1


class FakePort:
    def __init__(self) -> None:
        self.actions: list[tuple[str, tuple[int, int]]] = []
        self.fail_disconnect = False

    def connect_from(self, address: tuple[int, int]) -> None:
        self.actions.append(("connect_from", address))

    def connect_to(self, address: tuple[int, int]) -> None:
        self.actions.append(("connect_to", address))

    def disconnect_from(self, address: tuple[int, int]) -> None:
        self.actions.append(("disconnect_from", address))
        if self.fail_disconnect:
            raise ALSAError("remote endpoint gone", -2)

    def disconnect_to(self, address: tuple[int, int]) -> None:
        self.actions.append(("disconnect_to", address))
        if self.fail_disconnect:
            raise ALSAError("remote endpoint gone", -2)


class FakeClient:
    def __init__(self, name: str, *, endpoint_client_id: int = 24) -> None:
        self.name = name
        self.endpoint_client_id = endpoint_client_id
        self.port = FakePort()
        self.events: list[tuple[object, object]] = []
        self.incoming: object | None = None
        self.drained = 0
        self.closed = False
        self.fail_input = False
        self.fail_output = False
        self.fail_close = False
        self.last_timeout: float | None = None

    def list_ports(self, **options: bool) -> list[SimpleNamespace]:
        assert options == {"input": True, "output": True}
        return [port(client_id=self.endpoint_client_id)]

    def create_port(self, name: str) -> FakePort:
        assert name == "local"
        return self.port

    def event_input(self, timeout: float | None = None) -> object | None:
        if timeout == 0:
            raise AssertionError("timeout=0 would wait forever in alsa-midi")
        self.last_timeout = timeout
        if self.fail_input:
            raise OSError("gone")
        return self.incoming

    def event_output(self, event: object, *, port: object) -> None:
        if self.fail_output:
            raise OSError("gone")
        self.events.append((event, port))

    def drain_output(self) -> None:
        self.drained += 1

    def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise OSError("close failed")


def test_transport_connect_send_receive_and_idempotent_close() -> None:
    client = FakeClient("production-test")
    client.incoming = alsa_event("CONTROLLER", channel=1, param=7, value=0)
    transport = AlsaSequencerTransport(
        client_name="production-test",
        local_port_name="local",
        client_factory=lambda name: client,
    )

    endpoint = transport.connect()
    assert endpoint.address == (24, 0)
    assert client.port.actions == [
        ("connect_from", (24, 0)),
        ("connect_to", (24, 0)),
    ]

    transport.send(NoteOn(2, 127, 0))
    assert isinstance(client.events[0][0], NoteOnEvent)
    assert client.events[0][1] is client.port
    assert client.drained == 1
    assert transport.receive(timeout=0.25) == ControlChange(2, 7, 0)
    assert client.last_timeout == 0.25

    transport.close()
    transport.close()
    assert client.port.actions[-2:] == [
        ("disconnect_to", (24, 0)),
        ("disconnect_from", (24, 0)),
    ]
    assert client.closed
    assert not transport.connected


def test_transport_classifies_client_creation_failure() -> None:
    def fail_client_creation(name: str) -> object:
        raise OSError("ALSA unavailable")

    transport = AlsaSequencerTransport(client_factory=fail_client_creation)

    with pytest.raises(TransportConnectionError, match="connect failed"):
        transport.connect()


def test_transport_names_missing_sequencer_device() -> None:
    def fail_client_creation(name: str) -> object:
        raise ALSAError("No such file or directory", -2)

    transport = AlsaSequencerTransport(client_factory=fail_client_creation)

    with pytest.raises(TransportConnectionError, match="/dev/snd/seq"):
        transport.connect()


def test_transport_preserves_device_discovery_failure() -> None:
    client = FakeClient("production-test")
    client.list_ports = lambda **options: []  # type: ignore[method-assign]
    transport = AlsaSequencerTransport(client_factory=lambda name: client)

    with pytest.raises(DiscoveryError, match="no bidirectional"):
        transport.connect()

    assert client.closed


def test_transport_close_tolerates_vanished_remote_endpoint() -> None:
    client = FakeClient("production-test")
    transport = AlsaSequencerTransport(
        local_port_name="local",
        client_factory=lambda name: client,
    )
    transport.connect()
    client.port.fail_disconnect = True

    transport.close()

    assert client.port.actions[-2:] == [
        ("disconnect_to", (24, 0)),
        ("disconnect_from", (24, 0)),
    ]
    assert client.closed
    assert not transport.connected


def test_transport_classifies_close_failure() -> None:
    client = FakeClient("production-test")
    transport = AlsaSequencerTransport(
        local_port_name="local",
        client_factory=lambda name: client,
    )
    transport.connect()
    client.fail_close = True

    with pytest.raises(TransportConnectionError, match="close failed"):
        transport.close()

    assert not transport.connected


def test_transport_rejects_io_while_disconnected() -> None:
    transport = AlsaSequencerTransport(client_factory=FakeClient)

    with pytest.raises(TransportStateError, match="disconnected"):
        transport.send(NoteOn(1, 0, 0))


def test_transport_classifies_live_send_and_receive_failures() -> None:
    client = FakeClient("production-test")
    transport = AlsaSequencerTransport(
        local_port_name="local",
        client_factory=lambda name: client,
    )
    transport.connect()
    client.fail_output = True

    with pytest.raises(TransportConnectionError, match="send failed"):
        transport.send(NoteOn(2, 0, 0))

    client.fail_input = True
    with pytest.raises(TransportConnectionError, match="receive failed"):
        transport.receive(timeout=0.25)


def test_reconnect_rediscovers_changed_endpoint_identity() -> None:
    clients = iter(
        [
            FakeClient("production-test", endpoint_client_id=24),
            FakeClient("production-test", endpoint_client_id=31),
        ]
    )
    transport = AlsaSequencerTransport(
        local_port_name="local",
        client_factory=lambda name: next(clients),
    )

    assert transport.connect().address == (24, 0)
    transport.close()
    assert transport.connect().address == (31, 0)


def test_event_input_timeout_none_blocks() -> None:
    assert _event_input_timeout(None) is None


@pytest.mark.parametrize("timeout", [0, 0.0])
def test_event_input_timeout_zero_is_a_positive_poll(timeout: float) -> None:
    mapped = _event_input_timeout(timeout)
    assert mapped == _POLL_TIMEOUT_SECONDS
    assert mapped > 0


def test_event_input_timeout_positive_is_preserved() -> None:
    assert _event_input_timeout(0.25) == 0.25


@pytest.mark.parametrize("timeout", [-1, True, "1"])
def test_event_input_timeout_rejects_invalid_values(timeout: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _event_input_timeout(timeout)  # type: ignore[arg-type]


def test_receive_timeout_zero_polls_without_blocking() -> None:
    client = FakeClient("production-test")
    transport = AlsaSequencerTransport(
        local_port_name="local",
        client_factory=lambda name: client,
    )
    transport.connect()

    started = time.monotonic()
    assert transport.receive(timeout=0) is None
    elapsed = time.monotonic() - started

    assert elapsed < 0.25
    assert client.last_timeout == _POLL_TIMEOUT_SECONDS
    assert client.last_timeout != 0


def test_receive_timeout_zero_returns_a_queued_message() -> None:
    client = FakeClient("production-test")
    client.incoming = alsa_event("CONTROLLER", channel=1, param=7, value=0)
    transport = AlsaSequencerTransport(
        local_port_name="local",
        client_factory=lambda name: client,
    )
    transport.connect()

    assert transport.receive(timeout=0) == ControlChange(2, 7, 0)
    assert client.last_timeout == _POLL_TIMEOUT_SECONDS
