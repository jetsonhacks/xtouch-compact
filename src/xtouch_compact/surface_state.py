"""Desired and last-sent state for host-controlled surface feedback."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .controls import Button, Encoder, FootControl, Layer
from .errors import UnsupportedOperationError
from .events import (
    ButtonPressed,
    ButtonReleased,
    EncoderPositionReported,
    PhysicalControlEvent,
)
from .feedback import (
    ButtonLedState,
    EncoderRingDisplay,
    EncoderRingMode,
    StatusLedState,
)

_TRANSPORT_BUTTONS = frozenset(
    {
        Button.REWIND,
        Button.FAST_FORWARD,
        Button.LOOP,
        Button.RECORD,
        Button.STOP,
        Button.PLAY,
    }
)


@dataclass(frozen=True, slots=True)
class ButtonFeedbackState:
    """Read-only feedback state for one assignable button LED."""

    button: Button
    desired: ButtonLedState | None = None
    last_sent: ButtonLedState | None = None


@dataclass(frozen=True, slots=True)
class EncoderFeedbackState:
    """Read-only mode and display state for one encoder ring."""

    encoder: Encoder
    desired_mode: EncoderRingMode | None = None
    last_sent_mode: EncoderRingMode | None = None
    desired_display: EncoderRingDisplay | None = None
    last_sent_display: EncoderRingDisplay | None = None


@dataclass(frozen=True, slots=True)
class LayerFeedbackState:
    """Read-only desired and last-sent layer selection."""

    desired: Layer | None = None
    last_sent: Layer | None = None


@dataclass(frozen=True, slots=True)
class StatusFeedbackState:
    """Read-only feedback state for one supported status LED."""

    control: FootControl
    desired: StatusLedState | None = None
    last_sent: StatusLedState | None = None


@dataclass(frozen=True, slots=True)
class SurfaceStateSnapshot:
    """Immutable snapshot of all host-controlled surface feedback."""

    buttons: tuple[ButtonFeedbackState, ...]
    encoders: tuple[EncoderFeedbackState, ...]
    layer: LayerFeedbackState
    status_leds: tuple[StatusFeedbackState, ...]


class SurfaceStateController:
    """Store desired feedback and the last commands sent successfully."""

    def __init__(self, assignable_buttons: tuple[Button, ...]) -> None:
        self._buttons = {
            button: ButtonFeedbackState(button) for button in assignable_buttons
        }
        self._encoders = {encoder: EncoderFeedbackState(encoder) for encoder in Encoder}
        self._layer = LayerFeedbackState()
        self._status_leds = {
            FootControl.FOOT_SWITCH: StatusFeedbackState(FootControl.FOOT_SWITCH)
        }

    def button_state(self, button: Button) -> ButtonFeedbackState:
        try:
            return self._buttons[button]
        except (KeyError, TypeError) as error:
            raise UnsupportedOperationError(
                f"{button!r} has no synchronized button LED"
            ) from error

    def encoder_state(self, encoder: Encoder) -> EncoderFeedbackState:
        try:
            return self._encoders[encoder]
        except (KeyError, TypeError) as error:
            raise UnsupportedOperationError(
                f"{encoder!r} has no synchronized encoder ring"
            ) from error

    def layer_state(self) -> LayerFeedbackState:
        return self._layer

    def status_state(self, control: FootControl) -> StatusFeedbackState:
        try:
            return self._status_leds[control]
        except (KeyError, TypeError) as error:
            raise UnsupportedOperationError(
                f"{control!r} has no synchronized status LED"
            ) from error

    def snapshot(self) -> SurfaceStateSnapshot:
        return SurfaceStateSnapshot(
            buttons=tuple(self._buttons.values()),
            encoders=tuple(self._encoders.values()),
            layer=self._layer,
            status_leds=tuple(self._status_leds.values()),
        )

    def physical_event(self, event: PhysicalControlEvent | None) -> None:
        """Invalidate feedback that a local control action can redraw."""
        if isinstance(event, ButtonPressed) and event.button in _TRANSPORT_BUTTONS:
            for button in _TRANSPORT_BUTTONS:
                current = self.button_state(button)
                self._buttons[button] = replace(current, last_sent=None)
        elif isinstance(event, ButtonReleased):
            # Measurement on 2026-08-09 found that releasing an assignable
            # button after a host BLINK command turned its LED off, replacing
            # rather than restoring the last remote state (see
            # ``docs/hardware-observations.md``, "Observed 2026-08-09: Buttons
            # and Layers"). Applied as a conservative group policy across all
            # assignable buttons from that one representative measurement.
            self.invalidate_button_led(event.button)
        elif isinstance(event, EncoderPositionReported):
            self.invalidate_encoder_display(event.encoder)

    def invalidate_button_led(self, button: Button) -> None:
        """Mark one button's last-sent LED state unknown, keeping desired state.

        Used where the device may have redrawn the LED locally, and after
        raw diagnostic output to the button's LED address, so the next
        matching-value request is not suppressed as a no-op duplicate.
        Identities without a synchronized LED, including Layer A/B, are
        ignored.
        """
        if button not in self._buttons:
            return
        self._buttons[button] = replace(self.button_state(button), last_sent=None)

    def request_button(self, button: Button, state: ButtonLedState) -> bool:
        current = self.button_state(button)
        self._buttons[button] = replace(current, desired=state)
        return current.last_sent != state

    def button_sent(self, button: Button, state: ButtonLedState) -> None:
        self._buttons[button] = replace(self.button_state(button), last_sent=state)

    def request_encoder_mode(self, encoder: Encoder, mode: EncoderRingMode) -> bool:
        current = self.encoder_state(encoder)
        self._encoders[encoder] = replace(current, desired_mode=mode)
        return current.last_sent_mode != mode

    def encoder_mode_sent(self, encoder: Encoder, mode: EncoderRingMode) -> None:
        self._encoders[encoder] = replace(
            self.encoder_state(encoder),
            last_sent_mode=mode,
            last_sent_display=None,
        )

    def request_encoder_display(
        self, encoder: Encoder, display: EncoderRingDisplay
    ) -> bool:
        current = self.encoder_state(encoder)
        self._encoders[encoder] = replace(current, desired_display=display)
        return current.last_sent_display != display

    def encoder_display_sent(
        self, encoder: Encoder, display: EncoderRingDisplay
    ) -> None:
        self._encoders[encoder] = replace(
            self.encoder_state(encoder), last_sent_display=display
        )

    def invalidate_encoder_display(self, encoder: Encoder) -> None:
        """Mark one encoder's last-sent ring display unknown.

        A physical rotation redraws the ring locally in every ring mode,
        so a remote display the session already believes it sent may no
        longer be visible. Call this once per decoded physical rotation
        so the next matching-value display request is not suppressed as a
        no-op duplicate. See ``docs/hardware-observations.md``.
        """
        self._encoders[encoder] = replace(
            self.encoder_state(encoder), last_sent_display=None
        )

    def request_layer(self, layer: Layer) -> None:
        self._layer = replace(self._layer, desired=layer)

    def layer_sent(self, layer: Layer) -> None:
        self._layer = replace(self._layer, last_sent=layer)

    def request_status(self, control: FootControl, state: StatusLedState) -> bool:
        current = self.status_state(control)
        self._status_leds[control] = replace(current, desired=state)
        return current.last_sent != state

    def status_sent(self, control: FootControl, state: StatusLedState) -> None:
        self._status_leds[control] = replace(
            self.status_state(control), last_sent=state
        )

    def invalidate_encoder_mode(self, encoder: Encoder) -> None:
        """Invalidate one encoder's ring-mode (and display) history.

        A raw ring-mode command has the same hardware side effect as
        :meth:`encoder_mode_sent`: it redraws the ring from the local
        encoder value and replaces any remotely assigned display. Both
        histories are therefore invalidated together, not just the mode.
        """
        self._encoders[encoder] = replace(
            self.encoder_state(encoder),
            last_sent_mode=None,
            last_sent_display=None,
        )

    def invalidate_status_led(self, control: FootControl) -> None:
        """Invalidate one status LED's history while preserving desired state."""
        self._status_leds[control] = replace(self.status_state(control), last_sent=None)

    def invalidate_layer(self) -> None:
        """Invalidate layer history while preserving desired state."""
        self._layer = replace(self._layer, last_sent=None)

    def invalidate_last_sent(self) -> None:
        for button in self._buttons:
            self.invalidate_button_led(button)
        for encoder in self._encoders:
            self.invalidate_encoder_mode(encoder)
        self.invalidate_layer()
        for control in self._status_leds:
            self.invalidate_status_led(control)
