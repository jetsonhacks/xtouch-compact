"""Shared test doubles and session construction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from xtouch_compact import DeviceSpecification, Layer, XTouchCompactSession

SPEC_PATH = Path(__file__).resolve().parents[1] / "specs" / "xtouch-compact-midi.yaml"


class SendFailure(RuntimeError):
    """Raised by :class:`FakeTransport` when a test asks the next send to fail."""


class FakeTransport:
    """In-memory transport for session tests that do not exercise ALSA."""

    def __init__(self, messages: list[object] | None = None) -> None:
        self.messages = list(messages or [])
        self.sent: list[object] = []
        self.connected = False
        self.closed = False
        self.fail_next_send = False

    def connect(self) -> object:
        self.connected = True
        return object()

    def receive(self, timeout: float | None = None) -> object | None:
        return self.messages.pop(0) if self.messages else None

    def send(self, message: object) -> None:
        if self.fail_next_send:
            self.fail_next_send = False
            raise SendFailure("transport send failed")
        self.sent.append(message)

    def close(self) -> None:
        self.closed = True
        self.connected = False


def make_session(
    specification: DeviceSpecification,
    transport: object,
    *,
    global_midi_channel: int = 2,
    startup_layer: Layer = Layer.A,
) -> XTouchCompactSession:
    """Construct a session around an already-created test transport."""
    return XTouchCompactSession(
        transport,
        specification,
        global_midi_channel=global_midi_channel,
        startup_layer=startup_layer,
    )


def make_fake_session(
    specification: DeviceSpecification,
    transport: FakeTransport | None = None,
    *,
    ready: bool = False,
    global_midi_channel: int = 2,
    startup_layer: Layer = Layer.A,
) -> tuple[XTouchCompactSession, FakeTransport]:
    """Return a session and its fake transport, optionally already ``READY``."""
    if transport is None:
        transport = FakeTransport()
    session = make_session(
        specification,
        transport,
        global_midi_channel=global_midi_channel,
        startup_layer=startup_layer,
    )
    if ready:
        session.connect()
        session.initialize()
        transport.sent.clear()
    return session, transport


class SessionBuilder(Protocol):
    """Pytest fixture type for :func:`make_fake_session` bound to one specification."""

    def __call__(
        self,
        transport: FakeTransport | None = None,
        *,
        ready: bool = False,
        global_midi_channel: int = 2,
        startup_layer: Layer = Layer.A,
    ) -> tuple[XTouchCompactSession, FakeTransport]: ...


def bind_session_builder(
    specification: DeviceSpecification,
) -> Callable[..., tuple[XTouchCompactSession, FakeTransport]]:
    def build_session(
        transport: FakeTransport | None = None,
        *,
        ready: bool = False,
        global_midi_channel: int = 2,
        startup_layer: Layer = Layer.A,
    ) -> tuple[XTouchCompactSession, FakeTransport]:
        return make_fake_session(
            specification,
            transport,
            ready=ready,
            global_midi_channel=global_midi_channel,
            startup_layer=startup_layer,
        )

    return build_session
