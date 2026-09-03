# Examples

These scripts need a connected X-TOUCH COMPACT in **Standard MIDI** mode
and `--channel` set to the device Global MIDI Channel (1–16). They are
manual hardware tools, not CI tests.

`--channel` has no default. It must match the number shown on the
controller. A wrong channel sends feedback the device is not listening
for; the device does not error, so the failure looks like a dead LED or
motor. See [docs/hardware.md](../docs/hardware.md).

Run from the repository root after `uv sync`:

```bash
uv run python examples/smoke.py --channel 2
uv run python examples/demo.py --channel 2
```

## smoke.py

Interactive first-hour smoke test. Walks through Standard MIDI mode, the
channel, `aconnect`, a fader move, the PLAY LED, an encoder ring, and a
receive loop. Each stage asks for a yes/no confirmation and prints a
pass/fail/skip summary.

Use this before writing application code. Details:
[docs/hardware.md](../docs/hardware.md#first-hour-smoke-test).

## demo.py

Non-interactive visual self-test. Watch the device; there are no
confirmation prompts.

1. Every assignable button LED cycles off, on, blink, off.
2. Every encoder ring cycles on, then off.
3. All nine faders run a traveling sine wave, then settle at mid-scale.

Optional timing:

```bash
uv run python examples/demo.py --channel 2 --hold-seconds 2 --sine-seconds 5
```

## Other scripts

Narrower one-feature examples, useful once smoke or demo has already
proved the box:

| Script | What it does |
|---|---|
| `monitor_controls.py` | Print decoded physical events until Ctrl-C |
| `move_faders.py` | Move every motorized fader to `--value` (default 64) |
| `button_leds.py` | Light PLAY, blink STOP, wait for Enter |
| `encoder_rings.py` | Set encoder 1 to fan mode at mid-scale, wait for Enter |

```bash
uv run python examples/monitor_controls.py --channel 2
uv run python examples/move_faders.py --channel 2 --value 96
uv run python examples/button_leds.py --channel 2
uv run python examples/encoder_rings.py --channel 2
```

LEDs and rings stay as last commanded until another script or
`smoke.py` turns them off. There is no power-on reset between runs.
