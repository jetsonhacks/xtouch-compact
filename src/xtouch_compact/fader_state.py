"""State and ownership rules for the nine motorized faders."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .controls import Fader
from .events import FaderPositionReported, FaderReleased, FaderTouched


class FaderOwner(Enum):
    """The party currently allowed to move one motorized fader."""

    APPLICATION = "application"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class FaderState:
    """Read-only snapshot of application and device state for one fader.

    ``observation_is_current`` means only that no motor command has been
    sent since ``observed_value`` was last reported: it is not hardware
    acknowledgement or a guarantee of present physical position. A decoded
    position report sets it true; a successfully sent motor command sets
    it false. Ordinary host-driven motor travel has no reliable position
    echo, so a stale (non-current) observation must not suppress a needed
    command, while touch alone does not refresh it.
    """

    desired_value: int | None = None
    observed_value: int | None = None
    observation_is_current: bool = False
    touched: bool = False
    owner: FaderOwner = FaderOwner.APPLICATION
    last_commanded_value: int | None = None


@dataclass(frozen=True, slots=True)
class FaderTransition:
    """One state transition and its optional motor-command action."""

    state: FaderState
    command_value: int | None = None


def _application_requested(state: FaderState, value: int) -> FaderTransition:
    """Give touched faders to the human and reconcile them on release."""
    updated = replace(state, desired_value=value)
    if state.owner is FaderOwner.HUMAN:
        return FaderTransition(updated)
    if state.observation_is_current:
        if state.observed_value == value:
            return FaderTransition(updated)
        return FaderTransition(updated, value)
    if state.last_commanded_value == value:
        return FaderTransition(updated)
    return FaderTransition(updated, value)


def _position_reported(state: FaderState, value: int) -> FaderTransition:
    return FaderTransition(
        replace(state, observed_value=value, observation_is_current=True)
    )


def _touched(state: FaderState) -> FaderTransition:
    return FaderTransition(replace(state, touched=True, owner=FaderOwner.HUMAN))


def _released(state: FaderState) -> FaderTransition:
    was_touched = state.touched
    updated = replace(
        state,
        touched=False,
        owner=FaderOwner.APPLICATION,
    )
    desired = updated.desired_value
    if not was_touched or desired is None:
        return FaderTransition(updated)
    if updated.observation_is_current:
        if desired == updated.observed_value:
            return FaderTransition(updated)
    elif desired == updated.last_commanded_value:
        return FaderTransition(updated)
    return FaderTransition(updated, desired)


class FaderStateController:
    """Store independent fader states and apply the ownership rules."""

    def __init__(self) -> None:
        self.reset()

    def state(self, fader: Fader) -> FaderState:
        return self._states[fader]

    def application_requested(self, fader: Fader, value: int) -> int | None:
        return self._apply(fader, _application_requested(self._states[fader], value))

    def physical_event(
        self,
        event: FaderPositionReported | FaderTouched | FaderReleased,
    ) -> int | None:
        state = self._states[event.fader]
        if isinstance(event, FaderPositionReported):
            transition = _position_reported(state, event.value)
        elif isinstance(event, FaderTouched):
            transition = _touched(state)
        else:
            transition = _released(state)
        return self._apply(event.fader, transition)

    def motor_command_sent(self, fader: Fader, value: int) -> None:
        self._states[fader] = replace(
            self._states[fader],
            last_commanded_value=value,
            observation_is_current=False,
        )

    def reset(self) -> None:
        self._states = {fader: FaderState() for fader in Fader}

    def _apply(self, fader: Fader, transition: FaderTransition) -> int | None:
        self._states[fader] = transition.state
        return transition.command_value
