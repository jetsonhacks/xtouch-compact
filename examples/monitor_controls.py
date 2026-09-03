#!/usr/bin/env python3
"""Print decoded physical events until interrupted."""

from __future__ import annotations

import argparse

from xtouch_compact import XTouchCompactSession


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
        print("Listening. Press Ctrl-C to stop.")
        try:
            while True:
                event = session.receive(timeout=0.5)
                if event is not None:
                    print(event)
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
