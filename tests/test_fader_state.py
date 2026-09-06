from dataclasses import FrozenInstanceError

import pytest

from tests.helpers import FakeTransport, SendFailure, SessionFactory
from xtouch_compact import (
    ControlChange,
    Fader,
    FaderOwner,
    FaderPositionReported,
    FaderReleased,
    FaderTouched,
    LifecycleError,
    XTouchCompactSession,
)


def receive(
    session: XTouchCompactSession,
    transport: FakeTransport,
    message: ControlChange,
) -> object:
    transport.messages.append(message)
    received = session.receive_input()
    assert received is not None
    return received.physical_event


def test_all_faders_start_with_independent_application_owned_state(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session

    states = [session.fader_state(fader) for fader in Fader]

    assert len(states) == 9
    assert len({id(state) for state in states}) == 9
    assert all(state.owner is FaderOwner.APPLICATION for state in states)
    assert all(not state.touched for state in states)
    assert all(state.desired_value is None for state in states)
    assert all(state.observed_value is None for state in states)
    assert all(state.last_commanded_value is None for state in states)


def test_required_ownership_and_reconciliation_scenario(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    session.set_fader(fader, 90)
    assert session.fader_state(fader).desired_value == 90
    assert transport.sent == [ControlChange(2, 1, 90)]

    moved = receive(session, transport, ControlChange(1, 1, 90))
    assert isinstance(moved, FaderPositionReported)
    assert session.fader_state(fader).observed_value == 90

    touched = receive(session, transport, ControlChange(1, 101, 127))
    assert isinstance(touched, FaderTouched)
    assert session.fader_state(fader).touched
    assert session.fader_state(fader).owner is FaderOwner.HUMAN

    session.set_fader(fader, 40)
    assert session.fader_state(fader).desired_value == 40
    assert transport.sent == [ControlChange(2, 1, 90)]

    moved = receive(session, transport, ControlChange(1, 1, 65))
    state = session.fader_state(fader)
    assert isinstance(moved, FaderPositionReported)
    assert state.observed_value == 65
    assert state.desired_value == 40
    assert state.owner is FaderOwner.HUMAN

    released = receive(session, transport, ControlChange(1, 101, 0))
    state = session.fader_state(fader)
    assert isinstance(released, FaderReleased)
    assert not state.touched
    assert state.owner is FaderOwner.APPLICATION
    assert state.last_commanded_value == 40
    assert transport.sent == [ControlChange(2, 1, 90), ControlChange(2, 1, 40)]

    moved = receive(session, transport, ControlChange(1, 1, 40))
    assert isinstance(moved, FaderPositionReported)
    assert session.fader_state(fader).observed_value == 40


def test_movement_alone_does_not_change_ownership_or_desired_value(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    session.set_fader(Fader.CHANNEL_1, 80)

    receive(session, transport, ControlChange(1, 1, 72))

    state = session.fader_state(Fader.CHANNEL_1)
    assert state.observed_value == 72
    assert state.desired_value == 80
    assert state.owner is FaderOwner.APPLICATION


def test_release_without_a_reconciliation_difference_sends_nothing(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session

    receive(session, transport, ControlChange(1, 101, 127))
    receive(session, transport, ControlChange(1, 101, 0))
    assert transport.sent == []

    session.set_fader(Fader.CHANNEL_1, 40)
    receive(session, transport, ControlChange(1, 1, 40))
    receive(session, transport, ControlChange(1, 101, 127))
    receive(session, transport, ControlChange(1, 101, 0))
    assert transport.sent == [ControlChange(2, 1, 40)]


def test_touched_fader_does_not_block_another_fader(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    receive(session, transport, ControlChange(1, 101, 127))

    session.set_fader(Fader.CHANNEL_1, 30)
    session.set_fader(Fader.CHANNEL_2, 70)

    assert session.fader_state(Fader.CHANNEL_1).owner is FaderOwner.HUMAN
    assert session.fader_state(Fader.CHANNEL_2).owner is FaderOwner.APPLICATION
    assert transport.sent == [ControlChange(2, 2, 70)]


def test_repeated_inputs_do_not_send_redundant_motor_commands(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session

    session.set_fader(Fader.CHANNEL_1, 64)
    session.set_fader(Fader.CHANNEL_1, 64)
    receive(session, transport, ControlChange(1, 101, 127))
    receive(session, transport, ControlChange(1, 101, 127))
    receive(session, transport, ControlChange(1, 1, 50))
    receive(session, transport, ControlChange(1, 1, 50))
    receive(session, transport, ControlChange(1, 101, 0))
    receive(session, transport, ControlChange(1, 101, 0))

    assert transport.sent == [ControlChange(2, 1, 64), ControlChange(2, 1, 64)]


def test_close_resets_fader_state_and_snapshots_are_immutable(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, _ = ready_session
    session.set_fader(Fader.MAIN, 127)
    snapshot = session.fader_state(Fader.MAIN)

    with pytest.raises(FrozenInstanceError):
        snapshot.desired_value = 1  # type: ignore[misc]

    session.close()
    reset = session.fader_state(Fader.MAIN)
    assert reset.desired_value is None
    assert reset.last_commanded_value is None
    assert reset.owner is FaderOwner.APPLICATION


def test_repeated_differing_commands_without_observation_both_send(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    session.set_fader(fader, 90)
    session.set_fader(fader, 20)

    assert transport.sent == [ControlChange(2, 1, 90), ControlChange(2, 1, 20)]


def test_command_touch_without_movement_request_release_reasserts(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    session.set_fader(fader, 90)
    receive(session, transport, ControlChange(1, 101, 127))  # touch, no movement
    session.set_fader(fader, 20)  # touched: desired only, no send
    receive(session, transport, ControlChange(1, 101, 0))  # release

    assert transport.sent == [ControlChange(2, 1, 90), ControlChange(2, 1, 20)]


def test_touch_current_observation_equal_to_request_suppresses_release(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    receive(session, transport, ControlChange(1, 101, 127))  # touch
    receive(session, transport, ControlChange(1, 1, 30))  # observed 30, current
    session.set_fader(fader, 30)  # touched: desired only
    receive(session, transport, ControlChange(1, 101, 0))  # release

    assert transport.sent == []


def test_touch_current_observation_differing_from_request_reasserts_on_release(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    receive(session, transport, ControlChange(1, 101, 127))  # touch
    receive(session, transport, ControlChange(1, 1, 30))  # observed 30, current
    session.set_fader(fader, 70)
    receive(session, transport, ControlChange(1, 101, 0))  # release

    assert transport.sent == [ControlChange(2, 1, 70)]


def test_repeated_identical_requests_without_intervening_input_suppress(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    session.set_fader(fader, 50)
    session.set_fader(fader, 50)

    assert transport.sent == [ControlChange(2, 1, 50)]


def test_newer_current_observation_takes_precedence_over_command_history(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    session.set_fader(fader, 50)
    receive(session, transport, ControlChange(1, 1, 30))  # newer differing position
    session.set_fader(fader, 50)  # must reassert, not suppress via command history

    assert transport.sent == [ControlChange(2, 1, 50), ControlChange(2, 1, 50)]


def test_observation_validity_after_send_observation_and_reset(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    receive(session, transport, ControlChange(1, 1, 30))
    assert session.fader_state(fader).observation_is_current

    session.set_fader(fader, 50)
    assert not session.fader_state(fader).observation_is_current

    receive(session, transport, ControlChange(1, 1, 50))
    assert session.fader_state(fader).observation_is_current

    session.close()
    assert not session.fader_state(fader).observation_is_current


def test_observation_validity_unaffected_by_failed_send(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1
    receive(session, transport, ControlChange(1, 1, 50))
    assert session.fader_state(fader).observation_is_current

    transport.fail_next_send = True
    with pytest.raises(SendFailure):
        session.set_fader(fader, 90)

    state = session.fader_state(fader)
    assert state.observation_is_current
    assert state.last_commanded_value is None


def test_application_requested_suppresses_against_equal_current_observation(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    receive(session, transport, ControlChange(1, 1, 50))  # observed 50, current
    session.set_fader(fader, 50)  # application-owned, matches current observation

    assert transport.sent == []
    assert session.fader_state(fader).desired_value == 50


def test_release_suppresses_against_equal_stale_last_commanded_value(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session
    fader = Fader.CHANNEL_1

    session.set_fader(fader, 40)  # sends 40, invalidates observation currency
    receive(session, transport, ControlChange(1, 101, 127))  # touch
    session.set_fader(fader, 40)  # touched: desired only, still matches history
    receive(session, transport, ControlChange(1, 101, 0))  # release

    assert transport.sent == [ControlChange(2, 1, 40)]


def test_observation_validity_is_independent_per_fader(
    ready_session: tuple[XTouchCompactSession, FakeTransport],
) -> None:
    session, transport = ready_session

    receive(session, transport, ControlChange(1, 1, 50))  # CHANNEL_1 observed
    session.set_fader(Fader.CHANNEL_2, 90)  # CHANNEL_2 command, unrelated fader

    assert session.fader_state(Fader.CHANNEL_1).observation_is_current
    assert not session.fader_state(Fader.CHANNEL_2).observation_is_current


def test_fader_request_before_ready_does_not_change_state(
    build_session: SessionFactory,
) -> None:
    session, _ = build_session()

    with pytest.raises(LifecycleError, match="disconnected"):
        session.set_fader(Fader.CHANNEL_1, 70)

    assert session.fader_state(Fader.CHANNEL_1).desired_value is None
