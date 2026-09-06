"""Supported exports and exception compatibility; behavior lives with its owner."""

import pytest

import xtouch_compact
from tests.helpers import SessionFactory
from xtouch_compact import (
    AmbiguousDeviceError,
    DeviceNotFoundError,
    DiscoveryError,
    LifecycleError,
    SessionConfigurationError,
    TransportConnectionError,
    TransportError,
    UnsupportedOperationError,
    XTouchCompactError,
)

EXPECTED_PUBLIC_EXPORTS = {
    "XTouchCompactSession",
    "SessionState",
    "ReceivedInput",
    "Fader",
    "Encoder",
    "Button",
    "Layer",
    "FootControl",
    "ButtonLedState",
    "EncoderRingMode",
    "EncoderRingDisplay",
    "EncoderRingDisplayKind",
    "StatusLedState",
    "ButtonFeedbackState",
    "EncoderFeedbackState",
    "FaderState",
    "FaderOwner",
    "LayerFeedbackState",
    "StatusFeedbackState",
    "SurfaceStateSnapshot",
    "ButtonPressed",
    "ButtonReleased",
    "EncoderPositionReported",
    "EncoderPressed",
    "EncoderReleased",
    "FaderPositionReported",
    "FaderReleased",
    "FaderTouched",
    "PhysicalControlEvent",
    "XTouchCompactError",
    "LifecycleError",
    "SessionConfigurationError",
    "DiscoveryError",
    "DeviceNotFoundError",
    "AmbiguousDeviceError",
    "TransportError",
    "TransportConnectionError",
    "TransportStateError",
    "UnsupportedOperationError",
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
}


def test_public_exports_match_the_supported_contract() -> None:
    assert set(xtouch_compact.__all__) == EXPECTED_PUBLIC_EXPORTS
    for name in EXPECTED_PUBLIC_EXPORTS:
        assert hasattr(xtouch_compact, name), f"missing public export {name}"


class TestExceptions:
    def test_lifecycle_and_unsupported_operation_are_xtouch_compact_errors(
        self,
    ) -> None:
        assert issubclass(LifecycleError, XTouchCompactError)
        assert issubclass(SessionConfigurationError, XTouchCompactError)
        assert issubclass(SessionConfigurationError, ValueError)
        assert issubclass(UnsupportedOperationError, XTouchCompactError)
        assert issubclass(DeviceNotFoundError, DiscoveryError)
        assert issubclass(AmbiguousDeviceError, DiscoveryError)
        assert issubclass(DiscoveryError, XTouchCompactError)
        assert issubclass(TransportConnectionError, TransportError)
        assert issubclass(TransportError, XTouchCompactError)

    def test_application_code_can_catch_broad_base_exception(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        with pytest.raises(XTouchCompactError):
            device_session.initialize()
