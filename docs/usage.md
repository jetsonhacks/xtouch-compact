# Usage

This page describes application use of the synchronous session API. Start with
the [README quick start](../README.md#quick-start) and the
[hardware smoke test](hardware.md#first-hour-smoke-test).

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
has a transport:

```python
from xtouch_compact import AlsaSequencerTransport, XTouchCompactSession

session = XTouchCompactSession(
    AlsaSequencerTransport(),
    global_midi_channel=2,
)
```

There is no device-specification argument: the library supports one fixed
factory Standard MIDI profile.

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
from xtouch_compact import ButtonPressed

event = session.receive(timeout=0.25)
if isinstance(event, ButtonPressed):
    print(event.button, event.layer)
```

`receive()` processes one transport result and returns its decoded event, if
any. `timeout=None` waits indefinitely for transport input; `timeout=0` polls;
a positive value waits up to that many seconds. Unsupported traffic may make
the call return `None` before the timeout expires. The call is synchronous;
there is no callback API, background thread, or asyncio integration.

`receive()` returns `None` on timeout and also when a received MIDI message
does not decode into one of the typed physical events below (unknown
address, or foot-control input). Use `receive_input()` when diagnostics need
the raw message:

```python
received = session.receive_input(timeout=0.25)
if received is not None:
    print(received.message, received.physical_event)
```

`receive_input()` is useful for correlating a raw MIDI message with the
application-level event it decoded to (or `None` if it decoded to none).
It is not a lossless capture mechanism: the ALSA transport itself returns
`None` for an ALSA sequencer event type it does not convert to a MIDI
message (see `midi_from_alsa_event` in
[`alsa_transport.py`](../src/xtouch_compact/alsa_transport.py)), and that
case is indistinguishable from an ordinary timeout at the session level.
Anything that needs every ALSA event, decodable or not, needs a lower-level
ALSA capture tool instead of this API.

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

Fader positions use the MIDI 7-bit range 0–127. `EncoderRingDisplay.at()` and
`.blinking_at()` take a ring segment position from 1 through 13, not a MIDI
0–127 value; `.off()`, `.all_on()`, and `.all_blinking()` take no position.
Button LEDs accept `OFF`, `ON`, and `BLINK`. Encoder ring modes are `SINGLE`,
`PAN`, `FAN`, `SPREAD`, and `TRIM`.

Setters suppress values that still match their usable last-sent state;
physical input can invalidate that history and permit an equal request to
be sent again. `select_layer()` always transmits, and faders follow the
[ownership rules](#fader-ownership) below. Last-sent state is command history.
The device does not acknowledge that the LED, ring, or motor actually moved.

`sync_feedback()` resends desired button, ring, layer, and foot-switch LED
state that differs from last-sent state. `invalidate_feedback_state()` marks
last-sent values unknown while keeping desired values, so the next sync or
setter can reassert them.

## Fader Ownership

Each motorized fader has an independent snapshot from `fader_state(fader)`;
its fields are listed in [State Inspection](api.md#state-inspection).

The application must call `receive()` or `receive_input()` regularly: those
calls process touch, release, and position reports. A touch still queued in
the transport has not changed the session's ownership state. The physical
device's touch override is separate from this software state.

A processed touch gives that fader to the human. `set_fader()` updates the
desired value but sends no motor command while the session considers it
touched. A processed release returns ownership to the application and
reconciles a known desired value. Duplicate releases do not actuate.

For both an application request and release reconciliation:

- If `observation_is_current` is true, compare the desired value with the
  observed value. Send only if they differ.
- Otherwise, compare with `last_commanded_value`. Send only if they differ.

A position report makes the observation current. A successfully sent motor
command makes it non-current; merely touching the fader does not refresh it.
"Current" means no motor command has been sent since the report, not that
the device has acknowledged its position. The old `observed_value` remains
available as diagnostic history. Other faders are unaffected.

Initialization does not move faders to discover their positions. Unknown
desired and observed values stay unset until the application or the device
provides them.

## Reconnect

`reconnect()` is an explicit, synchronous transaction. It closes the previous
connection, reconnects the transport, asserts the currently desired layer,
and calls `sync_feedback()`. The default ALSA transport discovers the device
by name again; custom transports supply their own connection behavior.
Reconnect resets all fader snapshots and does not restore motor positions.

A live ALSA send or receive failure raises `TransportConnectionError`, moves
the session to `DISCONNECTED`, and leaves desired surface feedback in place
for a later `reconnect()`. A `None` receive result is not proof that the device
is gone: it can mean timeout or unsupported traffic. The library does not
poll or ping the device to establish liveness on its own, so a receive
timeout is not a presence check, a watchdog, or an emergency-stop signal.
Call `reconnect()` after you have established, by whatever means your
application uses (a raised `TransportConnectionError`, a USB hotplug
notification, an operator action), that the controller has actually
returned.

Deciding what device loss or an unresponsive controller means for the rest
of an application — including any robot or motion-control behavior gated on
it — is the application's responsibility. The library provides transport and
session state (`SessionState`, the exceptions above); it does not provide a
safety-rated enable/stop mechanism.

## Close

`close()` is idempotent. A closed session may be connected again with
`connect()` then `initialize()`. Context-manager exit always closes.

## Application-Owned Bindings

The library supplies physical identities and feedback, while the application
assigns meaning: a fader might request a joint position, an encoder might
adjust a parameter, and PLAY might trigger an application action. Robot
bindings, motion planning, servo loops, and safety functions are not supplied.
The library does not guarantee real-time timing or device presence.

Use the semantic setters for tracked feedback. Raw diagnostic `send()` bypasses
both feedback tracking and fader ownership. Mixing raw writes with setters can
leave last-sent history stale and suppress a later semantic command. For
non-fader feedback, `invalidate_feedback_state()` allows a subsequent sync to
reassert desired values; it does not invalidate fader command history. Use a
separate diagnostic session for raw motor experiments.
