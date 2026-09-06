"""Tests for the stable application interface.

Library imports in this file come from the package root. Test doubles come
from ``tests.helpers``. This file exists to guard the supported downstream
contract: package exports, lifecycle, semantic outputs, event consumption,
fader/surface state inspection, exceptions, and reconnect, all reached
without importing implementation modules directly.
"""

import pytest

import xtouch_compact
from tests.helpers import FakeTransport, SessionFactory
from xtouch_compact import (
    AmbiguousDeviceError,
    Button,
    ButtonLedState,
    ButtonPressed,
    DeviceNotFoundError,
    DiscoveryError,
    Encoder,
    EncoderRingDisplay,
    EncoderRingMode,
    Fader,
    FaderOwner,
    Layer,
    LifecycleError,
    NoteOn,
    ProgramChange,
    SessionConfigurationError,
    SessionState,
    StatusLedState,
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


class TestPackageExports:
    def test_expected_public_names_are_importable(self) -> None:
        for name in EXPECTED_PUBLIC_EXPORTS:
            assert hasattr(xtouch_compact, name), f"missing public export {name}"

    def test_all_matches_module_attributes(self) -> None:
        assert set(xtouch_compact.__all__) == EXPECTED_PUBLIC_EXPORTS
        for name in xtouch_compact.__all__:
            assert hasattr(xtouch_compact, name)


class TestLifecycle:
    def test_methods_before_connect_require_connection_or_ready(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        assert device_session.state is SessionState.DISCONNECTED
        with pytest.raises(LifecycleError, match="disconnected"):
            device_session.initialize()
        with pytest.raises(LifecycleError, match="disconnected"):
            device_session.receive()

    def test_connect_then_initialize_reaches_ready(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        device_session.connect()
        assert device_session.state is SessionState.STARTUP_LAYER_UNASSERTED
        device_session.initialize()
        assert device_session.state is SessionState.READY

    def test_double_connect_is_a_lifecycle_error(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        device_session.connect()
        with pytest.raises(LifecycleError):
            device_session.connect()

    def test_close_is_idempotent_and_session_is_reusable(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        device_session.connect()
        device_session.initialize()
        device_session.close()
        device_session.close()
        assert device_session.state is SessionState.DISCONNECTED
        device_session.connect()
        device_session.initialize()
        assert device_session.state is SessionState.READY

    def test_context_manager_connects_initializes_and_closes(
        self, build_session: SessionFactory
    ) -> None:
        transport = FakeTransport()
        device_session, _ = build_session(transport)
        with device_session as entered:
            assert entered is device_session
            assert entered.state is SessionState.READY
        assert device_session.state is SessionState.DISCONNECTED

    def test_open_is_the_application_constructor(self) -> None:
        transport = FakeTransport()
        session = xtouch_compact.XTouchCompactSession.open(
            global_midi_channel=2,
            transport=transport,
        )
        assert session.state is SessionState.DISCONNECTED
        with session:
            assert session.state is SessionState.READY
        assert session.state is SessionState.DISCONNECTED

    def test_context_manager_closes_on_exception(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        with pytest.raises(ValueError, match="boom"), device_session:
            raise ValueError("boom")
        assert device_session.state is SessionState.DISCONNECTED

    def test_context_manager_closes_when_initialization_fails(
        self, build_session: SessionFactory
    ) -> None:
        class InitializationFailureTransport(FakeTransport):
            def send(self, message: object) -> None:
                raise ValueError("initialization failed")

        device_session, transport = build_session(InitializationFailureTransport())

        with pytest.raises(ValueError, match="initialization failed"), device_session:
            pass

        assert device_session.state is SessionState.DISCONNECTED
        assert transport.connected is False

    def test_context_manager_connect_interrupt_leaves_disconnected(
        self, build_session: SessionFactory
    ) -> None:
        class InterruptTransport(FakeTransport):
            def connect(self) -> object:
                raise KeyboardInterrupt

        device_session, transport = build_session(InterruptTransport())

        with pytest.raises(KeyboardInterrupt), device_session:
            pass

        assert device_session.state is SessionState.DISCONNECTED
        assert transport.connected is False


class TestSemanticOutputs:
    def test_set_button_led_sends_and_deduplicates(
        self, build_session: SessionFactory
    ) -> None:
        device_session, transport = build_session()
        device_session.connect()
        device_session.initialize()
        transport.sent.clear()

        device_session.set_button_led(Button.PLAY, ButtonLedState.ON)
        assert len(transport.sent) == 1
        device_session.set_button_led(Button.PLAY, ButtonLedState.ON)
        assert len(transport.sent) == 1

    def test_select_layer_always_transmits(self, build_session: SessionFactory) -> None:
        device_session, transport = build_session()
        device_session.connect()
        device_session.initialize()
        transport.sent.clear()

        device_session.select_layer(Layer.A)
        device_session.select_layer(Layer.A)
        assert sum(isinstance(m, ProgramChange) for m in transport.sent) == 2

    def test_encoder_ring_mode_restores_desired_display(
        self, build_session: SessionFactory
    ) -> None:
        device_session, transport = build_session()
        device_session.connect()
        device_session.initialize()
        device_session.set_encoder_ring_value(
            Encoder.CHANNEL_1, EncoderRingDisplay.at(5)
        )
        transport.sent.clear()

        device_session.set_encoder_ring_mode(Encoder.CHANNEL_1, EncoderRingMode.PAN)

        assert len(transport.sent) == 2
        state = device_session.encoder_feedback_state(Encoder.CHANNEL_1)
        assert state.last_sent_mode is EncoderRingMode.PAN
        assert state.last_sent_display == EncoderRingDisplay.at(5)

    def test_unsupported_semantic_value_raises_unsupported_operation(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        device_session.connect()
        device_session.initialize()
        with pytest.raises(UnsupportedOperationError):
            device_session.set_encoder_ring_value(
                Encoder.CHANNEL_1, EncoderRingDisplay.at(999)
            )


class TestEventConsumption:
    def test_receive_returns_typed_physical_event(
        self, build_session: SessionFactory
    ) -> None:
        transport = FakeTransport([NoteOn(1, 54, 127)])
        device_session, _ = build_session(transport)
        device_session.connect()
        device_session.initialize()

        event = device_session.receive()

        assert isinstance(event, ButtonPressed)
        assert event.button is Button.PLAY


class TestFaderState:
    def test_fader_state_is_read_only_snapshot(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        device_session.connect()
        device_session.initialize()

        device_session.set_fader(Fader.CHANNEL_1, 64)
        state = device_session.fader_state(Fader.CHANNEL_1)

        assert state.desired_value == 64
        assert state.owner is FaderOwner.APPLICATION


class TestSurfaceState:
    def test_surface_state_snapshot_is_immutable(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()
        device_session.connect()
        device_session.initialize()

        device_session.set_foot_switch_led(StatusLedState.ON)
        snapshot = device_session.surface_state()

        assert snapshot.status_leds[0].desired is StatusLedState.ON
        with pytest.raises(AttributeError):
            snapshot.status_leds[0].desired = StatusLedState.OFF  # type: ignore[misc]

    def test_unsupported_state_inspection_uses_public_error(
        self, build_session: SessionFactory
    ) -> None:
        device_session, _ = build_session()

        with pytest.raises(UnsupportedOperationError):
            device_session.button_feedback_state(Button.LAYER_A)


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


class TestReconnect:
    def test_reconnect_restores_desired_feedback_without_alsa_internals(
        self, build_session: SessionFactory
    ) -> None:
        device_session, transport = build_session()
        device_session.connect()
        device_session.initialize()
        device_session.set_button_led(Button.PLAY, ButtonLedState.ON)

        device_session.reconnect()

        assert device_session.state is SessionState.READY
        assert (
            device_session.button_feedback_state(Button.PLAY).last_sent
            is ButtonLedState.ON
        )

    def test_connection_loss_surfaces_transport_connection_error(
        self, build_session: SessionFactory
    ) -> None:
        class FailingTransport(FakeTransport):
            def receive(self, timeout: float | None = None) -> object | None:
                raise TransportConnectionError("lost")

        device_session, _ = build_session(FailingTransport())
        device_session.connect()
        device_session.initialize()

        with pytest.raises(TransportConnectionError):
            device_session.receive()
        assert device_session.state is SessionState.DISCONNECTED
