"""ALSA Sequencer discovery, MIDI conversion, and connection lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from errno import ENOENT
from typing import Any

from .errors import (
    AmbiguousDeviceError,
    DeviceNotFoundError,
    DiscoveryError,
    TransportConnectionError,
    TransportStateError,
)
from .midi import ControlChange, NoteOff, NoteOn, ProgramChange, RawMidiMessage

DEFAULT_DEVICE_NAME = "X-TOUCH COMPACT"

# alsa-midi's event_input uses ``if timeout:`` and treats 0 as wait-forever.
# A positive duration that expires immediately is a non-blocking poll.
_POLL_TIMEOUT_SECONDS = 1e-6


def _event_input_timeout(timeout: float | None) -> float | None:
    """Map this library's receive timeout onto alsa-midi's ``event_input``.

    Public contract: ``None`` blocks, ``0`` polls, a positive value waits
    that many seconds. Do not forward ``0`` to alsa-midi.
    """
    if timeout is None:
        return None
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise TypeError("timeout must be None or a number of seconds")
    if timeout < 0:
        raise ValueError("timeout must be None or a non-negative number of seconds")
    if timeout == 0:
        return _POLL_TIMEOUT_SECONDS
    return float(timeout)


def _connect_failure_message(error: BaseException) -> str:
    """Classify a client-creation failure into an actionable message.

    ``alsa-midi`` reports a missing ``/dev/snd/seq`` as an ``ALSAError``
    (or, for some backends, an ``OSError``) carrying an ``ENOENT`` errno.
    That specific case has one dominant real-world cause — a kernel built
    without ALSA Sequencer support, notably stock Jetson kernels — so it
    gets its own message instead of a generic wrapper.
    """
    if _is_enoent(error):
        return (
            "ALSA Sequencer device /dev/snd/seq is missing; the running "
            "kernel was likely built without ALSA Sequencer support "
            "(see docs/hardware.md#linux-and-alsa-sequencer)"
        )
    return (
        f"ALSA MIDI connect failed: {error}; see "
        "docs/hardware.md#linux-and-alsa-sequencer for prerequisites"
    )


def _is_enoent(error: BaseException) -> bool:
    """Return whether ``error`` reports ENOENT, ALSA- or OS-style, either sign."""
    errno_value = getattr(error, "errnum", None)
    if errno_value is None:
        errno_value = getattr(error, "errno", None)
    return errno_value is not None and abs(errno_value) == ENOENT


def _disconnect_if_endpoint_exists(
    operation: Callable[[tuple[int, int]], None], address: tuple[int, int]
) -> None:
    try:
        operation(address)
    except Exception as error:
        if not _is_enoent(error):
            raise


@dataclass(frozen=True, slots=True)
class SequencerEndpoint:
    """Stable metadata needed to connect to one ALSA Sequencer port."""

    client_id: int
    port_id: int
    client_name: str
    port_name: str
    capabilities: int

    @property
    def address(self) -> tuple[int, int]:
        return self.client_id, self.port_id


def discover_endpoint(
    ports: Iterable[Any],
    device_name: str = DEFAULT_DEVICE_NAME,
    port_name: str | None = None,
    required_capabilities: int | None = None,
) -> SequencerEndpoint:
    """Return the unique named, bidirectional ALSA endpoint."""
    if required_capabilities is None:
        from alsa_midi import RW_PORT

        required_capabilities = int(RW_PORT)
    normalized_device_name = device_name.casefold()
    normalized_port_name = port_name.casefold() if port_name else None
    matches: list[SequencerEndpoint] = []

    for port in ports:
        client_name = str(getattr(port, "client_name", "") or "")
        candidate_port_name = str(getattr(port, "name", "") or "")
        capabilities = int(getattr(port, "capability", 0))
        if client_name.casefold() != normalized_device_name:
            continue
        if capabilities & required_capabilities != required_capabilities:
            continue
        if (
            normalized_port_name is not None
            and normalized_port_name not in candidate_port_name.casefold()
        ):
            continue
        matches.append(
            SequencerEndpoint(
                client_id=int(port.client_id),
                port_id=int(port.port_id),
                client_name=client_name,
                port_name=candidate_port_name,
                capabilities=capabilities,
            )
        )

    qualifier = f" and port name containing {port_name!r}" if port_name else ""
    if not matches:
        raise DeviceNotFoundError(
            f"no bidirectional ALSA Sequencer port found for client "
            f"{device_name!r}{qualifier}; run `aconnect -l` to check the "
            "device is powered, in Standard MIDI mode, and enumerated "
            "(see docs/hardware.md#linux-and-alsa-sequencer)"
        )
    if len(matches) > 1:
        identities = ", ".join(
            f"{item.client_id}:{item.port_id} {item.port_name!r}" for item in matches
        )
        raise AmbiguousDeviceError(
            f"multiple bidirectional ports match {device_name!r}: {identities}; "
            "supply a port-name filter (see docs/hardware.md#linux-and-alsa-sequencer)"
        )
    return matches[0]


def midi_from_alsa_event(event: Any) -> RawMidiMessage | None:
    """Convert one supported ALSA event, returning ``None`` for other traffic."""
    event_type = getattr(getattr(event, "type", None), "name", "")
    midi_channel = getattr(event, "channel", -1) + 1
    try:
        if event_type == "CONTROLLER":
            return ControlChange(midi_channel, event.param, event.value)
        if event_type == "NOTEON":
            return NoteOn(midi_channel, event.note, event.velocity)
        if event_type == "NOTEOFF":
            return NoteOff(midi_channel, event.note, event.velocity)
        if event_type == "PGMCHANGE":
            return ProgramChange(midi_channel, event.value)
    except (AttributeError, TypeError, ValueError):
        return None
    return None


def alsa_event_from_midi(message: RawMidiMessage) -> Any:
    """Convert one validated MIDI message into an ``alsa-midi`` event."""
    from alsa_midi import (
        ControlChangeEvent,
        NoteOffEvent,
        NoteOnEvent,
        ProgramChangeEvent,
    )

    midi_channel = message.midi_channel - 1
    if isinstance(message, NoteOn):
        return NoteOnEvent(
            channel=midi_channel,
            note=message.note_number,
            velocity=message.velocity,
        )
    if isinstance(message, NoteOff):
        return NoteOffEvent(
            channel=midi_channel,
            note=message.note_number,
            velocity=message.velocity,
        )
    if isinstance(message, ControlChange):
        return ControlChangeEvent(
            channel=midi_channel,
            param=message.control_number,
            value=message.value,
        )
    if isinstance(message, ProgramChange):
        return ProgramChangeEvent(
            channel=midi_channel,
            value=message.program_number,
        )
    raise TypeError(f"unsupported MIDI message {type(message).__name__}")


class AlsaSequencerTransport:
    """Synchronous bidirectional transport for validated MIDI messages."""

    def __init__(
        self,
        *,
        client_name: str = "xtouch-compact",
        local_port_name: str = "X-TOUCH COMPACT transport",
        device_name: str = DEFAULT_DEVICE_NAME,
        port_name: str | None = None,
        client_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._client_name = client_name
        self._local_port_name = local_port_name
        self._device_name = device_name
        self._port_name = port_name
        self._client_factory = client_factory
        self._client: Any | None = None
        self._local_port: Any | None = None
        self._endpoint: SequencerEndpoint | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def endpoint(self) -> SequencerEndpoint | None:
        return self._endpoint

    def connect(self) -> SequencerEndpoint:
        """Open ALSA, discover the device, and subscribe in both directions."""
        if self.connected:
            raise TransportStateError("ALSA Sequencer transport is already connected")
        client_factory = self._client_factory
        try:
            if client_factory is None:
                from alsa_midi import SequencerClient

                client_factory = SequencerClient
            client = client_factory(self._client_name)
        except Exception as error:
            raise TransportConnectionError(_connect_failure_message(error)) from error
        local_port = None
        endpoint = None
        connected_from = False
        connected_to = False
        try:
            ports = client.list_ports(input=True, output=True)
            endpoint = discover_endpoint(
                ports,
                device_name=self._device_name,
                port_name=self._port_name,
            )
            local_port = client.create_port(self._local_port_name)
            local_port.connect_from(endpoint.address)
            connected_from = True
            local_port.connect_to(endpoint.address)
            connected_to = True
        except BaseException as error:
            if local_port is not None and endpoint is not None:
                if connected_to:
                    with suppress(Exception):
                        local_port.disconnect_to(endpoint.address)
                if connected_from:
                    with suppress(Exception):
                        local_port.disconnect_from(endpoint.address)
            with suppress(Exception):
                client.close()
            if isinstance(error, DiscoveryError):
                raise
            if isinstance(error, Exception):
                raise TransportConnectionError(
                    _connect_failure_message(error)
                ) from error
            raise
        self._client = client
        self._local_port = local_port
        self._endpoint = endpoint
        return endpoint

    def receive(self, timeout: float | None = None) -> RawMidiMessage | None:
        """Receive one event; timeouts and unsupported events return ``None``.

        ``timeout`` is seconds to wait. ``None`` blocks indefinitely. ``0``
        polls and returns immediately. A positive value waits up to that
        many seconds.
        """
        client, _ = self._connected_resources()
        event_timeout = _event_input_timeout(timeout)
        try:
            event = client.event_input(timeout=event_timeout)
        except Exception as error:
            raise TransportConnectionError("ALSA MIDI receive failed") from error
        return None if event is None else midi_from_alsa_event(event)

    def send(self, message: RawMidiMessage) -> None:
        """Queue and drain one validated MIDI message."""
        client, local_port = self._connected_resources()
        event = alsa_event_from_midi(message)
        try:
            client.event_output(event, port=local_port)
            client.drain_output()
        except Exception as error:
            raise TransportConnectionError("ALSA MIDI send failed") from error

    def close(self) -> None:
        """Disconnect subscriptions and release the ALSA client."""
        client = self._client
        local_port = self._local_port
        endpoint = self._endpoint
        self._client = None
        self._local_port = None
        self._endpoint = None
        if client is None:
            return
        try:
            try:
                if local_port is not None and endpoint is not None:
                    # The remote ALSA endpoint may already be gone after a USB
                    # disconnect. Local client closure still releases resources.
                    try:
                        _disconnect_if_endpoint_exists(
                            local_port.disconnect_to, endpoint.address
                        )
                    finally:
                        _disconnect_if_endpoint_exists(
                            local_port.disconnect_from, endpoint.address
                        )
            finally:
                client.close()
        except Exception as error:
            raise TransportConnectionError("ALSA MIDI close failed") from error

    def _connected_resources(self) -> tuple[Any, Any]:
        if self._client is None or self._local_port is None:
            raise TransportStateError("ALSA Sequencer transport is disconnected")
        return self._client, self._local_port

    def __enter__(self) -> AlsaSequencerTransport:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
