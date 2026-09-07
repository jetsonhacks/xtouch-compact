"""Session lifecycle, physical input, and synchronized surface feedback."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from enum import Enum

from .controls import Button, Encoder, Fader, FootControl, Layer
from .decoder import InboundDecoder
from .device_map import (
    ASSIGNABLE_BUTTONS,
    classify_rx_message,
    matches_layer_program_change,
)
from .errors import LifecycleError, SessionConfigurationError, TransportConnectionError
from .events import (
    FaderPositionReported,
    FaderReleased,
    FaderTouched,
    PhysicalControlEvent,
)
from .fader_state import FaderState, FaderStateController
from .feedback import (
    ButtonLedState,
    EncoderRingDisplay,
    EncoderRingMode,
    StatusLedState,
)
from .feedback_encoder import SemanticFeedbackEncoder
from .midi import ControlChange, ProgramChange, RawMidiMessage
from .surface_state import (
    ButtonFeedbackState,
    EncoderFeedbackState,
    LayerFeedbackState,
    StatusFeedbackState,
    SurfaceStateController,
    SurfaceStateSnapshot,
)
from .transport import MidiTransport


def _validate_session_construction(
    global_midi_channel: int, startup_layer: Layer
) -> None:
    if isinstance(global_midi_channel, bool) or not isinstance(
        global_midi_channel, int
    ):
        raise SessionConfigurationError("global_midi_channel must be an integer")
    if not 1 <= global_midi_channel <= 16:
        raise SessionConfigurationError("global_midi_channel must be from 1 through 16")
    if not isinstance(startup_layer, Layer):
        raise SessionConfigurationError("startup_layer must be a Layer")


class SessionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    STARTUP_LAYER_UNASSERTED = "startup_layer_unasserted"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class ReceivedInput:
    """One supported raw MIDI message and its optional physical event."""

    message: RawMidiMessage
    physical_event: PhysicalControlEvent | None


class XTouchCompactSession:
    """Bidirectional session for the fixed factory X-TOUCH COMPACT profile.

    As a context manager, connects and initializes on entry and closes on exit.
    Receiving, sending, feedback setters, and sync_feedback() require READY.
    Last-sent feedback records successful transport sends, not device acknowledgements.
    See docs/api.md for the contract and docs/usage.md for examples.
    """

    def __init__(
        self,
        transport: MidiTransport,
        *,
        global_midi_channel: int,
        startup_layer: Layer = Layer.A,
    ) -> None:
        _validate_session_construction(global_midi_channel, startup_layer)
        self._transport = transport
        self._decoder = InboundDecoder()
        self._startup_layer = startup_layer
        self._feedback_encoder = SemanticFeedbackEncoder(
            global_midi_channel=global_midi_channel
        )
        self._state = SessionState.DISCONNECTED
        self._faders = FaderStateController()
        self._surface = SurfaceStateController(ASSIGNABLE_BUTTONS)
        self._surface.request_layer(startup_layer)

    @classmethod
    def open(
        cls,
        *,
        global_midi_channel: int,
        startup_layer: Layer = Layer.A,
        port_name: str | None = None,
        transport: MidiTransport | None = None,
    ) -> XTouchCompactSession:
        """Construct a disconnected session; no attached device is required.

        Uses ALSA unless transport is supplied. port_name filters ALSA discovery
        and cannot be combined with a supplied transport. Use as a context manager
        to connect, initialize, and close automatically.
        """
        if transport is None:
            from .alsa_transport import AlsaSequencerTransport

            transport = AlsaSequencerTransport(port_name=port_name)
        elif port_name is not None:
            raise SessionConfigurationError(
                "port_name applies only when using the default ALSA transport"
            )
        return cls(
            transport,
            global_midi_channel=global_midi_channel,
            startup_layer=startup_layer,
        )

    @property
    def state(self) -> SessionState:
        return self._state

    def connect(self) -> None:
        """Connect without enabling input; call initialize() before use.

        Requires DISCONNECTED. Failure, including interruption, leaves it disconnected.
        """
        if self._state is not SessionState.DISCONNECTED:
            raise LifecycleError("X-TOUCH session is already connected")
        self._state = SessionState.CONNECTING
        try:
            self._transport.connect()
        except BaseException:
            self._disconnect_after_failure()
            raise
        self._surface.invalidate_last_sent()
        self._state = SessionState.STARTUP_LAYER_UNASSERTED

    def initialize(self) -> None:
        """Send the configured preset-layer command and make input available."""
        if self._state is SessionState.DISCONNECTED:
            raise LifecycleError("X-TOUCH session is disconnected")
        if self._state is not SessionState.STARTUP_LAYER_UNASSERTED:
            raise LifecycleError("X-TOUCH session requires an unasserted connection")
        layer = self._surface.layer_state().desired or self._startup_layer
        self._send_transport(self._feedback_encoder.layer(layer))
        self._surface.layer_sent(layer)
        self._state = SessionState.READY

    def reconnect(self) -> None:
        """Close, reconnect, reassert the desired layer, and restore feedback.

        The default ALSA transport rediscovers the endpoint. Fader state resets;
        motors are never repositioned automatically. On failure, the session is
        disconnected and desired non-fader feedback is retained for retry.
        Receive timeouts cannot establish device loss; recovery must be explicit.
        See docs/usage.md#reconnect.
        """
        self.close()
        try:
            self.connect()
            self.initialize()
            self.sync_feedback()
        except BaseException:
            if self._state is not SessionState.DISCONNECTED:
                self._disconnect_after_failure()
            raise

    def receive(self, timeout: float | None = None) -> PhysicalControlEvent | None:
        """Receive one physical event, or None on timeout or unsupported input.

        Requires READY. Timeout is in seconds: None blocks indefinitely, zero
        polls, and a positive value bounds the wait. Use receive_input() to
        inspect supported MIDI that has no physical-event meaning.
        """
        received = self.receive_input(timeout=timeout)
        return None if received is None else received.physical_event

    def receive_input(self, timeout: float | None = None) -> ReceivedInput | None:
        """Receive supported raw MIDI and its optional physical event.

        Requires READY; timeout follows receive(). Returns None on timeout or an
        unsupported ALSA event. A received message can have physical_event=None.
        """
        self._require_ready()
        message = self._receive_transport(timeout)
        if message is None:
            return None
        physical_event = self._decoder.decode(message)
        self._apply_fader_event(physical_event)
        self._surface.physical_event(physical_event)
        return ReceivedInput(message, physical_event)

    def send(self, message: RawMidiMessage) -> None:
        """Send raw MIDI immediately, bypassing deduplication and touch ownership.

        Requires READY. Successful mapped output on the RX channel invalidates
        its feedback history; ring-mode output also invalidates display history.
        Raw fader output instead updates last_commanded_value and marks the
        observation non-current, preserving desired/observed values and ownership.
        sync_feedback() never restores faders. Unmapped or wrong-channel output
        has no tracking effect. Failed sends skip this bookkeeping;
        TransportConnectionError disconnects and resets live fader state and
        feedback history. See docs/usage.md#raw-diagnostic-output.
        """
        self._require_ready()
        self._send_transport(message)
        self._invalidate_raw_feedback_effect(message)

    def set_fader(self, fader: Fader, value: int) -> None:
        """Request a fader position, deferring motor commands while touched.

        Requires READY. Release reconciles the desired position; redundant
        commands are suppressed. close()/reconnect() reset fader state without
        restoring motor positions. See fader_state() and docs/usage.md#fader-ownership.
        """
        self._require_ready()
        message = self._feedback_encoder.fader(fader, value)
        command_value = self._faders.application_requested(fader, message.value)
        if command_value is not None:
            self._send_fader_command(fader, command_value)

    def fader_state(self, fader: Fader) -> FaderState:
        """Return an immutable snapshot of one fader's current state."""
        return self._faders.state(fader)

    def set_button_led(self, button: Button, state: ButtonLedState) -> None:
        """Set desired LED feedback, sending only if last-sent state differs.

        Requires READY. Last-sent records a successful send, not hardware confirmation.
        """
        self._require_ready()
        message = self._feedback_encoder.button_led(button, state)
        if not self._surface.request_button(button, state):
            return
        self._send_transport(message)
        self._surface.button_sent(button, state)

    def set_encoder_ring_mode(self, encoder: Encoder, mode: EncoderRingMode) -> None:
        """Set a ring's display mode and restore its known desired display.

        Requires READY; modes matching last-sent state are skipped. Mode changes
        redraw the ring, so its desired display is resent after the mode succeeds.
        """
        self._require_ready()
        message = self._feedback_encoder.encoder_ring_mode(encoder, mode)
        if not self._surface.request_encoder_mode(encoder, mode):
            return
        self._send_transport(message)
        self._surface.encoder_mode_sent(encoder, mode)
        display = self._surface.encoder_state(encoder).desired_display
        if display is not None:
            self.set_encoder_ring_value(encoder, display)

    def set_encoder_ring_value(
        self, encoder: Encoder, display: EncoderRingDisplay
    ) -> None:
        """Set the displayed state of one encoder LED ring."""
        self._require_ready()
        message = self._feedback_encoder.encoder_ring_value(encoder, display)
        if not self._surface.request_encoder_display(encoder, display):
            return
        self._send_transport(message)
        self._surface.encoder_display_sent(encoder, display)

    def select_layer(self, layer: Layer) -> None:
        """Select Layer A or B. Requires READY and always transmits.

        Even repeated selections assert device state: physical layer changes
        are not reliably reported to the host.
        """
        self._require_ready()
        message = self._feedback_encoder.layer(layer)
        # Physical layer-button changes are not reported to the host. Always
        # transmit an explicit selection so local device state cannot make the
        # tracked last-sent value stale.
        self._surface.request_layer(layer)
        self._send_transport(message)
        self._surface.layer_sent(layer)

    def set_foot_switch_led(self, state: StatusLedState) -> None:
        """Set the host-controllable foot-switch status LED."""
        self._require_ready()
        message = self._feedback_encoder.foot_switch_led(state)
        if not self._surface.request_status(FootControl.FOOT_SWITCH, state):
            return
        self._send_transport(message)
        self._surface.status_sent(FootControl.FOOT_SWITCH, state)

    def button_feedback_state(self, button: Button) -> ButtonFeedbackState:
        """Return an immutable snapshot for one assignable button LED."""
        return self._surface.button_state(button)

    def encoder_feedback_state(self, encoder: Encoder) -> EncoderFeedbackState:
        """Return an immutable snapshot for one encoder ring."""
        return self._surface.encoder_state(encoder)

    def layer_feedback_state(self) -> LayerFeedbackState:
        """Return an immutable snapshot of layer feedback state."""
        return self._surface.layer_state()

    def status_feedback_state(
        self, control: FootControl = FootControl.FOOT_SWITCH
    ) -> StatusFeedbackState:
        """Return an immutable snapshot for one supported status LED."""
        return self._surface.status_state(control)

    def surface_state(self) -> SurfaceStateSnapshot:
        """Return one immutable snapshot of synchronized surface feedback."""
        return self._surface.snapshot()

    def invalidate_feedback_state(self) -> None:
        """Mark all last-sent feedback unknown while preserving desired state."""
        self._surface.invalidate_last_sent()

    def sync_feedback(self) -> None:
        """Send only desired feedback that differs from last-sent state."""
        self._require_ready()
        snapshot = self._surface.snapshot()
        # Setters deduplicate against live last-sent state. In particular, a
        # mode change can restore the display before we reach its setter.
        for button_state in snapshot.buttons:
            if button_state.desired is not None:
                self.set_button_led(button_state.button, button_state.desired)
        for encoder_state in snapshot.encoders:
            if encoder_state.desired_mode is not None:
                self.set_encoder_ring_mode(
                    encoder_state.encoder, encoder_state.desired_mode
                )
            if encoder_state.desired_display is not None:
                self.set_encoder_ring_value(
                    encoder_state.encoder, encoder_state.desired_display
                )
        layer = snapshot.layer
        # Explicit layer selection always transmits, so sync checks it here.
        if layer.desired is not None and layer.desired != layer.last_sent:
            self.select_layer(layer.desired)
        for status_state in snapshot.status_leds:
            if status_state.desired is not None:
                self.set_foot_switch_led(status_state.desired)

    def __enter__(self) -> XTouchCompactSession:
        """Connect and initialize, returning the session in ``READY``."""
        self.connect()
        try:
            self.initialize()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close the session unconditionally, regardless of the exception."""
        self.close()

    def close(self) -> None:
        try:
            self._transport.close()
        finally:
            self._state = SessionState.DISCONNECTED
            self._faders.reset()
            self._surface.invalidate_last_sent()

    def _disconnect_after_failure(self) -> None:
        self._state = SessionState.DISCONNECTED
        self._faders.reset()
        self._surface.invalidate_last_sent()
        with suppress(Exception):
            self._transport.close()

    def _receive_transport(self, timeout: float | None) -> RawMidiMessage | None:
        try:
            return self._transport.receive(timeout=timeout)
        except TransportConnectionError:
            self._disconnect_after_failure()
            raise

    def _send_transport(self, message: RawMidiMessage) -> None:
        try:
            self._transport.send(message)
        except TransportConnectionError:
            self._disconnect_after_failure()
            raise

    def _apply_fader_event(self, event: PhysicalControlEvent | None) -> None:
        if not isinstance(event, (FaderPositionReported, FaderTouched, FaderReleased)):
            return
        command_value = self._faders.physical_event(event)
        if command_value is not None:
            self._send_fader_command(event.fader, command_value)

    def _send_fader_command(self, fader: Fader, value: int) -> None:
        # Uses the internal transport send, not the public send(): this is
        # semantic feedback bookkeeping, not diagnostic raw output, and
        # must not run through _invalidate_raw_feedback_effect.
        self._send_transport(self._feedback_encoder.fader(fader, value))
        self._faders.motor_command_sent(fader, value)

    def _invalidate_raw_feedback_effect(self, message: RawMidiMessage) -> None:
        """Update tracking after a successful raw send; see send() for effects."""
        channel = self._feedback_encoder.global_midi_channel
        if isinstance(message, ProgramChange):
            if matches_layer_program_change(message, channel):
                self._surface.invalidate_layer()
            return
        binding = classify_rx_message(message, channel)
        if binding is None:
            return
        if binding.operation == "led" and isinstance(binding.control, Button):
            self._surface.invalidate_button_led(binding.control)
        elif binding.operation == "ring_behavior" and isinstance(
            binding.control, Encoder
        ):
            self._surface.invalidate_encoder_mode(binding.control)
        elif binding.operation == "ring_value" and isinstance(binding.control, Encoder):
            self._surface.invalidate_encoder_display(binding.control)
        elif binding.operation == "status_led" and isinstance(
            binding.control, FootControl
        ):
            self._surface.invalidate_status_led(binding.control)
        elif (
            binding.operation == "position"
            and isinstance(binding.control, Fader)
            and isinstance(message, ControlChange)
        ):
            self._faders.motor_command_sent(binding.control, message.value)

    def _require_ready(self) -> None:
        if self._state is SessionState.READY:
            return
        if self._state is SessionState.DISCONNECTED:
            raise LifecycleError("X-TOUCH session is disconnected")
        if self._state is SessionState.CONNECTING:
            raise LifecycleError("X-TOUCH session is still connecting")
        raise LifecycleError("X-TOUCH session startup layer is unasserted")
