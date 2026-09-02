"""Typed physical-control events emitted by the inbound decoder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .controls import Button, Encoder, Fader, Layer
from .midi import ControlChange, NoteOff, NoteOn


@dataclass(frozen=True, slots=True)
class ButtonPressed:
    button: Button
    layer: Layer
    raw: NoteOn


@dataclass(frozen=True, slots=True)
class ButtonReleased:
    button: Button
    layer: Layer
    raw: NoteOff


@dataclass(frozen=True, slots=True)
class FaderPositionReported:
    fader: Fader
    layer: Layer
    value: int
    raw: ControlChange


@dataclass(frozen=True, slots=True)
class FaderTouched:
    fader: Fader
    layer: Layer
    raw: ControlChange


@dataclass(frozen=True, slots=True)
class FaderReleased:
    fader: Fader
    layer: Layer
    raw: ControlChange


@dataclass(frozen=True, slots=True)
class EncoderPositionReported:
    encoder: Encoder
    layer: Layer
    value: int
    raw: ControlChange


@dataclass(frozen=True, slots=True)
class EncoderPressed:
    encoder: Encoder
    layer: Layer
    raw: NoteOn


@dataclass(frozen=True, slots=True)
class EncoderReleased:
    encoder: Encoder
    layer: Layer
    raw: NoteOff


PhysicalControlEvent: TypeAlias = (
    ButtonPressed
    | ButtonReleased
    | FaderPositionReported
    | FaderTouched
    | FaderReleased
    | EncoderPositionReported
    | EncoderPressed
    | EncoderReleased
)
