# xtouch-compact

[![CI](https://github.com/jetsonhacks/xtouch-compact/actions/workflows/ci.yml/badge.svg)](https://github.com/jetsonhacks/xtouch-compact/actions/workflows/ci.yml)

Python library for the Behringer X-TOUCH COMPACT on Linux ALSA Sequencer, in
Standard MIDI mode.

The library treats the controller as a bidirectional physical control surface.
Application code uses names such as `Fader.CHANNEL_1` and `Button.PLAY`. It
does not need MIDI note numbers, controller numbers, or ALSA client numbers.

## What This Library Is For

`xtouch-compact` is a control-surface library for robotics and other
interactive control applications that use the X-TOUCH COMPACT as a physical
input and feedback panel — for example, jogging a joint from a fader,
tele-operating a system with the encoders, or using the transport buttons and
LEDs as application-level controls.

Within that role, the library:

- decodes physical control input (fader moves and touch, encoder turns and
  pushes, button presses) into typed events;
- drives the controller's supported feedback: motorized faders, button LEDs,
  encoder LED rings, and the foot-switch status LED;
- keeps its own record of that feedback state coherent with what it last sent
  and, for faders, with human touch; and
- exposes that behavior through a synchronous, in-process session API —
  `connect()` / `initialize()` / `receive()` / the `set_*` methods — with no
  callback, thread, or asyncio layer of its own.

It does not control a robot, run a motion planner, close a servo loop, or
provide any safety function. What a fader, encoder, or button *means* to a
robot or application — a joint, an axis, a playback action — is entirely
application code; see [Application-Owned Bindings](#application-owned-bindings)
below.

## Requirements

- Linux with ALSA Sequencer available (`/dev/snd/seq`)
- Python 3.10 or later
- An X-TOUCH COMPACT in **Standard MIDI** mode, not Mackie Control
- The device Global MIDI Channel, in the user-facing range 1–16
- The controller's **factory** Standard MIDI mapping. Mappings changed with
  the X-TOUCH Editor are outside this library's supported contract.

Python dependencies, installed by `uv sync` from `pyproject.toml`:

- `alsa-midi` 1.0.4 or later (ALSA Sequencer client)

The library supports exactly one fixed factory profile: a typed Python table
(`xtouch_compact.device_map`) built into the package. There is no runtime
YAML dependency, device-specification file, or injection point, and no
support for arbitrary or user-remapped MIDI layouts.

"Out of the box" here means the library assumes, rather than detects or
repairs, that this contract already holds: the device in Standard MIDI mode,
its Global MIDI Channel configured and passed to the library, a Linux host
with ALSA Sequencer available, and the factory mapping intact. If any of
those are wrong, most commands fail silently on the device side rather than
raising an error in this library — see
[docs/hardware.md](docs/hardware.md#first-hour-smoke-test) for the smoke
test that checks them before you build on top.

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

That creates `.venv`, installs `alsa-midi`, and installs this package in
editable mode. The lockfile pins the exact versions. Dev tools (`pytest`,
`ruff`, `mypy`) are included.

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

GitHub Actions runs those same checks on every push and pull request, on
Python 3.10 through 3.13. The unit suite does not need a physical controller
or `/dev/snd/seq`. Hardware examples in `examples/` remain manual.

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
    Button,
    ButtonLedState,
    Fader,
    XTouchCompactSession,
)

with XTouchCompactSession.open(global_midi_channel=2) as session:
    session.set_fader(Fader.CHANNEL_1, 96)
    session.set_button_led(Button.PLAY, ButtonLedState.ON)
    event = session.receive(timeout=1.0)
    if event is not None:
        print(event)
```

`open()` builds the ALSA transport and device map. The `with` block
connects, sends the startup layer assertion, and closes on exit.
`connect()` and `initialize()` remain available as separate steps.

Import from the `xtouch_compact` package root. See
[docs/usage.md](docs/usage.md) for connection, input, and feedback, and
[docs/api.md](docs/api.md) for the supported types and methods.

With a connected controller, run the interactive smoke test, then the
visual demo. `--channel` is the Global MIDI Channel shown on the device:

```bash
uv run python examples/smoke.py --channel 2
uv run python examples/demo.py --channel 2
```

`examples/smoke.py` is the first-hour hardware check: Standard MIDI mode,
channel, `aconnect`, fader, PLAY LED, encoder ring, and a receive loop,
each with a pass/fail confirmation. See
[docs/hardware.md](docs/hardware.md#first-hour-smoke-test).

`examples/demo.py` lamp-tests every button LED, cycles every encoder ring,
then sweeps the nine faders through a traveling sine wave. It is not
interactive; watch the device while it runs.

The rest of `examples/` is documented in
[examples/README.md](examples/README.md).

The extracted Standard MIDI map is
[docs/xtouch-compact-midi.md](docs/xtouch-compact-midi.md). Dated hardware
measurements that the session policies follow are in
[docs/hardware-observations.md](docs/hardware-observations.md).

## Fader Ownership

Each motorized fader is either application-owned or human-owned:

- While a fader is untouched, `set_fader()` commands the motor to that
  position — the application owns it.
- Touching the fader hands it to the human. `set_fader()` still records the
  application's desired value, but the library does not fight the touch with
  motor motion while it is held.
- On release, the library reconciles the motor toward the application's
  current desired value, according to `fader_state()`'s desired/observed/
  last-commanded model — not by assuming the motor reached any prior
  command.

This is a conceptual summary. The full state model, including what
"observed" does and does not mean, is in
[docs/usage.md#fader-ownership](docs/usage.md#fader-ownership) and
[docs/api.md](docs/api.md#state-inspection).

## Feedback and State

The library keeps a coherent record of the feedback it has sent — desired
button LED, encoder ring, layer, and foot-switch state, each against what
was last actually sent — and resends what differs with `sync_feedback()`.
For faders it additionally tracks the human/application ownership above.
Sent state is command history, not hardware acknowledgement: the controller
does not confirm that an LED, ring, or motor actually changed. See
[docs/usage.md](docs/usage.md) and [docs/api.md](docs/api.md#state-inspection)
for the full model.

## Application-Owned Bindings

The library provides the physical control and feedback abstraction; it has
no opinion on what a control *means*. Deciding that, for example,
`Fader.CHANNEL_1` drives a robot joint, an encoder drives body yaw,
`Button.PLAY` starts a motion sequence, or an LED reflects application
state, is application code, not something this library configures or ships.
This repository contains no robot-specific bindings.

The library also does not provide a safety-rated enable, emergency stop, or
dead-man control, and it does not guarantee device presence or real-time
timing. A `receive()` timeout means no supported event arrived in that
interval — it is not proof the device disconnected. Device-loss policy and
any robot-safety behavior gated on the controller are the application's
responsibility; see [docs/usage.md#reconnect](docs/usage.md#reconnect).

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
