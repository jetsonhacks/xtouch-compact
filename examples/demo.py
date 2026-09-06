#!/usr/bin/env python3
"""Non-interactive visual self-test: lamp-test the LEDs, then wave the faders.

Runs straight through with no per-step confirmation, unlike smoke.py. Watch
the device while it runs:

1. Every assignable button LED (excluding the device-owned Layer A/B indicators)
   cycles off, on, blink, off.
2. Every encoder ring cycles on, off.
3. All nine faders move in a traveling sine wave for a few seconds, then
   settle at mid-scale.

If everything lights and moves as described, the box, the channel, and the
kernel are working end to end.
"""

from __future__ import annotations

import argparse
import math
import time

from xtouch_compact import (
    Button,
    ButtonLedState,
    Encoder,
    EncoderRingDisplay,
    Fader,
    XTouchCompactError,
    XTouchCompactSession,
)

_LAYER_BUTTONS = (Button.LAYER_A, Button.LAYER_B)
NON_LAYER_BUTTONS = tuple(b for b in Button if b not in _LAYER_BUTTONS)
FADERS = tuple(Fader)


def lamp_test_buttons(session: XTouchCompactSession, hold_seconds: float) -> None:
    print("Button LEDs: off, on, blink, off...")
    for state in (
        ButtonLedState.OFF,
        ButtonLedState.ON,
        ButtonLedState.BLINK,
        ButtonLedState.OFF,
    ):
        for button in NON_LAYER_BUTTONS:
            session.set_button_led(button, state)
        time.sleep(hold_seconds)


def lamp_test_rings(session: XTouchCompactSession, hold_seconds: float) -> None:
    print("Encoder rings: on, off...")
    for display in (EncoderRingDisplay.all_on(), EncoderRingDisplay.off()):
        for encoder in Encoder:
            session.set_encoder_ring_value(encoder, display)
        time.sleep(hold_seconds)


def sine_wave_faders(session: XTouchCompactSession, duration: float) -> None:
    print(f"Faders: sine wave for {duration:.0f} seconds...")
    period = 2.0
    update_interval = 0.05
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        if elapsed >= duration:
            break
        for index, fader in enumerate(FADERS):
            phase = 2 * math.pi * index / len(FADERS)
            angle = 2 * math.pi * elapsed / period + phase
            value = round(63.5 + 63.5 * math.sin(angle))
            session.set_fader(fader, value)
        time.sleep(update_interval)
    print("Faders: settling at mid-scale...")
    for fader in FADERS:
        session.set_fader(fader, 64)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        type=int,
        required=True,
        metavar="1-16",
        help="X-TOUCH Global MIDI Channel",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="how long to hold each LED lamp-test stage (default: 2.0)",
    )
    parser.add_argument(
        "--sine-seconds",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="how long to run the fader sine wave (default: 5.0)",
    )
    args = parser.parse_args()
    if not 1 <= args.channel <= 16:
        parser.error("channel must be in the range 1 through 16")
    if args.hold_seconds <= 0:
        parser.error("--hold-seconds must be positive")
    if args.sine_seconds <= 0:
        parser.error("--sine-seconds must be positive")

    try:
        with XTouchCompactSession.open(global_midi_channel=args.channel) as session:
            lamp_test_buttons(session, args.hold_seconds)
            lamp_test_rings(session, args.hold_seconds)
            sine_wave_faders(session, args.sine_seconds)
    except XTouchCompactError as error:
        print(f"Demo failed: {error}")
        return 1

    print("Demo complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
