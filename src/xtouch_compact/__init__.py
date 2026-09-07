"""Python support for the Behringer X-TOUCH COMPACT in Standard MIDI mode.

Import the session, controls, events, feedback types, and errors from this
package. Only the fixed factory MIDI profile is supported.
See docs/api.md for the API and advanced transport exports, and
docs/usage.md for examples.
"""

from .alsa_transport import (
    AlsaSequencerTransport,
    SequencerEndpoint,
    alsa_event_from_midi,
    discover_endpoint,
    midi_from_alsa_event,
)
from .controls import Button, Encoder, Fader, FootControl, Layer
from .decoder import InboundDecoder
from .errors import (
    AmbiguousDeviceError,
    DeviceNotFoundError,
    DiscoveryError,
    LifecycleError,
    SessionConfigurationError,
    TransportConnectionError,
    TransportError,
    TransportStateError,
    UnsupportedOperationError,
    XTouchCompactError,
)
from .events import (
    ButtonPressed,
    ButtonReleased,
    EncoderPositionReported,
    EncoderPressed,
    EncoderReleased,
    FaderPositionReported,
    FaderReleased,
    FaderTouched,
    PhysicalControlEvent,
)
from .fader_state import FaderOwner, FaderState
from .feedback import (
    ButtonLedState,
    EncoderRingDisplay,
    EncoderRingDisplayKind,
    EncoderRingMode,
    StatusLedState,
)
from .midi import ControlChange, NoteOff, NoteOn, ProgramChange, RawMidiMessage
from .session import ReceivedInput, SessionState, XTouchCompactSession
from .surface_state import (
    ButtonFeedbackState,
    EncoderFeedbackState,
    LayerFeedbackState,
    StatusFeedbackState,
    SurfaceStateSnapshot,
)
from .transport import MidiTransport

__version__ = "0.1.0"

__all__ = [
    # Session / lifecycle
    "ReceivedInput",
    "SessionState",
    "XTouchCompactSession",
    # Physical control identities
    "Button",
    "Encoder",
    "Fader",
    "FootControl",
    "Layer",
    # Physical events
    "ButtonPressed",
    "ButtonReleased",
    "EncoderPositionReported",
    "EncoderPressed",
    "EncoderReleased",
    "FaderPositionReported",
    "FaderReleased",
    "FaderTouched",
    "PhysicalControlEvent",
    # Semantic feedback types
    "ButtonLedState",
    "EncoderRingDisplay",
    "EncoderRingDisplayKind",
    "EncoderRingMode",
    "StatusLedState",
    # State inspection
    "ButtonFeedbackState",
    "EncoderFeedbackState",
    "FaderOwner",
    "FaderState",
    "LayerFeedbackState",
    "StatusFeedbackState",
    "SurfaceStateSnapshot",
    # Errors
    "AmbiguousDeviceError",
    "DeviceNotFoundError",
    "DiscoveryError",
    "LifecycleError",
    "SessionConfigurationError",
    "TransportConnectionError",
    "TransportError",
    "TransportStateError",
    "UnsupportedOperationError",
    "XTouchCompactError",
    # Advanced/diagnostic transport and codec types
    "AlsaSequencerTransport",
    "ControlChange",
    "InboundDecoder",
    "MidiTransport",
    "NoteOff",
    "NoteOn",
    "ProgramChange",
    "RawMidiMessage",
    "SequencerEndpoint",
    "alsa_event_from_midi",
    "discover_endpoint",
    "midi_from_alsa_event",
]
