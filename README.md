# xtouch-compact

[![CI](https://github.com/jetsonhacks/xtouch-compact/actions/workflows/ci.yml/badge.svg)](https://github.com/jetsonhacks/xtouch-compact/actions/workflows/ci.yml)

Python library for the Behringer X-TOUCH COMPACT on Linux ALSA Sequencer.
Use its faders, encoders, and buttons as an input and feedback panel for
robotics and other interactive applications.

The synchronous API provides typed input events and commands for motorized
faders, button LEDs, encoder LED rings, layer selection, and the foot-switch
status LED. Application code uses names such as `Fader.CHANNEL_1` and
`Button.PLAY`; the library handles MIDI addresses and ALSA discovery.
Control bindings and device-loss policy belong to the application.

## Requirements

- Linux with ALSA Sequencer available (`/dev/snd/seq`)
- Python 3.10 or later
- An X-TOUCH COMPACT in **Standard MIDI** mode with its **factory mappings**
- The device's configured Global MIDI Channel (1–16)

Mackie Control and mappings changed with X-TOUCH Editor are unsupported.
Foot-control input is available only as raw messages, not typed events.
For host setup and device limitations, see [Hardware](docs/hardware.md).

## Install

Clone and install with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/jetsonhacks/xtouch-compact.git
cd xtouch-compact
uv sync
```

This installs the library, its `alsa-midi` dependency, and development tools
into `.venv`, using the versions in the lockfile.

To use the library from another uv project:

```bash
uv add git+https://github.com/jetsonhacks/xtouch-compact
```

## Quick Start

Set `global_midi_channel` to the channel configured on your controller;
`2` below is an example, not a detected or assumed device setting.

```python
from xtouch_compact import Button, ButtonLedState, Fader, XTouchCompactSession

with XTouchCompactSession.open(global_midi_channel=2) as session:
    session.set_fader(Fader.CHANNEL_1, 96)
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    event = session.receive(timeout=1.0)
    if event is not None:
        print(event)
```

The context manager connects, asserts the startup layer, and closes on exit.
For continuous operation, service input regularly so the session can process
touch and other physical changes; see [Usage](docs/usage.md).

## Try the Hardware

Run the interactive smoke test first. Use the same Global MIDI Channel as
the controller:

```bash
uv run python examples/smoke.py --channel 2
uv run python examples/demo.py --channel 2
```

The smoke test checks input and feedback with operator confirmations. The
demo cycles LEDs and rings, then sweeps the faders. See the
[example scripts](examples/README.md) for individual controls.

## Documentation

| Document | Contents |
|---|---|
| [Usage](docs/usage.md) | Sessions, input, feedback, fader ownership, and recovery |
| [API](docs/api.md) | Supported types, methods, state snapshots, and errors |
| [Hardware](docs/hardware.md) | ALSA setup, device configuration, and bring-up |
| [MIDI map](docs/xtouch-compact-midi.md) | Manufacturer-derived protocol reference |
| [Hardware observations](docs/hardware-observations.md) | Measurements, deviations from the manual, and implementation decisions |
| [Historical specification](specs/README.md) | Machine-readable characterization evidence |
| [Development](docs/development.md) | Checks, test responsibilities, and documentation maintenance |

Release history: [CHANGELOG.md](CHANGELOG.md). License: [MIT](LICENSE).
