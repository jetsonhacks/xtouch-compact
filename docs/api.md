# API

Import supported names from `xtouch_compact`. This page defines the public
contract; other implementation names, including `device_map`, are internal.

This is a 0.1.0 interface. Exact semantic-version guarantees remain flexible
until 1.0. Code written against these exports should not need a broad rewrite
for later 0.x work.

## Session and Lifecycle

| Name | Role |
|---|---|
| `XTouchCompactSession` | Semantic bidirectional session |
| `SessionState` | `DISCONNECTED`, `CONNECTING`, `STARTUP_LAYER_UNASSERTED`, `READY` |
| `ReceivedInput` | One raw MIDI message and its optional physical event |

```text
constructed -> connect() -> STARTUP_LAYER_UNASSERTED
            -> initialize() -> READY
            -> reconnect() -> READY
            -> close() -> DISCONNECTED
```

`XTouchCompactSession.open(*, global_midi_channel, startup_layer=Layer.A, port_name=None, transport=None)`
constructs a disconnected session with `AlsaSequencerTransport` and the
fixed factory device map. It does not open ALSA. `port_name` is the
optional ALSA port-name filter. Pass `transport` to skip the default
transport (tests and non-ALSA backends).

`XTouchCompactSession(transport, *, global_midi_channel, startup_layer=Layer.A)`
is the explicit constructor when the caller already has a transport. There
is no device-specification argument: the library supports one fixed
factory profile, represented in `xtouch_compact.device_map`.

`global_midi_channel` is the device Global MIDI Channel, 1–16.
`startup_layer` must be `Layer.A` or `Layer.B`. Invalid values raise
`SessionConfigurationError` at construction, before any ALSA I/O.

| Method | Purpose |
|---|---|
| `open(...)` | Class method: default ALSA transport and fixed factory device map. Does not connect. |
| `connect()` | Open the transport. Does not yet publish semantic input. |
| `initialize()` | Assert the desired layer and enter `READY`. |
| `reconnect()` | Reconnect the transport, assert layer, restore non-fader feedback. The default ALSA transport rediscovers the endpoint. |
| `close()` | Release transport resources. Idempotent. |
| `receive(timeout=None)` | Next physical event, or `None`. `None` blocks; `0` polls; a positive value waits that many seconds. Also returns `None` when a received message does not decode into a typed event. |
| `receive_input(timeout=None)` | Raw message plus optional event. Same timeout contract as `receive()`. Not a lossless capture: the ALSA transport itself returns `None` for an ALSA event type it does not convert, indistinguishable here from a timeout. |
| `send(message)` | Raw diagnostic output; bypasses deduplication and touch ownership on the way out, and invalidates (never overwrites) matching tracked command history after a successful send. See [Application-Owned Bindings](usage.md#application-owned-bindings). |
| `set_fader(fader, value)` | Request a motor position, subject to touch ownership. |
| `fader_state(fader)` | Immutable fader snapshot. |
| `set_button_led(button, state)` | Assignable button LED: off, on, or blink. |
| `set_encoder_ring_mode(encoder, mode)` | Encoder LED-ring mode. Restores a known desired display after the mode command. |
| `set_encoder_ring_value(encoder, display)` | Encoder LED-ring display. |
| `select_layer(layer)` | Always transmits Layer A or B. |
| `set_foot_switch_led(state)` | Foot-switch status LED. |
| `button_feedback_state(button)` | Desired and last-sent LED state. |
| `encoder_feedback_state(encoder)` | Desired and last-sent ring mode and display. |
| `layer_feedback_state()` | Desired and last-sent layer. |
| `status_feedback_state(control=FootControl.FOOT_SWITCH)` | Desired and last-sent status LED. |
| `surface_state()` | Aggregate feedback snapshot. |
| `invalidate_feedback_state()` | Forget last-sent values; keep desired values. |
| `sync_feedback()` | Send desired feedback that differs from last-sent state. |

Context manager: `__enter__` calls `connect()` then `initialize()`;
`__exit__` always calls `close()`.

`session.state` reports the current `SessionState`.

## Physical Identities

| Type | Members |
|---|---|
| `Layer` | `A`, `B` |
| `Fader` | `CHANNEL_1` … `CHANNEL_8`, `MAIN` |
| `Encoder` | `CHANNEL_1` … `CHANNEL_8`, `POSITION_9` … `POSITION_16` |
| `Button` | `UPPER_TOP_*`, `UPPER_MID_*`, `UPPER_BOTTOM_*`, `LOWER_1` … `LOWER_9`, `REWIND`, `FAST_FORWARD`, `LOOP`, `RECORD`, `STOP`, `PLAY`, `LAYER_A`, `LAYER_B` |
| `FootControl` | `EXPRESSION_PEDAL`, `FOOT_SWITCH` |

Layer A/B indicator lights are device-owned. They follow `select_layer()` and
do not accept independent LED commands. `Button.LAYER_A` and `Button.LAYER_B`
identify the physical buttons, not host-assignable LEDs.

## Physical Events

| Type | Meaning |
|---|---|
| `ButtonPressed` / `ButtonReleased` | Assignable or transport button |
| `FaderPositionReported` | Fader value 0–127 |
| `FaderTouched` / `FaderReleased` | Fader touch strip |
| `EncoderPositionReported` | Encoder value 0–127 |
| `EncoderPressed` / `EncoderReleased` | Encoder push |

`PhysicalControlEvent` is the union of those types. Events include `layer`
and the raw MIDI message. Foot-control input is not a physical event; it
appears only as an undecoded message on `receive_input()`.

## Semantic Feedback

| Type | Values |
|---|---|
| `ButtonLedState` | `OFF`, `ON`, `BLINK` |
| `EncoderRingMode` | `SINGLE`, `PAN`, `FAN`, `SPREAD`, `TRIM` |
| `EncoderRingDisplayKind` | `OFF`, `POSITION`, `BLINKING_POSITION`, `ALL_ON`, `ALL_BLINKING` |
| `StatusLedState` | `OFF`, `ON` |

`EncoderRingDisplay` is a frozen command. Convenience constructors:

- `EncoderRingDisplay.off()`
- `EncoderRingDisplay.at(position)`
- `EncoderRingDisplay.blinking_at(position)`
- `EncoderRingDisplay.all_on()`
- `EncoderRingDisplay.all_blinking()`

Positioned displays require an integer ring segment position from 1 through
13, not a MIDI 0–127 value. Other kinds reject a position argument.

## State Inspection

| Type | Contents |
|---|---|
| `FaderOwner` | `APPLICATION`, `HUMAN` |
| `FaderState` | `desired_value`, `observed_value`, `observation_is_current`, `touched`, `owner`, `last_commanded_value` |
| `ButtonFeedbackState` | `button`, `desired`, `last_sent` |
| `EncoderFeedbackState` | `encoder`, desired and last-sent mode and display |
| `LayerFeedbackState` | `desired`, `last_sent` |
| `StatusFeedbackState` | `control`, `desired`, `last_sent` |
| `SurfaceStateSnapshot` | Tuples of the feedback states above |

Snapshots are immutable. Last-sent means the last command the transport
accepted. It is not confirmation that the hardware applied the command.

`observation_is_current` starts false, becomes true on a decoded position
report, and becomes false after a successfully sent motor command or reset.
Touch alone does not refresh it. When false, the stored observation is history;
reconciliation uses command history instead. See the
[fader ownership rules](usage.md#fader-ownership).

## Errors

```text
XTouchCompactError
├── LifecycleError
├── SessionConfigurationError
├── DiscoveryError
│   ├── DeviceNotFoundError
│   └── AmbiguousDeviceError
├── TransportError
│   ├── TransportStateError
│   └── TransportConnectionError
└── UnsupportedOperationError
```

Catch the narrow subclass, or `XTouchCompactError` for library lifecycle,
discovery, transport, and unsupported-operation failures. Invalid argument
types and numeric ranges can also raise `TypeError` or `ValueError`.
ALSA I/O failures are wrapped by the transport.

## Device Map

The library supports one fixed factory Standard MIDI profile, defined as a
typed Python table in `xtouch_compact.device_map` (an internal module, not
part of the public API). There is no runtime device-specification loading,
no injection point, and no YAML dependency at runtime. Mappings changed
with the X-TOUCH Editor are not supported.

`specs/xtouch-compact-midi.yaml` remains in the repository as a historical
characterization artifact — see [specs/README.md](../specs/README.md) — not
as runtime configuration. The human-readable map is
[xtouch-compact-midi.md](xtouch-compact-midi.md); empirical value
semantics are in [hardware-observations.md](hardware-observations.md).

## Advanced and Diagnostic Exports

These remain importable from the package root for tests and low-level tools.
Normal application code can ignore them.

- `AlsaSequencerTransport`, `SequencerEndpoint`, `discover_endpoint`
- `alsa_event_from_midi`, `midi_from_alsa_event`
- `InboundDecoder`
- `NoteOn`, `NoteOff`, `ControlChange`, `ProgramChange`, `RawMidiMessage`
- `MidiTransport`

`AlsaSequencerTransport` is the Linux transport used to construct a session.
`MidiTransport` is the structural protocol it satisfies (`connect`,
`receive`, `send`, `close`); implement it only to supply a non-ALSA
transport in place of `AlsaSequencerTransport`.
Discovery matches a unique client name with read, write, and both
subscription capabilities.
