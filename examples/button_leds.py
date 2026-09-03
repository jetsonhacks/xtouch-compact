#!/usr/bin/env python3
"""Light PLAY, blink STOP, then wait for Enter."""

from __future__ import annotations

import argparse

from xtouch_compact import Button, ButtonLedState, XTouchCompactSession


def main() -> None:
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

    with XTouchCompactSession.open(global_midi_channel=args.channel) as session:
        session.set_button_led(Button.PLAY, ButtonLedState.ON)
        session.set_button_led(Button.STOP, ButtonLedState.BLINK)
        input("LEDs commanded. Press Enter to close.")


if __name__ == "__main__":
    main()
