"""Transport contracts shared by sessions and concrete MIDI backends."""

from __future__ import annotations

from typing import Protocol

from .errors import TransportConnectionError, TransportStateError
from .midi import RawMidiMessage

__all__ = ["MidiTransport", "TransportConnectionError", "TransportStateError"]


class MidiTransport(Protocol):
    """Minimal synchronous transport required by an X-TOUCH session."""

    def connect(self) -> object: ...

    def receive(self, timeout: float | None = None) -> RawMidiMessage | None: ...

    def send(self, message: RawMidiMessage) -> None: ...

    def close(self) -> None: ...
