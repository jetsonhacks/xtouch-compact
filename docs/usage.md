# Usage

This page describes the normal application path: construct a session, connect,
initialize, send feedback, and receive physical events.

## Device Setup

1. Connect the X-TOUCH COMPACT over USB.
2. Put the unit in Standard MIDI mode. Mackie Control is not supported.
3. Note the Global MIDI Channel shown on the device (1–16). Host-to-device
   commands use this channel. Do not infer it from incoming fader or button
   messages; those often use a different transmit channel.

Confirm that Linux exposes the sequencer:

```bash
ls -l /dev/snd/seq
aconnect -l
```

The controller should appear as client name `X-TOUCH COMPACT` with a
bidirectional port such as `X-TOUCH COMPACT MIDI 1`. If `/dev/snd/seq` is
missing, see [hardware.md](hardware.md).

## Construct a Session

```python
from xtouch_compact import Layer, XTouchCompactSession

session = XTouchCompactSession.open(
    global_midi_channel=2,
    startup_layer=Layer.A,
)
```

`open()` does not open ALSA and does not require the device to be attached.
`global_midi_channel` is required and must be 1–16. `startup_layer` defaults
to Layer A. Invalid values raise `SessionConfigurationError` immediately.

The default transport discovers the endpoint by client name
`X-TOUCH COMPACT`. If several matching ports exist, pass `port_name` with a
unique fragment of the ALSA port name. Do not hard-code ALSA client or port
numbers; those identities change across reconnects.

The explicit constructor remains available when the application already
has a transport or a loaded specification:

```python
from xtouch_compact import (
    AlsaSequencerTransport,
    XTouchCompactSession,
    load_device_specification,
)

session = XTouchCompactSession(
    AlsaSequencerTransport(),
    load_device_specification(),
    global_midi_channel=2,
)
```

## Connect and Initialize

```python
session.connect()
session.initialize()
```

Or:

```python
with session:
    ...
```

`connect()` opens the ALSA client, local port, and subscriptions.
`initialize()` sends a Program Change that selects the desired startup layer
on the Global MIDI Channel, then enters `READY`. Semantic input and output
require `READY`.

The Layer A/B lights on the device do not prove that initialization
succeeded. The session records a completed transport send, not a hardware
acknowledgement.

## Receive Physical Events

```python
from xtouch_compact import ButtonPressed, FaderTouched

event = session.receive(timeout=0.25)
if isinstance(event, ButtonPressed):
    print(event.button, event.layer)
```

`receive()` waits for one decoded event, or until `timeout` seconds
elapse. `timeout=None` waits indefinitely. `timeout=0` polls and returns
immediately. A positive value waits up to that many seconds. The call is
synchronous. There is no callback API, background thread, or asyncio
integration.

`receive()` returns `None` on timeout and also when a MIDI message has no
typed physical event (unknown address, or foot-control input). Use
`receive_input()` when diagnostics need the raw message:

```python
received = session.receive_input(timeout=0.25)
if received is not None:
    print(received.message, received.physical_event)
```

Typed events cover fader position, fader touch and release, encoder turn and
push, and button press and release. Each event carries the physical identity,
the layer inferred from the factory transmit map, and the raw MIDI message.

## Send Feedback

All setters require `READY`. Values are semantic; the session encodes them
through the device map.

```python
from xtouch_compact import (
    Button,
    ButtonLedState,
    Encoder,
    EncoderRingDisplay,
    EncoderRingMode,
    Fader,
    Layer,
    StatusLedState,
)

session.set_fader(Fader.CHANNEL_1, 96)
session.set_button_led(Button.PLAY, ButtonLedState.ON)
session.set_encoder_ring_mode(Encoder.CHANNEL_1, EncoderRingMode.FAN)
session.set_encoder_ring_value(Encoder.CHANNEL_1, EncoderRingDisplay.at(8))
session.select_layer(Layer.B)
session.set_foot_switch_led(StatusLedState.ON)
```

Fader positions and encoder display positions use the MIDI 7-bit range 0–127.
Button LEDs accept `OFF`, `ON`, and `BLINK`. Encoder ring modes are `SINGLE`,
`PAN`, `FAN`, `SPREAD`, and `TRIM`.

Repeated setter calls with the same semantic value are suppressed, except
`select_layer()`, which always transmits. Last-sent state is command history.
The device does not acknowledge that the LED, ring, or motor actually moved.

`sync_feedback()` resends desired button, ring, layer, and foot-switch LED
state that differs from last-sent state. `invalidate_feedback_state()` marks
last-sent values unknown while keeping desired values, so the next sync or
setter can reassert them.

## Fader Ownership

Each motorized fader has an independent snapshot from `fader_state(fader)`:
desired value, last observed value, touch, owner, and last commanded motor
value.

Touch gives that fader to the human. `set_fader()` still updates the desired
value, but the session does not send a motor command while the fader is
touched. On release, if the desired value is set and differs from the
observed position, the session sends the desired value once. Other faders are
unaffected.

Initialization does not move faders to discover their positions. Unknown
desired and observed values stay unset until the application or the device
provides them.

## Reconnect

`reconnect()` is an explicit, synchronous transaction. It closes the previous
connection, discovers the device by name again, asserts the currently desired
layer, and calls `sync_feedback()`. It resets all fader snapshots and does
not restore motor positions.

A live ALSA send or receive failure raises `TransportConnectionError`, moves
the session to `DISCONNECTED`, and leaves desired surface feedback in place
for a later `reconnect()`. A receive timeout is not proof that the device is
gone. Call `reconnect()` after you know the controller has returned.

## Close

`close()` is idempotent. A closed session may be connected again with
`connect()` then `initialize()`. Context-manager exit always closes.
