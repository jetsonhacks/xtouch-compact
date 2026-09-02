"""Semantic values for host-controlled X-TOUCH feedback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ButtonLedState(Enum):
    OFF = "off"
    ON = "on"
    BLINK = "blink"


class EncoderRingMode(Enum):
    SINGLE = "single"
    PAN = "pan"
    FAN = "fan"
    SPREAD = "spread"
    TRIM = "trim"


class EncoderRingDisplayKind(Enum):
    OFF = "all_off"
    POSITION = "position"
    BLINKING_POSITION = "blinking_position"
    ALL_ON = "all_on"
    ALL_BLINKING = "all_blinking"


@dataclass(frozen=True, slots=True)
class EncoderRingDisplay:
    """One semantic encoder-ring display command."""

    kind: EncoderRingDisplayKind
    position: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EncoderRingDisplayKind):
            raise TypeError("kind must be an EncoderRingDisplayKind")
        positioned = self.kind in {
            EncoderRingDisplayKind.POSITION,
            EncoderRingDisplayKind.BLINKING_POSITION,
        }
        if positioned:
            if isinstance(self.position, bool) or not isinstance(self.position, int):
                raise TypeError("position must be an integer")
        elif self.position is not None:
            raise ValueError(f"{self.kind.value} does not accept a position")

    @classmethod
    def off(cls) -> EncoderRingDisplay:
        return cls(EncoderRingDisplayKind.OFF)

    @classmethod
    def at(cls, position: int) -> EncoderRingDisplay:
        return cls(EncoderRingDisplayKind.POSITION, position)

    @classmethod
    def blinking_at(cls, position: int) -> EncoderRingDisplay:
        return cls(EncoderRingDisplayKind.BLINKING_POSITION, position)

    @classmethod
    def all_on(cls) -> EncoderRingDisplay:
        return cls(EncoderRingDisplayKind.ALL_ON)

    @classmethod
    def all_blinking(cls) -> EncoderRingDisplay:
        return cls(EncoderRingDisplayKind.ALL_BLINKING)


class StatusLedState(Enum):
    OFF = "off"
    ON = "on"
