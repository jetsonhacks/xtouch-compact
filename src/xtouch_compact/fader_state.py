"""State and ownership policy for the nine motorized faders."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol

from .controls import Fader
from .events import FaderPositionReported, FaderReleased, FaderTouched


class FaderOwner(Enum):
    """The party currently allowed to move one motorized fader."""

    APPLICATION = "application"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class FaderState:
    """Read-only snapshot of application and device state for one fader."""

    desired_value: int | None = None
    observed_value: int | None = None
    touched: bool = False
    owner: FaderOwner = FaderOwner.APPLICATION
    last_commanded_value: int | None = None


@dataclass(frozen=True, slots=True)
class FaderTransition:
    """One state transition and its optional motor-command action."""

    state: FaderState
    command_value: int | None = None


class DefaultFaderOwnershipPolicy:
    """Give touched faders to the human and reconcile them on release."""

    def application_requested(self, state: FaderState, value: int) -> FaderTransition:
        updated = replace(state, desired_value=value)
        if state.owner is FaderOwner.HUMAN:
            return FaderTransition(updated)
        if state.observed_value == value or state.last_commanded_value == value:
            return FaderTransition(updated)
        return FaderTransition(updated, value)

    def position_reported(self, state: FaderState, value: int) -> FaderTransition:
        return FaderTransition(replace(state, observed_value=value))

    def touched(self, state: FaderState) -> FaderTransition:
        return FaderTransition(replace(state, touched=True, owner=FaderOwner.HUMAN))

    def released(self, state: FaderState) -> FaderTransition:
        was_touched = state.touched
        updated = replace(
            state,
            touched=False,
            owner=FaderOwner.APPLICATION,
        )
        desired = updated.desired_value
        if not was_touched or desired is None or desired == updated.observed_value:
            return FaderTransition(updated)
        return FaderTransition(updated, desired)


class FaderOwnershipPolicy(Protocol):
    """Transition contract used by the fader state controller."""

    def application_requested(
        self, state: FaderState, value: int
    ) -> FaderTransition: ...

    def position_reported(self, state: FaderState, value: int) -> FaderTransition: ...

    def touched(self, state: FaderState) -> FaderTransition: ...

    def released(self, state: FaderState) -> FaderTransition: ...


class FaderStateController:
    """Store independent fader states and apply one ownership policy."""

    def __init__(self, policy: FaderOwnershipPolicy | None = None) -> None:
        self._policy = DefaultFaderOwnershipPolicy() if policy is None else policy
        self.reset()

    def state(self, fader: Fader) -> FaderState:
        return self._states[fader]

    def application_requested(self, fader: Fader, value: int) -> int | None:
        return self._apply(
            fader, self._policy.application_requested(self._states[fader], value)
        )

    def physical_event(
        self,
        event: FaderPositionReported | FaderTouched | FaderReleased,
    ) -> int | None:
        state = self._states[event.fader]
        if isinstance(event, FaderPositionReported):
            transition = self._policy.position_reported(state, event.value)
        elif isinstance(event, FaderTouched):
            transition = self._policy.touched(state)
        else:
            transition = self._policy.released(state)
        return self._apply(event.fader, transition)

    def motor_command_sent(self, fader: Fader, value: int) -> None:
        self._states[fader] = replace(self._states[fader], last_commanded_value=value)

    def reset(self) -> None:
        self._states = {fader: FaderState() for fader in Fader}

    def _apply(self, fader: Fader, transition: FaderTransition) -> int | None:
        self._states[fader] = transition.state
        return transition.command_value
