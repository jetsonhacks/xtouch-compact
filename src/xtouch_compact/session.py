"""Narrow X-TOUCH connection initialization and receive pipeline."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from enum import Enum

from .controls import Button, Encoder, Fader, FootControl, Layer
from .decoder import InboundDecoder
from .device_map import (
    RX_CONTROL_INDEX,
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
    """The stable application entry point: a semantic bidirectional session.

    Application code reasons about physical controls, typed physical
    events, semantic feedback values, and this lifecycle; it does not need
    transport, ALSA, or MIDI internals. See ``docs/api.md`` for the
    full lifecycle, reconnect, and feedback-synchronization contract.
    Also usable as a context manager: ``__enter__`` performs ``connect()``
    then ``initialize()`` and returns the ready session; ``__exit__`` always
    calls ``close()``. :meth:`open` constructs a session with the default
    ALSA transport and bundled device map.
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
        assignable_buttons = tuple(
            button for button in Button if (button, "led") in RX_CONTROL_INDEX
        )
        self._surface = SurfaceStateController(assignable_buttons)
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
        """Construct a session with the default ALSA transport.

        Does not connect and does not require the device to be attached.
        Uses the fixed factory device map; there is no configurable
        device specification. Use as a context manager to connect,
        initialize, and close:

        ``with XTouchCompactSession.open(global_midi_channel=2) as session:``

        ``port_name`` is forwarded to :class:`AlsaSequencerTransport` when
        ``transport`` is omitted. Pass ``transport`` only for tests or a
        non-ALSA backend; the explicit constructor remains available for
        the same purpose.
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
        """Connect the transport without yet publishing semantic input.

        A failure at any point, including ``BaseException`` such as
        ``KeyboardInterrupt``, leaves the session ``DISCONNECTED``.
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
        """Close, rediscover, reconnect, reassert layer, and restore feedback.

        ``reconnect()`` is a single synchronous transaction: it (1) performs
        fresh endpoint discovery when using the default ALSA transport,
        (2) establishes a fresh transport
        connection, (3) performs the mandatory startup layer assertion, and
        (4) restores desired surface feedback (button LEDs, encoder ring
        modes and displays, layer, and the foot-switch status LED) through
        :meth:`sync_feedback`. It resets fader interaction state (desired
        and observed positions, touch, ownership, and motor-command history)
        but never repositions motorized faders automatically. Every stage
        must succeed before the session reports ``READY``; a failure at any
        stage leaves the session ``DISCONNECTED`` with partial resources
        closed and desired feedback preserved for a later attempt. Passive
        ``receive()``/``receive_input()`` polling may not itself observe
        device disappearance on every host stack; call ``reconnect()``
        explicitly rather than relying on receive timeouts to detect loss.
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
        """Block for one decoded physical event, or ``None`` if unavailable.

        Requires ``READY``. ``timeout`` is seconds to wait. ``None`` blocks
        indefinitely; ``0`` polls and returns immediately; a positive value
        waits up to that many seconds. Returns ``None`` when the timeout
        elapses with no message, and also when a message arrives that has
        no physical-event meaning (for example unmapped or diagnostic-only
        traffic) — use :meth:`receive_input` to distinguish those cases.
        This is a synchronous polling interface; there is no callback,
        thread, or asyncio integration.
        """
        received = self.receive_input(timeout=timeout)
        return None if received is None else received.physical_event

    def receive_input(self, timeout: float | None = None) -> ReceivedInput | None:
        """Receive one raw MIDI message alongside its decoded event.

        Requires ``READY``. ``timeout`` has the same meaning as
        :meth:`receive`. Returns ``None`` on timeout or when the transport
        discards an unsupported ALSA event. Otherwise returns a
        :class:`ReceivedInput` whose
        ``physical_event`` is ``None`` for messages with no supported
        physical-control meaning, while ``message`` always carries the raw
        typed MIDI for diagnostics.
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
        """Send diagnostic MIDI immediately, bypassing deduplication and touch.

        After a successful send on the configured output channel, matching
        button/ring/status/layer commands invalidate their last-sent history.
        A ring-mode command also invalidates the ring's display history.
        Later setters or sync_feedback() can restore known desired feedback.

        A matching motor command instead records its raw value as
        last_commanded_value and marks the observation non-current. Desired
        value, observed position, and touch ownership remain unchanged.
        Subsequent set_fader() calls still defer while touched and suppress
        redundant commands; sync_feedback() does not reconcile faders.

        Wrong-channel and unmapped output has no tracking effect after a
        successful send. Failed sends skip this raw-output bookkeeping, but
        TransportConnectionError still disconnects and resets live fader
        state and feedback history through normal connection-loss handling.
        See docs/usage.md#raw-diagnostic-output for details.
        """
        self._require_ready()
        self._send_transport(message)
        self._invalidate_raw_feedback_effect(message)

    def set_fader(self, fader: Fader, value: int) -> None:
        """Set the application-desired position, subject to touch ownership.

        This does not mean "force the motor immediately regardless of touch
        state." It updates the fader's desired position and sends a motor
        command only while that fader is application-owned (untouched); a
        touched fader belongs to :attr:`~xtouch_compact.FaderOwner.HUMAN`
        and defers the motor command until release. See :meth:`fader_state`
        for the full snapshot including desired value, observed value, touch
        state, owner, and last commanded value. Fader state resets on
        ``close()``/``reconnect()``; motor positions are never restored
        automatically.
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
        """Set one assignable button LED's desired state.

        Updates desired feedback state and sends only when it differs from
        the last-sent value (semantic equality suppresses repeated
        commands). "Last-sent" means the last command this session
        successfully handed to the transport; the device gives no
        acknowledgement, so this is command history, not confirmed physical
        state. See :meth:`button_feedback_state`.
        """
        self._require_ready()
        message = self._feedback_encoder.button_led(button, state)
        if not self._surface.request_button(button, state):
            return
        self._send_transport(message)
        self._surface.button_sent(button, state)

    def set_encoder_ring_mode(self, encoder: Encoder, mode: EncoderRingMode) -> None:
        """Select the display mode for one encoder LED ring.

        Mode and display are separate semantic concepts, but hardware
        characterization found that a mode change redraws the ring from
        the local encoder value and replaces any remotely assigned
        display. After a successful mode change, this method therefore
        automatically resends the encoder's known desired display so
        callers do not have to manually restore it after every mode change.
        See ``docs/hardware-observations.md``.
        """
        self._require_ready()
        message = self._feedback_encoder.encoder_ring_mode(encoder, mode)
        if not self._surface.request_encoder_mode(encoder, mode):
            return
        self._send_transport(message)
        self._surface.encoder_mode_sent(encoder, mode)
        display = self._surface.encoder_state(encoder).desired_display
        if display is not None:
            self._send_transport(
                self._feedback_encoder.encoder_ring_value(encoder, display)
            )
            self._surface.encoder_display_sent(encoder, display)

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
        """Select Layer A or Layer B and always transmit the command.

        Unlike the other semantic setters, this is not an ordinary
        deduplicated feedback setter: it always sends its Program Change,
        even when tracked desired and last-sent layer state already match.
        Physical Layer A/B button presses on the device are not reliably
        reported to the host, so last-sent state alone cannot prove the
        device's actual layer. Every explicit call is therefore a device-
        state assertion, not just a state update.
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
        for button_state in snapshot.buttons:
            if (
                button_state.desired is not None
                and button_state.desired != button_state.last_sent
            ):
                self.set_button_led(button_state.button, button_state.desired)
        for encoder_state in snapshot.encoders:
            if (
                encoder_state.desired_mode is not None
                and encoder_state.desired_mode != encoder_state.last_sent_mode
            ):
                self.set_encoder_ring_mode(
                    encoder_state.encoder, encoder_state.desired_mode
                )
            if (
                encoder_state.desired_display is not None
                and encoder_state.desired_display != encoder_state.last_sent_display
            ):
                self.set_encoder_ring_value(
                    encoder_state.encoder, encoder_state.desired_display
                )
        layer = snapshot.layer
        if layer.desired is not None and layer.desired != layer.last_sent:
            self.select_layer(layer.desired)
        for status_state in snapshot.status_leds:
            if (
                status_state.desired is not None
                and status_state.desired != status_state.last_sent
            ):
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
        """Invalidate tracked command history a successful raw send affects.

        See :meth:`send` for the full contract this implements.
        """
        channel = self._feedback_encoder.global_midi_channel
        if isinstance(message, ProgramChange):
            if matches_layer_program_change(message, channel):
                self._surface.raw_layer_sent()
            return
        binding = classify_rx_message(message, channel)
        if binding is None:
            return
        if binding.operation == "led" and isinstance(binding.control, Button):
            self._surface.raw_button_led_sent(binding.control)
        elif binding.operation == "ring_behavior" and isinstance(
            binding.control, Encoder
        ):
            self._surface.raw_encoder_mode_sent(binding.control)
        elif binding.operation == "ring_value" and isinstance(binding.control, Encoder):
            self._surface.raw_encoder_display_sent(binding.control)
        elif binding.operation == "status_led" and isinstance(
            binding.control, FootControl
        ):
            self._surface.raw_status_sent(binding.control)
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
