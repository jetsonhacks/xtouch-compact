"""Raw diagnostic ``send()`` as a state-invalidating override.

``send()`` bypasses semantic deduplication and touch ownership on the way
out, but a successful transmission that matches a tracked RX binding must
invalidate the affected *last-sent* command history so a later semantic
setter or :meth:`~xtouch_compact.XTouchCompactSession.sync_feedback` call
is not suppressed as a duplicate of the raw traffic. See ``send()``'s
docstring in ``session.py`` for the full contract.
"""

from __future__ import annotations

import pytest

from tests.helpers import FakeTransport, SendFailure, SessionFactory
from xtouch_compact import (
    Button,
    ButtonLedState,
    ControlChange,
    Encoder,
    EncoderRingDisplay,
    EncoderRingMode,
    Fader,
    FaderOwner,
    FootControl,
    Layer,
    LifecycleError,
    NoteOn,
    ProgramChange,
    StatusLedState,
    XTouchCompactSession,
)
from xtouch_compact.device_map import RX_CONTROL_INDEX


def test_raw_override_between_two_semantic_sets_does_not_suppress_the_final_one(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    """ON -> raw OFF -> semantic ON must transmit the final ON.

    Note 38 is PLAY's button-LED RX address (Quick Start Guide V6.0 p. 32);
    velocity 2/0 are the characterized ON/OFF values (see
    ``docs/hardware-observations.md``). Both are independent of the
    implementation's device-map table, not derived from it.
    """
    session, transport = ready_session

    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    session.send(NoteOn(2, 38, 0))  # raw diagnostic override
    session.set_button_led(Button.PLAY, ButtonLedState.ON)

    assert transport.sent == [
        NoteOn(2, 38, 2),
        NoteOn(2, 38, 0),
        NoteOn(2, 38, 2),
    ]
    assert session.button_feedback_state(Button.PLAY).desired is ButtonLedState.ON
    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.ON


def test_sync_feedback_alone_restores_a_previously_desired_led_after_raw_override(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    session.send(NoteOn(2, 38, 0))
    transport.sent.clear()

    session.sync_feedback()

    assert transport.sent == [NoteOn(2, 38, 2)]
    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.ON


def test_raw_send_does_not_disturb_an_unrelated_button(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    session.set_button_led(Button.RECORD, ButtonLedState.ON)

    session.send(NoteOn(2, 38, 0))  # PLAY's address only

    assert session.button_feedback_state(Button.PLAY).last_sent is None
    assert session.button_feedback_state(Button.RECORD).last_sent is ButtonLedState.ON


def test_raw_send_on_the_wrong_channel_leaves_tracked_state_untouched(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session
    session.set_button_led(Button.PLAY, ButtonLedState.ON)

    session.send(NoteOn(5, 38, 0))  # session channel is 2

    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.ON


def test_raw_send_to_an_unmapped_address_leaves_tracked_state_untouched(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session
    session.set_button_led(Button.PLAY, ButtonLedState.ON)

    session.send(NoteOn(2, 100, 0))  # no RX binding at this address

    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.ON


def test_raw_ring_mode_command_invalidates_both_mode_and_display_history(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    """A raw ring-mode command redraws the display too, exactly like the
    semantic ``set_encoder_ring_mode()`` cross-effect it stands in for."""
    session, transport = ready_session
    encoder = Encoder.CHANNEL_1
    session.set_encoder_ring_mode(encoder, EncoderRingMode.PAN)
    session.set_encoder_ring_value(encoder, EncoderRingDisplay.at(7))
    mode_binding = RX_CONTROL_INDEX[(encoder, "ring_behavior")]

    session.send(ControlChange(2, mode_binding.address.number, 2))  # raw FAN

    state = session.encoder_feedback_state(encoder)
    assert state.desired_mode is EncoderRingMode.PAN
    assert state.desired_display == EncoderRingDisplay.at(7)
    assert state.last_sent_mode is None
    assert state.last_sent_display is None

    transport.sent.clear()
    session.sync_feedback()

    display_binding = RX_CONTROL_INDEX[(encoder, "ring_value")]
    assert transport.sent == [
        ControlChange(2, mode_binding.address.number, 1),  # PAN restored
        ControlChange(2, display_binding.address.number, 7),  # display restored
    ]


def test_raw_ring_value_command_invalidates_only_display_history(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    encoder = Encoder.CHANNEL_1
    session.set_encoder_ring_mode(encoder, EncoderRingMode.PAN)
    session.set_encoder_ring_value(encoder, EncoderRingDisplay.at(7))
    display_binding = RX_CONTROL_INDEX[(encoder, "ring_value")]

    session.send(ControlChange(2, display_binding.address.number, 0))  # raw all_off

    state = session.encoder_feedback_state(encoder)
    assert state.last_sent_mode is EncoderRingMode.PAN
    assert state.last_sent_display is None

    transport.sent.clear()
    session.sync_feedback()

    assert transport.sent == [ControlChange(2, display_binding.address.number, 7)]


def test_raw_send_does_not_disturb_an_unrelated_encoder(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session
    turned, untouched = Encoder.CHANNEL_1, Encoder.CHANNEL_2
    session.set_encoder_ring_value(turned, EncoderRingDisplay.at(7))
    session.set_encoder_ring_value(untouched, EncoderRingDisplay.at(7))
    binding = RX_CONTROL_INDEX[(turned, "ring_value")]

    session.send(ControlChange(2, binding.address.number, 0))

    assert session.encoder_feedback_state(turned).last_sent_display is None
    assert session.encoder_feedback_state(
        untouched
    ).last_sent_display == EncoderRingDisplay.at(7)


def test_raw_program_change_invalidates_layer_last_sent_history(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session

    session.send(ProgramChange(2, 1))  # raw layer B assertion

    state = session.layer_feedback_state()
    assert state.desired is Layer.A
    assert state.last_sent is None

    transport.sent.clear()
    session.sync_feedback()

    # select_layer() always transmits regardless of last-sent history.
    assert transport.sent == [ProgramChange(2, 0)]


def test_raw_status_led_command_invalidates_status_history(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    session.set_foot_switch_led(StatusLedState.ON)
    binding = RX_CONTROL_INDEX[(FootControl.FOOT_SWITCH, "status_led")]

    session.send(ControlChange(2, binding.address.number, 0))  # raw diagnostic OFF

    state = session.status_feedback_state()
    assert state.desired is StatusLedState.ON
    assert state.last_sent is None

    transport.sent.clear()
    session.sync_feedback()

    assert transport.sent == [ControlChange(2, binding.address.number, 127)]


def test_raw_motor_command_invalidates_history_without_touching_desired_or_observed(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1
    session.set_fader(fader, 90)
    transport.messages.append(ControlChange(1, 1, 90))
    session.receive_input()  # observed == desired, observation current
    transport.sent.clear()

    session.send(ControlChange(2, 1, 40))  # raw motor override

    state = session.fader_state(fader)
    assert state.desired_value == 90
    assert state.observed_value == 90
    assert not state.observation_is_current
    assert state.last_commanded_value == 40
    assert state.owner is FaderOwner.APPLICATION
    assert not state.touched

    session.set_fader(fader, 90)  # must reassert: raw diverged from desired

    assert transport.sent == [ControlChange(2, 1, 40), ControlChange(2, 1, 90)]


def test_raw_motor_command_matching_desired_value_suppresses_a_redundant_resend(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    """A stale (non-current) observation must not block a *needed* command,
    but raw history that already matches desired must not force a
    redundant one either."""
    session, transport = ready_session
    fader = Fader.CHANNEL_1
    session.set_fader(fader, 90)
    transport.sent.clear()

    session.send(ControlChange(2, 1, 90))  # raw command happens to match desired
    session.set_fader(fader, 90)

    assert transport.sent == [ControlChange(2, 1, 90)]


def test_raw_send_does_not_disturb_touch_ownership_or_a_deferred_desired_value(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1
    transport.messages.append(ControlChange(1, 101, 127))  # touch
    session.receive_input()
    session.set_fader(fader, 40)  # touched: desired only, deferred, no send

    session.send(ControlChange(2, 1, 10))  # raw output still transmits while touched

    state = session.fader_state(fader)
    assert state.owner is FaderOwner.HUMAN
    assert state.touched
    assert state.desired_value == 40
    assert state.last_commanded_value == 10

    transport.messages.append(ControlChange(1, 101, 0))  # release
    session.receive_input()

    assert transport.sent[-1] == ControlChange(2, 1, 40)


def test_raw_send_does_not_disturb_an_unrelated_fader(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session
    session.set_fader(Fader.CHANNEL_1, 50)
    session.set_fader(Fader.CHANNEL_2, 50)

    session.send(ControlChange(2, 1, 10))  # CHANNEL_1's RX address only

    assert session.fader_state(Fader.CHANNEL_1).last_commanded_value == 10
    assert session.fader_state(Fader.CHANNEL_2).last_commanded_value == 50


def test_failed_raw_send_does_not_invalidate_tracked_history(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    transport.fail_next_send = True

    with pytest.raises(SendFailure):
        session.send(NoteOn(2, 38, 0))

    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.ON


def test_failed_raw_fader_send_does_not_invalidate_command_history(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    session.set_fader(Fader.CHANNEL_1, 90)
    transport.fail_next_send = True

    with pytest.raises(SendFailure):
        session.send(ControlChange(2, 1, 40))

    state = session.fader_state(Fader.CHANNEL_1)
    assert state.last_commanded_value == 90
    assert state.observation_is_current is False


def test_semantic_output_before_ready_is_unaffected_by_raw_send_changes(
    build_session: SessionFactory,
) -> None:
    """Regression guard: raw-send bookkeeping must not affect the ordinary
    not-ready guard shared with every other public output method."""
    session, transport = build_session()

    with pytest.raises(LifecycleError, match="disconnected"):
        session.send(NoteOn(2, 38, 0))

    assert transport.sent == []
