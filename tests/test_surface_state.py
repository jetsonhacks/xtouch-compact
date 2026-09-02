from dataclasses import FrozenInstanceError

import pytest

from tests.helpers import FakeTransport, SendFailure, SessionBuilder
from xtouch_compact import (
    Button,
    ButtonLedState,
    ControlChange,
    Encoder,
    EncoderPositionReported,
    EncoderRingDisplay,
    EncoderRingMode,
    Fader,
    FootControl,
    Layer,
    NoteOn,
    ProgramChange,
    StatusLedState,
    XTouchCompactSession,
)


def test_initial_snapshot_covers_only_supported_feedback(
    build_session: SessionBuilder,
) -> None:
    session, _ = build_session()

    snapshot = session.surface_state()

    assert len(snapshot.buttons) == 39
    assert {state.button for state in snapshot.buttons} == set(Button) - {
        Button.LAYER_A,
        Button.LAYER_B,
    }
    assert all(state.desired is None for state in snapshot.buttons)
    assert all(state.last_sent is None for state in snapshot.buttons)
    assert len(snapshot.encoders) == 16
    assert all(state.desired_mode is None for state in snapshot.encoders)
    assert all(state.desired_display is None for state in snapshot.encoders)
    assert snapshot.layer.desired is Layer.A
    assert snapshot.layer.last_sent is None
    assert snapshot.status_leds[0].control is FootControl.FOOT_SWITCH


@pytest.mark.parametrize("state", list(ButtonLedState))
def test_button_updates_track_state_and_deduplicate(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    state: ButtonLedState,
) -> None:
    session, transport = ready_session
    button = Button.UPPER_TOP_1

    session.set_button_led(button, state)
    session.set_button_led(button, state)

    feedback = session.button_feedback_state(button)
    assert feedback.desired is state
    assert feedback.last_sent is state
    assert len(transport.sent) == 1


def test_buttons_track_and_send_independently(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session

    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    session.set_button_led(Button.RECORD, ButtonLedState.BLINK)
    session.set_button_led(Button.PLAY, ButtonLedState.OFF)

    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.OFF
    assert (
        session.button_feedback_state(Button.RECORD).last_sent is ButtonLedState.BLINK
    )
    assert len(transport.sent) == 3


def test_transport_button_press_invalidates_group_for_led_reassertion(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    session.set_button_led(Button.RECORD, ButtonLedState.BLINK)
    session.set_button_led(Button.UPPER_TOP_1, ButtonLedState.ON)
    transport.sent.clear()
    transport.messages.append(NoteOn(1, 54, 127))

    received = session.receive_input()

    assert received is not None
    assert session.button_feedback_state(Button.PLAY).last_sent is None
    assert session.button_feedback_state(Button.RECORD).last_sent is None
    assert (
        session.button_feedback_state(Button.UPPER_TOP_1).last_sent
        is ButtonLedState.ON
    )

    session.set_button_led(Button.PLAY, ButtonLedState.ON)

    assert len(transport.sent) == 1
    assert session.button_feedback_state(Button.PLAY).last_sent is ButtonLedState.ON


@pytest.mark.parametrize("mode", list(EncoderRingMode))
def test_encoder_modes_track_state_and_deduplicate(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    mode: EncoderRingMode,
) -> None:
    session, transport = ready_session

    session.set_encoder_ring_mode(Encoder.CHANNEL_1, mode)
    session.set_encoder_ring_mode(Encoder.CHANNEL_1, mode)

    state = session.encoder_feedback_state(Encoder.CHANNEL_1)
    assert state.desired_mode is mode
    assert state.last_sent_mode is mode
    assert len(transport.sent) == 1


@pytest.mark.parametrize(
    "display",
    [
        EncoderRingDisplay.off(),
        EncoderRingDisplay.at(1),
        EncoderRingDisplay.at(7),
        EncoderRingDisplay.blinking_at(13),
        EncoderRingDisplay.all_on(),
        EncoderRingDisplay.all_blinking(),
    ],
)
def test_encoder_displays_track_state_and_deduplicate(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    display: EncoderRingDisplay,
) -> None:
    session, transport = ready_session

    session.set_encoder_ring_value(Encoder.POSITION_16, display)
    session.set_encoder_ring_value(Encoder.POSITION_16, display)

    state = session.encoder_feedback_state(Encoder.POSITION_16)
    assert state.desired_display == display
    assert state.last_sent_display == display
    assert len(transport.sent) == 1


def test_encoder_mode_and_display_synchronize_independently(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    encoder = Encoder.CHANNEL_2

    session.set_encoder_ring_mode(encoder, EncoderRingMode.PAN)
    session.set_encoder_ring_value(encoder, EncoderRingDisplay.at(5))
    transport.sent.clear()
    session.set_encoder_ring_value(encoder, EncoderRingDisplay.at(7))

    state = session.encoder_feedback_state(encoder)
    assert state.last_sent_mode is EncoderRingMode.PAN
    assert state.last_sent_display == EncoderRingDisplay.at(7)
    assert len(transport.sent) == 1


def test_encoder_mode_change_restores_known_desired_display(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    encoder = Encoder.CHANNEL_2
    display = EncoderRingDisplay.at(10)
    session.set_encoder_ring_value(encoder, display)
    transport.sent.clear()

    session.set_encoder_ring_mode(encoder, EncoderRingMode.PAN)

    assert transport.sent == [ControlChange(2, 11, 1), ControlChange(2, 27, 10)]
    state = session.encoder_feedback_state(encoder)
    assert state.last_sent_mode is EncoderRingMode.PAN
    assert state.last_sent_display == display


def test_physical_rotation_invalidates_last_sent_display_for_reassertion(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    """A physical rotation redraws the ring locally in every ring mode (M7
    Encoders and Rings), so a remote display the session believes it
    already sent may no longer be visible. The next matching-value
    ``set_encoder_ring_value()`` call must not be suppressed as a no-op
    duplicate."""
    session, transport = ready_session
    encoder = Encoder.CHANNEL_1
    display = EncoderRingDisplay.at(7)
    session.set_encoder_ring_value(encoder, display)
    assert session.encoder_feedback_state(encoder).last_sent_display == display
    transport.messages.append(ControlChange(1, 10, 64))  # encoder_1 turn, TX channel

    received = session.receive_input()

    assert isinstance(received.physical_event, EncoderPositionReported)
    assert session.encoder_feedback_state(encoder).last_sent_display is None
    transport.sent.clear()

    session.set_encoder_ring_value(encoder, display)

    assert transport.sent == [ControlChange(2, 26, 7)]
    assert session.encoder_feedback_state(encoder).last_sent_display == display


def test_physical_rotation_does_not_invalidate_other_encoders_display(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    turned, untouched = Encoder.CHANNEL_1, Encoder.CHANNEL_2
    display = EncoderRingDisplay.at(7)
    session.set_encoder_ring_value(turned, display)
    session.set_encoder_ring_value(untouched, display)
    transport.messages.append(ControlChange(1, 10, 64))  # encoder_1 turn, TX channel

    session.receive_input()

    assert session.encoder_feedback_state(turned).last_sent_display is None
    assert session.encoder_feedback_state(untouched).last_sent_display == display


def test_encoders_track_state_independently(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session

    session.set_encoder_ring_mode(Encoder.CHANNEL_1, EncoderRingMode.PAN)
    session.set_encoder_ring_mode(Encoder.CHANNEL_2, EncoderRingMode.FAN)

    assert (
        session.encoder_feedback_state(Encoder.CHANNEL_1).last_sent_mode
        is EncoderRingMode.PAN
    )
    assert (
        session.encoder_feedback_state(Encoder.CHANNEL_2).last_sent_mode
        is EncoderRingMode.FAN
    )


@pytest.mark.parametrize("layer", list(Layer))
def test_layer_updates_track_state_and_reassert_on_repeated_selection(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    layer: Layer,
) -> None:
    session, transport = ready_session

    session.select_layer(layer)
    session.select_layer(layer)

    state = session.layer_feedback_state()
    assert state.desired is layer
    assert state.last_sent is layer
    assert transport.sent == [
        ProgramChange(2, 0 if layer is Layer.A else 1),
        ProgramChange(2, 0 if layer is Layer.A else 1),
    ]


def test_startup_layer_assertion_is_recorded_and_never_deduplicated(
    build_session: SessionBuilder,
) -> None:
    session, transport = build_session(startup_layer=Layer.B)

    session.connect()
    session.initialize()
    session.select_layer(Layer.B)
    session.close()
    session.connect()
    session.initialize()

    assert transport.sent == [
        ProgramChange(2, 1),
        ProgramChange(2, 1),
        ProgramChange(2, 1),
    ]
    assert session.layer_feedback_state().desired is Layer.B
    assert session.layer_feedback_state().last_sent is Layer.B


@pytest.mark.parametrize("state", list(StatusLedState))
def test_status_led_tracks_state_and_deduplicates(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    state: StatusLedState,
) -> None:
    session, transport = ready_session

    session.set_foot_switch_led(state)
    session.set_foot_switch_led(state)

    feedback = session.status_feedback_state()
    assert feedback.desired is state
    assert feedback.last_sent is state
    assert len(transport.sent) == 1


@pytest.mark.parametrize(
    ("update", "inspect", "desired_attribute", "last_sent_attribute"),
    [
        (
            lambda session: session.set_button_led(Button.PLAY, ButtonLedState.ON),
            lambda session: session.button_feedback_state(Button.PLAY),
            "desired",
            "last_sent",
        ),
        (
            lambda session: session.set_encoder_ring_mode(
                Encoder.CHANNEL_1, EncoderRingMode.PAN
            ),
            lambda session: session.encoder_feedback_state(Encoder.CHANNEL_1),
            "desired_mode",
            "last_sent_mode",
        ),
        (
            lambda session: session.select_layer(Layer.B),
            lambda session: session.layer_feedback_state(),
            "desired",
            "last_sent",
        ),
        (
            lambda session: session.set_foot_switch_led(StatusLedState.ON),
            lambda session: session.status_feedback_state(),
            "desired",
            "last_sent",
        ),
    ],
)
def test_failed_send_preserves_desired_state_for_retry(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
    update: object,
    inspect: object,
    desired_attribute: str,
    last_sent_attribute: str,
) -> None:
    session, transport = ready_session
    before = inspect(session)  # type: ignore[operator]
    previous_last_sent = getattr(before, last_sent_attribute)
    transport.fail_next_send = True

    with pytest.raises(SendFailure):
        update(session)  # type: ignore[operator]

    failed = inspect(session)  # type: ignore[operator]
    assert getattr(failed, desired_attribute) is not None
    assert getattr(failed, last_sent_attribute) == previous_last_sent

    update(session)  # type: ignore[operator]
    retried = inspect(session)  # type: ignore[operator]
    assert getattr(retried, last_sent_attribute) == getattr(retried, desired_attribute)
    assert len(transport.sent) == 1


def test_invalidation_and_sync_resend_only_known_desired_feedback(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    session.set_encoder_ring_mode(Encoder.CHANNEL_1, EncoderRingMode.PAN)
    session.set_encoder_ring_value(Encoder.CHANNEL_1, EncoderRingDisplay.at(7))
    session.set_foot_switch_led(StatusLedState.ON)
    transport.sent.clear()

    session.invalidate_feedback_state()
    invalid = session.surface_state()
    assert session.button_feedback_state(Button.PLAY).last_sent is None
    assert session.encoder_feedback_state(Encoder.CHANNEL_1).last_sent_mode is None
    assert invalid.layer.last_sent is None
    assert session.status_feedback_state().last_sent is None

    session.sync_feedback()

    assert len(transport.sent) == 5
    assert sum(isinstance(message, NoteOn) for message in transport.sent) == 1
    assert sum(isinstance(message, ProgramChange) for message in transport.sent) == 1
    session.sync_feedback()
    assert len(transport.sent) == 5


def test_close_preserves_desired_feedback_and_invalidates_last_sent(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    session.set_encoder_ring_value(Encoder.CHANNEL_1, EncoderRingDisplay.at(7))

    session.close()

    assert session.button_feedback_state(Button.PLAY).desired is ButtonLedState.ON
    assert session.button_feedback_state(Button.PLAY).last_sent is None
    encoder = session.encoder_feedback_state(Encoder.CHANNEL_1)
    assert encoder.desired_display == EncoderRingDisplay.at(7)
    assert encoder.last_sent_display is None
    assert session.fader_state(Fader.CHANNEL_1).desired_value is None


def test_public_snapshots_are_immutable(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session
    snapshot = session.surface_state()

    with pytest.raises(FrozenInstanceError):
        snapshot.layer.desired = Layer.B  # type: ignore[misc]
    with pytest.raises(TypeError):
        snapshot.buttons[0] = snapshot.buttons[1]  # type: ignore[index]

    assert session.layer_feedback_state().desired is Layer.A


def test_sync_feedback_leaves_fader_ownership_with_m4(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    transport.messages.append(ControlChange(1, 101, 127))
    session.receive_input()
    session.set_fader(Fader.CHANNEL_1, 70)

    session.sync_feedback()
    assert transport.sent == []

    transport.messages.append(ControlChange(1, 101, 0))
    session.receive_input()
    assert transport.sent == [ControlChange(2, 1, 70)]
