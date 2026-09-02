"""Public exception hierarchy for the X-TOUCH COMPACT application interface.

Application code should catch these types rather than ALSA-specific or
built-in exceptions. Each subclass documents which broad category of failure
it represents; most public session methods raise only from this hierarchy.
"""

from __future__ import annotations


class XTouchCompactError(RuntimeError):
    """Base class for public lifecycle, device, and protocol failures."""


class LifecycleError(XTouchCompactError):
    """A session method was called from an unsupported lifecycle state.

    Raised by ``connect()``, ``initialize()``, and every method that
    requires ``SessionState.READY`` when the session is not in the required
    state.
    """


class SpecificationError(XTouchCompactError, ValueError):
    """The device description is malformed, contradictory, or cannot load."""


class DiscoveryError(XTouchCompactError):
    """ALSA discovery did not resolve to exactly one matching endpoint."""


class DeviceNotFoundError(DiscoveryError):
    """No ALSA Sequencer endpoint matched the requested device identity."""


class AmbiguousDeviceError(DiscoveryError):
    """More than one ALSA Sequencer endpoint matched the requested identity."""


class TransportError(XTouchCompactError):
    """Base class for transport-lifecycle and connection failures."""


class TransportStateError(TransportError):
    """A transport operation requires a different connection state."""


class TransportConnectionError(TransportError):
    """A connected transport can no longer exchange MIDI with its endpoint."""


class UnsupportedOperationError(XTouchCompactError, ValueError):
    """A requested semantic operation has no supported device mapping."""
