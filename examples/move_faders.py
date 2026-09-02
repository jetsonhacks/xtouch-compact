#!/usr/bin/env python3
"""Move every motorized fader to a position, then wait for Enter."""

from __future__ import annotations

import argparse

from xtouch_compact import (
    AlsaSequencerTransport,
    Fader,
    XTouchCompactSession,
    load_device_specification,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        type=int,
        required=True,
        metavar="1-16",
        help="X-TOUCH Global MIDI Channel",
    )
    parser.add_argument(
        "--value",
        type=int,
        default=64,
        metavar="0-127",
        help="Fader position (default: 64)",
    )
    args = parser.parse_args()
    if not 1 <= args.channel <= 16:
        parser.error("channel must be in the range 1 through 16")
    if not 0 <= args.value <= 127:
        parser.error("value must be in the range 0 through 127")

    session = XTouchCompactSession(
        AlsaSequencerTransport(),
        load_device_specification(),
        global_midi_channel=args.channel,
    )
    with session:
        for fader in Fader:
            session.set_fader(fader, args.value)
        input("Faders commanded. Press Enter to close.")


if __name__ == "__main__":
    main()
