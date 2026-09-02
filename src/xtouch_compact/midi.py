"""Small, ALSA-independent MIDI message values used by the device model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


def _validate_range(name: str, value: int, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be from {minimum} through {maximum}")


@dataclass(frozen=True, slots=True)
class NoteOn:
    """One Note On message with a user-facing MIDI channel."""

    midi_channel: int
    note_number: int
    velocity: int

    def __post_init__(self) -> None:
        _validate_range("midi_channel", self.midi_channel, 1, 16)
        _validate_range("note_number", self.note_number, 0, 127)
        _validate_range("velocity", self.velocity, 0, 127)


@dataclass(frozen=True, slots=True)
class NoteOff:
    """One Note Off message with a user-facing MIDI channel."""

    midi_channel: int
    note_number: int
    velocity: int

    def __post_init__(self) -> None:
        _validate_range("midi_channel", self.midi_channel, 1, 16)
        _validate_range("note_number", self.note_number, 0, 127)
        _validate_range("velocity", self.velocity, 0, 127)


@dataclass(frozen=True, slots=True)
class ControlChange:
    """One Control Change message with a user-facing MIDI channel."""

    midi_channel: int
    control_number: int
    value: int

    def __post_init__(self) -> None:
        _validate_range("midi_channel", self.midi_channel, 1, 16)
        _validate_range("control_number", self.control_number, 0, 127)
        _validate_range("value", self.value, 0, 127)


@dataclass(frozen=True, slots=True)
class ProgramChange:
    """One Program Change message with a user-facing MIDI channel."""

    midi_channel: int
    program_number: int

    def __post_init__(self) -> None:
        _validate_range("midi_channel", self.midi_channel, 1, 16)
        _validate_range("program_number", self.program_number, 0, 127)


RawMidiMessage: TypeAlias = NoteOn | NoteOff | ControlChange | ProgramChange
