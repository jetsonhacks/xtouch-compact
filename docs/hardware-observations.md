# Hardware Observations

This log records empirical behavior separately from manufacturer claims.
The supported library contract is summarized in [hardware.md](hardware.md).
The human-readable Standard MIDI map is
[xtouch-compact-midi.md](xtouch-compact-midi.md). The historical machine-readable
artifact is `specs/xtouch-compact-midi.yaml` (see
[specs/README.md](../specs/README.md)); the operational runtime map is
[`device_map.py`](../src/xtouch_compact/device_map.py).

Use one dated section per session. Record the device mode and preset, Linux
host, connection tool or program, exact MIDI bytes or structured message,
expected result, observed result, and whether the observation was repeated.

These notes were written during hardware characterization of the factory
Standard MIDI maps. They are kept here because several session policies
(fader touch ownership, encoder-ring restore after mode change and
rotation, always-transmit layer selection, transport-button LED group
invalidation, mandatory startup layer assertion) come from these
measurements rather than from the manufacturer guide.

## Open Characterization Items

- Cause of one isolated CC 1 value 0 during an untouched host-driven sweep.
- Foot-control ranges and switch values if suitable hardware is available.
- Cause of unsolicited Layer A expression-pedal CC 26 values 0 and 1 while no
  expression pedal was attached during the 2026-08-09 fader procedure.
- Why passive ALSA receive returns no event rather than reporting connection
  loss after USB disconnect or power-off.

Hardware observations inform the design but do not replace manufacturer
protocol claims.

## Observed 2026-08-11: Transport Button Press Replaces Host LED State

**Evidence type:** Reported by the Tiny Dancer downstream consumer through the
production ALSA transport and session while operating a loaded show.

The host first assigned the PLAY LED to on. Pressing PLAY started playback and
Tiny Dancer assigned STOP to on. Pressing STOP paused playback before motion
end, but PLAY did not illuminate even though Tiny Dancer recomputed PLAY as
enabled. The session still recorded PLAY-on as its last sent state after the
STOP press, so its semantic deduplication suppressed the equal reassertion.
This confirms that one transport-button press can redraw another button's LED
within the group; invalidating only the pressed button does not restore group
coherence.

This observation establishes local LED replacement for a representative of
the six-button right-side transport group. The session applies that group
contract by invalidating every transport button's last-sent LED value on a
decoded group press while preserving desired feedback. It does not generalize
the finding to other assignable-button groups or to button release behavior.

Representative controls establish the working behavior for a control group.
Further testing should target observed deviations rather than repeat the same
procedure for every mapped address.

## Observed 2026-08-09: Connection Smoke Pass

**Evidence type:** Software-path observation. This check did not include a
physical encoder action or visual controller observation.

- Host: NVIDIA Jetson AGX Thor Developer Kit, Ubuntu 24.04.4 LTS, kernel
  `6.8.12-1021-tegra`.
- ALSA endpoint during this pass: client 24, port 0, client name
  `X-TOUCH COMPACT`, port name `X-TOUCH COMPACT MIDI 1`.
- Procedure: production session encoder path on Global MIDI Channel 2.
- Result: production discovery connected, session initialization sent the Layer
  A assertion, all three manual encoder steps were explicitly skipped, and the
  session closed cleanly.

This result verifies the host connection and harness lifecycle. It does not
verify encoder direction, acceleration, push, release, or visible feedback.

## Observed 2026-08-09: Representative Faders

**Evidence type:** Measured on hardware through the production ALSA transport
and session, with operator-reported physical movement and captured MIDI input.

- Mode and layer: Standard MIDI mode, Layer A explicitly asserted.
- Global MIDI Channel: 2. Device TX channel: 1.
- Representative controls: `fader_1`, `fader_5`, and `master_fader`.
- Command values: 0, 1, 63, 64, 126, and 127, with approximately one second
  between commands.
- Endpoint during the procedure: transient ALSA client 24, port 0.

The operator observed all three faders reach the expected discrete positions.
Value 0 placed each fader at the bottom, value 127 placed it at the top, and
the intermediate values moved in the expected bottom-to-top orientation. The
operator reported no dead zone, clipping, inversion, or unexpected
quantization. An initial report described the large 1-to-63 and 64-to-126
steps, separated by one-second capture windows, as intermittent movement.
Focused repeats with the exact command sequence disclosed resolved that report:
`fader_1`, `fader_5`, and `master_fader` each passed.

The combined captures covered 36 representative motor commands across initial
and focused repeat runs. They contained no Layer A fader-position message on CC
1, CC 5, or CC 9. This result agrees with the 2026-08-08 finding that ordinary
host-driven motor travel produces no reproducible fader-position echo.

The touch procedure began with `fader_1` at value 127. Touch produced Layer A
CC 101 value 127 and decoded as `FaderTouched`. A semantic application request
for value 64 remained suppressed by the session's fader ownership policy. The
harness then resolved the fader RX address from the canonical specification and
sent one isolated raw value 96 through the production session. The operator
observed that the motor remained at 127 while touched. Release produced CC 101
value 0 and decoded as `FaderReleased`; the motor then moved to value 96. The
capture contained no fader-position report for the deferred movement.

This procedure confirms both distinct behaviors:

1. The session policy does not send semantic motor requests while touched.
2. The device accepts a raw position command while touched, holds the motor,
   retains the command, and applies it after release.

Two unrelated Layer A CC 26 messages appeared during the motor sweeps: value 1
during the master-fader value-126 capture and values 0 then 1 at the start of a
focused fader-1 run. CC 26 is the Layer A expression-pedal address. The operator
confirmed that no expression pedal was attached. The cause and relationship, if
any, to motor commands remain unresolved. The decoder preserved these raw
messages and returned no semantic event under the current deferred foot-control
policy.

## Observed 2026-08-10: Fine-Trim Consumer Follow-Up on Encoder 1 and 9

**Evidence type:** Measured on hardware through the production ALSA
transport and session. This session followed
up on a downstream consumer's (tiny-dancer XA4) open question about
recovering single-detent turn intent from `encoder_1`'s absolute stream.

The `encoder_1_slow` step (one detent clockwise, then one detent
counterclockwise) captured four Layer A CC 10 messages — values 0, 1, 0,
0 — within 0.3 milliseconds of each other. That capture window did not
isolate two distinct physical detents in real time; the operator's turn
and the tool's three-second capture window did not stay in sync, so this
run does not confirm or refute a one-detent-to-one-CC-step correspondence
for `encoder_1` specifically. A repeat with deliberately spaced single
turns would be needed to settle that question for `encoder_1`.

The `encoder_9_fast` step (slow rotation in both directions, then rapid
rotation) is more informative. Its early, slow segment showed a clean
sequence of single-unit changes in both directions
(`10, 11, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13`), consistent with the
existing finding that slow detents change the value by one. The rapid
portion showed accelerated multi-unit jumps (for example `13, 16, 19, 22,
25, 26`), and reaching the lower boundary produced four consecutive
repeated value-0 messages before recovering — direct, repeated
confirmation of the documented saturation behavior: continued rotation at
a boundary yields identical repeated values with no further information,
not a distinguishable "still turning" signal.

Combined with the Encoders and Rings finding below, this
session supports treating the absolute CC stream as reliable for
direction on unsaturated, slow transitions and confirms the saturation
repeat is real and repeatable, but it does not by itself establish an
exact single-detent guarantee for `encoder_1`.

## Observed 2026-08-09: Encoders and Rings

**Evidence type:** Measured on hardware through the production ALSA transport
and session, with captured MIDI input and operator-reported ring patterns.

Layer A `encoder_1` used absolute CC 10. Clockwise movement increased the value
and counterclockwise movement decreased it. Layer A `encoder_9` used absolute
CC 18. Slow detents changed the value mainly by one. Rapid rotation produced
larger consecutive absolute-value changes, including increments of two and
three. Repeated value 0 messages occurred at the lower boundary.

Layer B showed the same value semantics on its distinct addresses:
`encoder_1` used CC 37 and `encoder_9` used CC 45. Slow movement changed CC 45
by one. Rapid movement produced changes of two and three in either direction,
and continued counterclockwise detents emitted repeated value 0 at saturation.

Layer A `encoder_16` push sent Note On 15 velocity 127 and Note Off 15 velocity
0. Layer B used Note 70 with the same press and release form. The semantic
decoder resolved all four messages to `encoder_16` in the corresponding layer.

The unattached expression input emitted values 0 and 1 when the first physical
encoder action followed session initialization. It used Layer A CC 26 and Layer
B CC 63. This repeated the unexplained traffic seen during the fader procedure
and shows that the messages were not specific to motor movement.

### Ring Value Remote Control

Encoder 1 passed these remote display checks on Global MIDI Channel 2:

- value 0 turned all ring LEDs off;
- positions 1, 7, and 13 lit the leftmost, center, and rightmost LEDs;
- blinking positions 1, 7, and 13 blinked those respective LEDs;
- value 27 lit all 13 LEDs steadily; and
- value 28 blinked all 13 LEDs.

Repeating remote position 10 after each mode command lit only LED 10 in Single,
Pan, Fan, Spread, and Trim modes. Remote ring-value commands therefore select
the documented direct display independently of the current behavior mode.

### Local Ring Behavior Modes

The operator moved encoder 1 through visible segment boundaries after each
mode command. Several absolute encoder detents can map to one of the 13 visible
segments.

- Single displayed one moving LED.
- Pan briefly lit adjacent LEDs together at a segment transition, then retained
  only the new LED after further detents.
- Fan lit a left-filled bar from LED 1 through the current position.
- Spread expanded symmetrically around the center. Position 10 lit LEDs 4
  through 10; values at or below center showed only the center LED.
- Trim kept the center LED on and filled from the current position to center on
  either side.

Changing the mode after a remote position-10 command replaced the remote
display with a pattern derived from the encoder's local value. The session had
previously retained position 10 as last sent and suppressed an identical value
request. Invalidating and resending the remote value restored LED 10 in every
mode. This measured coupling requires the session to invalidate and restore a
known desired ring display after a successful mode change.

## Observed 2026-08-10: Ring Redraw Also Follows Physical Rotation, Not Only Mode Change

**Evidence type:** Reported by a downstream consumer (tiny-dancer) through the
production ALSA transport and session, then reproduced by log inspection of a
decoded `EncoderPositionReported` sequence against the consumer's own recorded
remote ring commands.

The Local Ring Behavior Modes finding above establishes that a ring-mode
command redraws the ring from the local encoder value. Downstream use exposed
a second, distinct trigger for the same local redraw: turning the encoder
itself, with no mode command sent, also redraws the ring from the local value.

The consumer computed and sent a correct remote position after every encoder
turn, confirmed by log inspection. The physical ring nonetheless remained on a
position consistent with the encoder's own local counter and did not correct
itself once rotation stopped. The session's `last_sent_display` for that
encoder still held the correct value the consumer had sent, so a later
identical-value request from the consumer was deduplicated and never
retransmitted, leaving the desynced local redraw on the ring indefinitely.

The session now invalidates one encoder's `last_sent_display` on every decoded
`EncoderPositionReported` for that encoder (`SurfaceStateController.
invalidate_encoder_display`, called from the session receive path),
mirroring the existing mode-change invalidation. This
does not by itself resend a display; it only removes the false "already sent"
belief so the consumer's next `set_encoder_ring_value()` call for that encoder
is not suppressed as a no-op duplicate, even when the newly computed value is
identical to what was last remotely sent.

### Follow-Up: A Brief Local Flash Remains During Active Rotation

The invalidate-on-rotation fix above eliminates the indefinitely stuck ring
this section opened with: the ring now reliably settles on the correct remote
value once rotation stops. The downstream consumer reported a residual, much
smaller symptom: a brief visible flash of the local redraw on each detent
during active rotation, before the corrected remote value round-trips back
over MIDI and overwrites it.

This flash is expected given the mechanism above, not a defect in the
invalidate-and-resend fix. The device redraws its ring locally the instant it
processes its own rotation, which is inherently faster than a host round trip
(receive the CC, compute a new display, send it back). No purely host-side
fix removes this one-frame artifact for a semantic display value that tracks
rotation; a consumer that finds the flash undesirable for a given encoder can
send `EncoderRingDisplay.off()` for that encoder instead of a tracked
position, which has no local value to flash toward.

## Observed 2026-08-10: Right-Group Transport Row Silkscreen Order

**Evidence type:** Operator-reported physical device inspection (silkscreen
labels), not a MIDI capture. The Buttons and Layers entry below confirmed
`right_1` (`rewind`)'s Note number on hardware but never verified the
semantic label of `right_4` or `right_5`.

`src/xtouch_compact/controls.py`'s `Button` enum assigned `STOP = "right_4"`
and `RECORD = "right_5"`. A tiny-dancer consumer using `Button.STOP` reported
that the physical button lighting and responding was the one silkscreened
RECORD, not STOP. Direct inspection of the device's right-side transport row
confirmed the physical left-to-right silkscreen order is REWIND, FAST
FORWARD, LOOP, RECORD, STOP, PLAY — `right_4` is RECORD and `right_5` is
STOP, the reverse of the prior assignment.

Corrected in `controls.py`: `RECORD = "right_4"`, `STOP = "right_5"`. The
underlying `right_4`/`right_5` position identities and their Note numbers
(52 and 53 respectively, per `specs/xtouch-compact-midi.yaml`) are unchanged
— only the semantic name attached to each position was wrong. No consumer
test in this repository depended on which physical position `Button.STOP`
or `Button.RECORD` names, so no other mapping change was required.

## Observed 2026-08-09: Buttons and Layers

**Evidence type:** Measured on hardware through the production ALSA transport
and session, with raw and semantic captures plus operator-reported LEDs.

Representative button input matched the candidate TX map in both layers. Each
press used Note On velocity 127 and each release used Note Off velocity 0.

| Physical button | Layer A Note | Layer B Note |
|---|---:|---:|
| `upper_top_1` | 16 | 71 |
| `upper_mid_1` | 24 | 79 |
| `upper_bottom_1` | 32 | 87 |
| `lower_1` | 40 | 95 |
| `rewind` | 49 | 104 |

The Layer A `upper_top_1` input Note 16 and its RX LED Note 0 physically
confirmed the required TX/RX asymmetry. On Global MIDI Channel 2, representative
buttons from all five physical groups passed OFF at velocity 0, steady ON at
velocity 2, and BLINK at velocity 3. The prior characterized result remains
authoritative for velocity 1 (off) and values 4–127 (ignored); those
unsupported-value probes were not repeated.

While `upper_top_1` remained physically held, remote OFF, ON, and BLINK each
took visible effect. Releasing after the BLINK command turned the LED off. The
device therefore accepts host LED commands during a local hold, but local
release can replace the last remote state rather than restore it.

Physical Layer A/B button captures contained no dedicated Note or Program
Change event. They did contain the unresolved unattached-expression traffic:
Layer A CC 26 alternated between 0 and 1, and Layer B CC 63 emitted 0 then 1.
The physical buttons changed the local preset, but the host could not infer
that change from a layer event.

This unobservable local change exposed a session-state error. After the session
had last sent Layer A, the operator selected Layer B physically. A repeated
semantic Layer A request was deduplicated and left the device in B. The session
was corrected to transmit every explicit layer selection. A connected physical
recheck then passed A, B, and A selection on Global MIDI Channel 2.

## Observed 2026-08-09: Reconnect and Power Cycle

**Evidence type:** Measured on hardware through the production reconnect path
with operator-reported feedback restoration and recorded ALSA identity.

Both a powered USB disconnect/reconnect and a controller power cycle restored
the requested Layer A state, steady `upper_top_1` LED, encoder-1 Pan display at
center, and foot-switch status LED. Both runs returned the session to `READY`.
ALSA used endpoint `24:0` before and after each run, so this campaign did not
observe endpoint renumbering.

The first powered USB reconnect attempt exposed a cleanup failure: disconnecting
subscriptions from the vanished endpoint raised ALSA `No such file or
directory` and prevented reconnect. Transport cleanup now treats remote
subscription removal as best effort while still closing the local client. The
corrected physical repeat passed.

In both corrected runs, a one-second passive receive returned no event after
device loss instead of raising a connection error. Explicit reconnect still
rediscovered, initialized, and restored the device. Passive loss notification
therefore remains unresolved; callers must not treat a receive timeout as proof
that the controller is still connected.

## Observed 2026-08-09: Cold-Start Layer Assertion Repeat

**Evidence type:** Measured on hardware through production ALSA discovery and
startup initialization, with raw diagnostic capture before initialization.

Two true power cycles again produced a visible Layer A indication before any
host Program Change. During the requested pre-assertion fader-1 action, the
device produced a high-rate alternating stream on Layer A CC 9 with values 0
and 127 rather than usable continuous fader-1 CC 1 positions. This differs from
the 2026-08-08 pre-assertion capture, which recorded alternating values on CC 1;
both measured results are preserved as a device cold-start anomaly.

The production startup path then sent Program Change 0 on Global MIDI Channel
2. Fader 1 immediately returned to normal Layer A reporting: touch used CC 101
value 127, and movement emitted continuous CC 1 values. The post-assertion
capture observed positions from 1 through 110 across the operator's moves.
This repeat confirms that the visible Layer A indicator is not sufficient
startup state and that an explicit Program Change 0 remains mandatory.

## Reported 2026-08-09: ALSA Sequencer Enablement

**Evidence type:** Hardware observation reported after rebuilding the target
kernel.

- Host: NVIDIA Jetson, Linux kernel `6.8.12-1021-tegra`.
- Loaded modules: `snd_seq_midi`, `snd_seq_midi_event`, and `snd_seq`.
- Sequencer device: `/dev/snd/seq` present.
- Observed ALSA identity for this boot: client 24, port 0, client name
  `X-TOUCH COMPACT`, port name `X-TOUCH COMPACT MIDI 1`. Client 24 is transient
  and must not be used for discovery.
- Input tool: `aseqdump` subscribed to the observed port.
- Output tool: `aplaymidi` sent a MIDI file to the observed port.

Layer A input arrived on user-facing MIDI channel 1. Observed messages included
Note On 16 velocity 127 for button press, Note Off 16 velocity 0 for release,
CC 1 values 0–127 for fader 1 position, and CC 101 values 127 and 0 for fader 1
touch and release. Encoder 1 sent absolute CC 10 values from 0 through 127 in
its current configuration. Faster movement could skip values, and movement at
an endpoint could repeat the saturated value.

Output on the separately configured Global MIDI Channel 2 moved motorized
fader 1. This result establishes ALSA Sequencer as the normal Linux MIDI
transport for the project. RawMIDI remains available for low-level diagnostic
work.

An ALSA Sequencer exploration program then opened Sequencer client 128, found the
device at the current `24:0` identity by its client and port names, and created
input and output subscriptions. It decoded one live message as
`event=CONTROL_CHANGE channel=1 controller=1 value=63 source=24:0`. A separate
run queued and drained `CONTROL_CHANGE` on channel 2, controller 1, value 64.
The program disconnected both subscriptions and closed its client on Ctrl-C.
The program output verifies the outbound API call; motor movement from this
specific run was not independently observed.

The semantic-decoding extension was smoke-tested through ALSA Sequencer on the
same host. The program discovered client 24, port 0 by name, opened local client
128, created both subscriptions, and sent Program Change value 0 on Global MIDI
Channel 2 to select Layer A. It then received `CONTROL_CHANGE` on TX channel 1,
controller 26, value 0 from `24:0` and resolved the address through the YAML TX
map as `FootControl.EXPRESSION_PEDAL` in Layer A. Ctrl-C disconnected both
subscriptions and closed the client. The test observed the output API call and
one incoming message; it did not independently verify the controller's visible
layer or move any physical control.

## Reported 2026-08-08: Jetson AGX Thor Characterization

**Evidence type:** Hardware observation. The guide omits the characterized TX
value semantics and cold-start behavior. Its button LED RX values conflict with
the tested unit.

- Host: NVIDIA Jetson AGX Thor connected over USB.
- Device mode: Standard MIDI mode; Layer A and Layer B are presets within this
  mode.
- Device firmware: 1.14.
- X-TOUCH Editor: 1.1.0.
- Configured Global MIDI Channel: 2.
- Factory preset TX channel: 1 for both layers.
- ALSA identity during this session: card 2, RawMIDI endpoint `hw:2,0,0`, device
  node `/dev/snd/midiC2D0`.
- Transport: USB Class Compliant MIDI through ALSA RawMIDI and `amidi`.
- Kernel limitation: `/dev/snd/seq` was absent, so ALSA Sequencer tools such as
  `aconnect` were unavailable.
- Experiment date and repetition count: not recorded. The reporter described
  the behavior as repeatable.

### Transmit Behavior

Layer B `fader_1` sent position on CC 28 and touch on CC 111. Layer A
`fader_1` used CC 1 and CC 101 respectively. Position was an absolute 7-bit
value from 0 through 127. Touch down sent value 127; touch release sent value
0.

Layer B `encoder_1` sent rotation on CC 37 as an absolute 0–127 value. Clockwise
rotation increased the value and counterclockwise rotation decreased it. Slow
rotation commonly changed the value by one; faster rotation made larger jumps.
The value clamped at 0 and 127, and further detents at a boundary continued to
send the boundary value. A decoder must preserve those repeated messages as raw
input events.

Layer B `encoder_1` push used Note 55. It sent Note On velocity 127 for press
and Note Off velocity 0 for release. Ordinary illuminated buttons used the same
form. For example, Layer B `upper_top_1` sent:

```text
90 47 7F
80 47 00
```

The physical Layer A and Layer B buttons emitted no host-visible MIDI messages.
They acted as local preset selectors.

### Receive Behavior

Host feedback worked on the configured Global MIDI Channel 2, independently of
the preset TX channel. Verified functions included motor faders on CC 1–9,
encoder-ring mode on CC 10–25, encoder-ring value on CC 26–41, status LEDs on
CC 42–43, and preset selection with Program Change.

These commands produced the expected results:

```text
# Fader 1: bottom, then top
amidi -p hw:2,0,0 -S "B1 01 00"
amidi -p hw:2,0,0 -S "B1 01 7F"

# Encoder 1 ring: all LEDs on
amidi -p hw:2,0,0 -S "B1 1A 1B"

# Foot-switch status LED: on, then off
amidi -p hw:2,0,0 -S "B1 2A 7F"
amidi -p hw:2,0,0 -S "B1 2A 00"
```

The guide documents button LED feedback as Note 0–38 on the Global MIDI
Channel, with Note On velocity 0 for off, 1 for on, 2 for blink, and 3–127
ignored. Direct testing found this different Note On velocity map:

| Velocity | Observed LED behavior |
|---:|---|
| 0 | Off |
| 1 | Off |
| 2 | Solid on |
| 3 | Blink |
| 4–127 | Ignored |

The implementation should therefore send velocity 0 for off, 2 for on, and 3
for blink on this hardware profile. It should treat 4–127 as unsupported. The
machine-readable map uses these observed values for encoding and preserves the
manufacturer values separately as conflicting protocol evidence.

An earlier test held a physical button, which lit its LED locally, and then
sent velocity 1 as the presumed host `on` value. The LED turned off. The new
characterization explains that result because velocity 1 acts as off. It does
not establish how physical press/release behavior interacts with a previously
set host LED state; that interaction remains open.

### Host-Driven Fader Movement and TX Echo

The host selected Layer A with `C1 00` and captured device TX while sending
fader 1 positions on the Global MIDI Channel. An initial untouched sequence
sent values 0, 64, 127, and 64, and the capture read zero bytes. A broader
untouched sweep sent values 0, 32, 64, 96, 127, and 64. That capture contained
one position message, `B0 01 00` (Layer A CC 1 value 0), and no messages
corresponding to the other commanded positions.

A follow-up moved the untouched fader through three 127-to-0 cycles and then to
64. The capture again read zero bytes. The single value 0 report was therefore
not reproducible during this session. The tested fader produced no consistent
TX echo from host-driven motor movement.

The touched test used one continuous capture. Touching Layer A fader 1 produced
`B0 65 7F` (CC 101 value 127). While the finger remained on the cap, the host
sent values 0, 32, 64, 96, and 127. The motor remained stationary and the
device sent no CC 1 position messages. Releasing the fader produced
`B0 65 00` (CC 101 value 0). The motor then moved to 127, the final position
received while touched, without sending a CC 1 position message.

This representative fader test establishes the current group behavior:
physical touch overrides motor actuation. The motor remains stationary while
touch is active. Host position commands received during the override are
deferred rather than discarded; the last position wins and takes effect on
release. Neither ordinary motor travel nor deferred catch-up travel produced a
reproducible position echo. Input handling must still preserve raw position
messages because the isolated value 0 remains unexplained and physical fader
movement uses the same CC address.

### Cold-Start Layer A Assertion

After a cold boot, moving a fader did not produce the expected Layer A messages
even though the Layer A indicator was lit and the editor showed the stored
Layer A mappings as CC 1 for position and CC 101 for touch. Instead, `fader_1`
produced alternating CC 1 values 0 and 127 rather than continuous position
values. Layer B worked normally.

A follow-up experiment cold-booted the device and left both physical Layer
buttons untouched. The host sent this exact command:

```text
amidi -p hw:2,0,0 -S "C1 00"
```

`C1 00` is Program Change 0 on user-facing MIDI channel 2. The command directly
selects Layer A according to the documented RX map. Immediately afterward,
Layer A `fader_1` produced normal continuous position values on CC 1, MIDI
channel 1.

The experiment shows that this device can display Layer A after power-on while
Layer A fader transmission remains inactive. Explicitly selecting Layer A was
sufficient to activate transmission; the test found no need for a Layer B to
Layer A transition.

Design consequence: after a connection becomes ready, startup should select the
desired preset layer explicitly on the configured Global MIDI Channel before
the library publishes semantic control input. The library must not infer that
channel from the factory control TX mappings or infer active startup state from
the Layer LED.
