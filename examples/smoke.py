#!/usr/bin/env python3
"""Interactive first-hour hardware smoke test.

Walks through the checks in docs/hardware.md in order: Standard MIDI mode,
Global MIDI Channel, ALSA Sequencer discovery, then a fader move, the PLAY
LED, an encoder ring, and a short receive loop. Each stage asks for a
yes/no confirmation of what was physically observed. Prints a pass/fail/skip
summary at the end.

This script is for a human at the controller. It is not a CI test.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from xtouch_compact import (
    Button,
    ButtonLedState,
    Encoder,
    EncoderRingDisplay,
    EncoderRingMode,
    Fader,
    SessionState,
    XTouchCompactError,
    XTouchCompactSession,
)

RESULTS: list[tuple[str, str]] = []


def record(stage: str, outcome: str) -> None:
    RESULTS.append((stage, outcome))


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(f"{prompt} [y/n] ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer y or n.")


def pause(prompt: str = "Press Enter to continue...") -> None:
    input(prompt)


def reset_surface(session: XTouchCompactSession) -> None:
    """Turn off every button LED and encoder ring.

    Earlier manual runs (button_leds.py, encoder_rings.py, ...) leave LEDs
    and rings lit on the physical device; there is no power-on reset between
    runs. Without this, a human can't tell which light the current step
    actually commanded.
    """
    for button in Button:
        if button in (Button.LAYER_A, Button.LAYER_B):
            continue  # layer indicators have no independent LED RX binding
        session.set_button_led(button, ButtonLedState.OFF)
    for encoder in Encoder:
        session.set_encoder_ring_value(encoder, EncoderRingDisplay.off())


def cleanup(session: XTouchCompactSession, primary_error: BaseException | None) -> None:
    """Attempt reset and close, preserving an earlier failure or interrupt.

    Expected library cleanup errors are reported. Unexpected errors and
    interrupts propagate after closure, unless a primary error already exists.
    """
    failures: list[tuple[str, BaseException]] = []
    try:
        if session.state is SessionState.READY:
            reset_surface(session)
    except BaseException as error:
        failures.append(("reset surface", error))
    finally:
        try:
            session.close()
        except BaseException as error:
            failures.append(("close session", error))

    for action, error in failures:
        print(f"Could not {action} during cleanup: {type(error).__name__}: {error}")
    if primary_error is None:
        for _, error in failures:
            if not isinstance(error, XTouchCompactError):
                raise error


def step_aconnect() -> None:
    print("\n== Step: aconnect ==")
    if shutil.which("aconnect") is None:
        print("aconnect not found on PATH; skipping this check.")
        print("See docs/hardware.md for ALSA Sequencer setup.")
        record("aconnect", "SKIP")
        return
    output = subprocess.run(
        ["aconnect", "-l"], capture_output=True, text=True, check=False
    ).stdout
    print(output)
    if "X-TOUCH COMPACT" in output:
        print("Found client 'X-TOUCH COMPACT'.")
        record("aconnect", "PASS")
    else:
        print(
            "Did not find a client named 'X-TOUCH COMPACT'. Check USB "
            "connection, Standard MIDI mode, and /dev/snd/seq "
            "(see docs/hardware.md)."
        )
        record("aconnect", "FAIL")


def step_fader(session: XTouchCompactSession) -> None:
    print("\n== Step: Fader ==")
    print("Commanding CHANNEL_1 fader to 0, then 127.")
    session.set_fader(Fader.CHANNEL_1, 0)
    pause("Press Enter once the fader has settled...")
    session.set_fader(Fader.CHANNEL_1, 127)
    if ask_yes_no("Did the CHANNEL_1 fader motor move to full?"):
        record("fader", "PASS")
    else:
        record("fader", "FAIL")


def step_play_led(session: XTouchCompactSession) -> None:
    print("\n== Step: PLAY LED ==")
    session.set_button_led(Button.PLAY, ButtonLedState.BLINK)
    if ask_yes_no("Is the PLAY button LED blinking?"):
        record("play_led", "PASS")
    else:
        record("play_led", "FAIL")
    session.set_button_led(Button.PLAY, ButtonLedState.OFF)


def step_encoder_ring(session: XTouchCompactSession) -> None:
    print("\n== Step: Encoder ring ==")
    session.set_encoder_ring_mode(Encoder.CHANNEL_1, EncoderRingMode.FAN)
    session.set_encoder_ring_value(Encoder.CHANNEL_1, EncoderRingDisplay.at(7))
    if ask_yes_no("Is encoder 1's ring lit in a fan pattern, mid-scale?"):
        record("encoder_ring", "PASS")
    else:
        record("encoder_ring", "FAIL")
    session.set_encoder_ring_value(Encoder.CHANNEL_1, EncoderRingDisplay.off())


def step_receive_loop(session: XTouchCompactSession) -> None:
    print("\n== Step: Receive loop ==")
    print(
        "Move CHANNEL_1 fader, turn encoder 1, and press PLAY. "
        "Decoded events print below. Press Ctrl-C when done."
    )
    seen: set[str] = set()
    try:
        while True:
            event = session.receive(timeout=0.5)
            if event is not None:
                print(event)
                seen.add(type(event).__name__)
    except KeyboardInterrupt:
        print()
    print(f"Distinct event types seen: {sorted(seen) or 'none'}")
    if ask_yes_no("Did moving the fader, encoder, and PLAY all produce events?"):
        record("receive_loop", "PASS")
    else:
        record("receive_loop", "FAIL")


def print_summary() -> int:
    print("\n== Summary ==")
    failed = False
    for stage, outcome in RESULTS:
        print(f"{outcome:<5} {stage}")
        if outcome == "FAIL":
            failed = True
    return 1 if failed else 0


def run(session: XTouchCompactSession) -> int:
    """Connect, initialize, run the checks, and clean up.

    Closure is attempted after every successful ``connect()``: on an
    ``initialize()`` failure, a failure or ``KeyboardInterrupt`` during a
    step, and a failure during the final surface reset. A reset failure
    (best-effort; hardware may already be gone) never prevents ``close()``,
    and a ``close()`` failure never hides a primary exception already
    propagating from a step. ``connect()`` failing outright needs no
    separate closure here: the session already tears itself down before
    raising.
    """
    try:
        session.connect()
    except XTouchCompactError as error:
        print(f"Could not connect: {error}")
        record("connect", "FAIL")
        return print_summary()

    primary_error: BaseException | None = None
    try:
        try:
            session.initialize()
        except XTouchCompactError as error:
            primary_error = error
            print(f"Could not initialize: {error}")
            record("connect", "FAIL")
            return print_summary()

        print("\nTurning off all button LEDs and encoder rings for a clean start...")
        reset_surface(session)
        step_fader(session)
        step_play_led(session)
        step_encoder_ring(session)
        step_receive_loop(session)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup(session, primary_error)

    return print_summary()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        type=int,
        required=True,
        metavar="1-16",
        help="X-TOUCH Global MIDI Channel",
    )
    args = parser.parse_args()
    if not 1 <= args.channel <= 16:
        parser.error("channel must be in the range 1 through 16")

    print("X-TOUCH COMPACT hardware smoke test")
    print("Confirm the device is in Standard MIDI mode (not Mackie Control)")
    print(f"and its Global MIDI Channel is set to {args.channel}.")
    if not ask_yes_no("Ready to continue?"):
        print("Aborted.")
        return 1

    step_aconnect()

    session = XTouchCompactSession.open(global_midi_channel=args.channel)
    return run(session)


if __name__ == "__main__":
    sys.exit(main())
