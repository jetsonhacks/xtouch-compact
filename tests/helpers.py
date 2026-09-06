"""Shared test doubles and session construction."""

from __future__ import annotations

from collections.abc import Callable

from xtouch_compact import Layer, XTouchCompactSession


class SendFailure(RuntimeError):
    """Generic send rejection used to test commit-after-send ordering.

    This intentionally does not model device loss. Production connection-loss
    recovery is exercised with TransportConnectionError in test_runtime.py.
    """


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


def make_fake_session(
    transport: FakeTransport | None = None,
    *,
    ready: bool = False,
    global_midi_channel: int = 2,
    startup_layer: Layer = Layer.A,
) -> tuple[XTouchCompactSession, FakeTransport]:
    """Return a session and its fake transport, optionally already ``READY``."""
    if transport is None:
        transport = FakeTransport()
    session = XTouchCompactSession(
        transport,
        global_midi_channel=global_midi_channel,
        startup_layer=startup_layer,
    )
    if ready:
        session.connect()
        session.initialize()
        transport.sent.clear()
    return session, transport


SessionFactory = Callable[..., tuple[XTouchCompactSession, FakeTransport]]
"""Type of the ``build_session`` fixture: see :func:`make_fake_session`."""
