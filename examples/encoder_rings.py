#!/usr/bin/env python3
"""Set encoder 1 to fan mode with a mid-scale display, then wait for Enter."""

from __future__ import annotations

import argparse

from xtouch_compact import (
    Encoder,
    EncoderRingDisplay,
    EncoderRingMode,
    XTouchCompactSession,
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
    args = parser.parse_args()
    if not 1 <= args.channel <= 16:
        parser.error("channel must be in the range 1 through 16")

    with XTouchCompactSession.open(global_midi_channel=args.channel) as session:
        session.set_encoder_ring_mode(Encoder.CHANNEL_1, EncoderRingMode.FAN)
        session.set_encoder_ring_value(Encoder.CHANNEL_1, EncoderRingDisplay.at(7))
        input("Encoder 1 ring commanded. Press Enter to close.")


if __name__ == "__main__":
    main()
