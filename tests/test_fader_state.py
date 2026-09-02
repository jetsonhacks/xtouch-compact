from dataclasses import FrozenInstanceError

import pytest

from tests.helpers import FakeTransport, SessionBuilder
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


def test_fader_request_before_ready_does_not_change_state(
    build_session: SessionBuilder,
) -> None:
    session, _ = build_session()

    with pytest.raises(LifecycleError, match="disconnected"):
        session.set_fader(Fader.CHANNEL_1, 70)

    assert session.fader_state(Fader.CHANNEL_1).desired_value is None
