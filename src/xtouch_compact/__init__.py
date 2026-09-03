"""Python support for the Behringer X-TOUCH COMPACT.

This package exposes a stable application interface for treating the
X-TOUCH COMPACT as a semantic bidirectional physical control surface.
Application code should import from this package root; it should not need
to import implementation modules (``_specification_common``,
``_specification_rx``, ``_specification_tx``, ``feedback_encoder``,
``fader_state``, ``surface_state``) directly for normal use.

The exports fall into five categories:

- session/lifecycle: :class:`XTouchCompactSession`, :class:`SessionState`,
  :class:`ReceivedInput`;
- physical control identities: :class:`Fader`, :class:`Encoder`,
  :class:`Button`, :class:`Layer`, :class:`FootControl`;
- physical events: the ``*Pressed``/``*Released``/``*Reported``/``*Touched``
  dataclasses and :data:`PhysicalControlEvent`;
- semantic feedback and state types: :class:`ButtonLedState`,
  :class:`EncoderRingMode`, :class:`EncoderRingDisplay`,
  :class:`StatusLedState`, :class:`FaderState`, :class:`FaderOwner`, and the
  surface-feedback snapshot types;
- errors: the :class:`XTouchCompactError` hierarchy in ``errors``.

A small set of advanced/diagnostic transport types
(:class:`AlsaSequencerTransport`, :class:`SequencerEndpoint`,
:class:`InboundDecoder`, the raw MIDI message types, and the ALSA
conversion helpers) remain exported for diagnostics, opt-in hardware tools,
and tests. Normal application code built only on the session API does not
need them. :class:`MidiTransport` is in this same advanced tier: it is the
structural protocol ``XTouchCompactSession``'s ``transport`` argument must
satisfy (``connect``/``receive``/``send``/``close``), needed only by code
that supplies a non-ALSA transport in place of
:class:`AlsaSequencerTransport`.
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
    SpecificationError,
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
from .specification import (
    DEFAULT_SPEC_PATH,
    DeviceSpecification,
    load_device_specification,
)
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
    "DEFAULT_SPEC_PATH",
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
    "SpecificationError",
    "TransportConnectionError",
    "TransportError",
    "TransportStateError",
    "UnsupportedOperationError",
    "XTouchCompactError",
    # Configuration / specification
    "DeviceSpecification",
    "load_device_specification",
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
