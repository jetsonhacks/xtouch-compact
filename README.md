# xtouch-compact

Python library for the Behringer X-TOUCH COMPACT on Linux ALSA Sequencer, in
Standard MIDI mode.

The library treats the controller as a bidirectional physical control surface.
Application code uses names such as `Fader.CHANNEL_1` and `Button.PLAY`. It
does not need MIDI note numbers, controller numbers, or ALSA client numbers.

## Requirements

- Linux with ALSA Sequencer available (`/dev/snd/seq`)
- Python 3.10 or later
- An X-TOUCH COMPACT in **Standard MIDI** mode, not Mackie Control
- The device Global MIDI Channel, in the user-facing range 1–16

Python dependencies, installed by `uv sync` from `pyproject.toml`:

- `alsa-midi` 1.0.4 or later (ALSA Sequencer client)
- `PyYAML` 6.0.2 or later (device map loader)

This project does not include a kernel, kernel modules, or an X-TOUCH device
driver. The controller is USB class-compliant MIDI. Some Linux kernels,
including stock NVIDIA Jetson kernels, omit ALSA Sequencer. This repository
does not provide or support a kernel rebuild. See
[docs/hardware.md](docs/hardware.md).

## Install

Clone the repository and sync with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/jetsonhacks/xtouch-compact.git
cd xtouch-compact
uv sync
```

That creates `.venv`, installs `alsa-midi` and `PyYAML`, and installs this
package in editable mode. The lockfile pins the exact versions. Dev tools
(`pytest`, `ruff`) are included.

```bash
uv run pytest
uv run ruff check .
```

From another uv project, add this repository as a dependency:

```bash
uv add git+https://github.com/jetsonhacks/xtouch-compact
```

## Quick Start

Put the device in Standard MIDI mode. Set `global_midi_channel` to the
channel configured on the controller (factory default is often 1; many
setups use 2).

```python
from xtouch_compact import (
    AlsaSequencerTransport,
    Button,
    ButtonLedState,
    Fader,
    XTouchCompactSession,
    load_device_specification,
)

transport = AlsaSequencerTransport()
specification = load_device_specification()
session = XTouchCompactSession(
    transport,
    specification,
    global_midi_channel=2,
)

with session:
    session.set_fader(Fader.CHANNEL_1, 96)
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    event = session.receive(timeout=1.0)
    if event is not None:
        print(event)
```

`with session:` connects the ALSA endpoint, sends the startup layer
assertion, and closes the session on exit. `connect()` and `initialize()`
remain available as separate steps.

Import from the `xtouch_compact` package root. See
[docs/usage.md](docs/usage.md) for connection, input, and feedback, and
[docs/api.md](docs/api.md) for the supported types and methods.

Examples in `examples/` need a connected controller and `--channel` set to
the Global MIDI Channel:

```bash
uv run python examples/monitor_controls.py --channel 2
uv run python examples/move_faders.py --channel 2 --value 96
uv run python examples/button_leds.py --channel 2
uv run python examples/encoder_rings.py --channel 2
```

## Scope

The library covers faders, encoders, assignable buttons, Layer A/B
selection, and the foot-switch status LED. Expression-pedal and foot-switch
**input** is mapped in the device description but is not published as typed
events. Mackie Control, DAW protocols, and robot-specific bindings are out
of scope.

## Changelog

Release history is in [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).
