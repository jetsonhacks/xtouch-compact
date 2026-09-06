# Hardware

## Linux and ALSA Sequencer

`xtouch-compact` sends and receives MIDI through the ALSA Sequencer. The
kernel must expose `/dev/snd/seq`. Userspace packages cannot substitute for
that device node.

On a working host:

```bash
ls -l /dev/snd/seq
lsmod | grep snd_seq
aconnect -l
```

Expect modules such as `snd_seq`, `snd_seq_midi`, and `snd_seq_midi_event`,
and an ALSA client named `X-TOUCH COMPACT`.

If RawMIDI tools such as `amidi` see the controller but `/dev/snd/seq` is
absent, the kernel was built without sequencer support. Some Linux kernels,
including stock NVIDIA Jetson kernels, ship in that configuration.

This project does not provide kernel sources, kernel configuration, module
packages, or support for rebuilding a kernel. Enable ALSA Sequencer on the
host first, then use this library.

## Controller Mode

Operate the X-TOUCH COMPACT in Standard MIDI mode. Mackie Control is out of
scope.

Set the Global MIDI Channel on the device and pass the same number, in the
range 1–16, as `global_midi_channel` when constructing `XTouchCompactSession`.
Host feedback uses that channel. Factory Layer A/B transmit maps often use a
different channel for faders, encoders, and buttons. The session keeps those
paths separate.

## Known Device Behavior

These limits are part of the supported contract. Dated measurement notes
are in [hardware-observations.md](hardware-observations.md). The extracted
Standard MIDI map is [xtouch-compact-midi.md](xtouch-compact-midi.md).

**Faders.** Host commands use 0–127. Physical touch overrides the motor, and
ordinary host-driven travel does not produce a reproducible position echo.
The session's software ownership follows processed input; see
[Fader Ownership](usage.md#fader-ownership) for input servicing and
reconciliation rules.

**Encoder rings.** A ring-mode command redraws the ring from the local
encoder value and replaces a remotely assigned display. After a successful
mode change, the session resends the known desired display. Physical rotation
invalidates last-sent display so a later `set_encoder_ring_value()` is not
treated as a duplicate.

**Layer selection.** Physical Layer A/B buttons do not emit a dedicated
host-visible layer event. `select_layer()` always transmits. Cold start can
leave Layer A visually selected while fader traffic is abnormal until the
startup Program Change is sent. That is why `initialize()` is mandatory.

**Transport-button LEDs.** Pressing one of the six right-side transport
buttons (rewind through play) can redraw the group's host-assigned LEDs
locally, replacing the host's last-sent state for other buttons in the same
group without emitting any host-visible event for that replacement — see
[Observed 2026-08-11: Transport Button Press Replaces Host LED
State](hardware-observations.md#observed-2026-08-11-transport-button-press-replaces-host-led-state).
Because the host has no way to learn that another button's LED changed, the
session cannot trust its own record of what is currently lit for the whole
group once any member of it is pressed. It invalidates last-sent LED state
for the whole group on a decoded press (the `_TRANSPORT_BUTTONS` branch of
`SurfaceStateController.physical_event` in
[`surface_state.py`](../src/xtouch_compact/surface_state.py), exercised by
`test_transport_button_press_invalidates_group_for_led_reassertion` in
[`test_surface_state.py`](../tests/test_surface_state.py)) so that an equal
desired state, which would otherwise be suppressed as a no-op duplicate, is
sent again. This is a conservative policy generalized from one representative
button in the group, not an independently measured result for every
transport button; other button groups are not given that treatment because
no equivalent observation exists for them.

**Disconnect.** A `receive()` result of `None` can mean timeout or unsupported
traffic — it is not proof that the USB device is
gone, and the library does not poll or ping the device to check. Liveness
and device-loss policy are the application's responsibility; the library
does not provide a safety-rated presence detector, watchdog, or
emergency-stop mechanism. After unplug or power-off, call `reconnect()` once
you have established through some other means (a raised
`TransportConnectionError`, a hotplug notification, an operator action) that
the controller is enumerated again. Reconnect restores button, ring, layer,
and foot-switch LED desired state. It does not move motorized faders.

**Foot controls.** The foot-switch status LED is host-controllable. Expression
pedal and foot-switch **input** is not published as typed events. Pedal range
was not characterized.

## First-Hour Smoke Test

Before writing application code, confirm the box, the channel, and the
kernel are right. This is a manual, on-device check — not part of CI.

```bash
uv run python examples/smoke.py --channel 2
```

`--channel` is required and has no default. The Global MIDI Channel is
per-unit configuration read off the device's own display, not something the
library can assume or detect; guessing wrong here sends every feedback
command (fader, LED, ring) to a channel the device isn't listening on. The
device silently drops or misinterprets most of that traffic rather than
erroring, which reads as a broken button or ring instead of a wrong channel.

The script walks through, in order:

1. **Standard MIDI mode and channel.** Confirms the device is in Standard
   MIDI mode (not Mackie Control) and that the Global MIDI Channel you pass
   with `--channel` matches the number shown on the device.
2. **`aconnect`.** Runs `aconnect -l` and checks for a client named
   `X-TOUCH COMPACT`. A miss here usually means `/dev/snd/seq` is absent —
   see [Linux and ALSA Sequencer](#linux-and-alsa-sequencer) above.
3. **Reset.** Turns off every button LED and encoder ring before testing
   anything. Prior manual runs of other `examples/` scripts leave the
   device's LEDs and rings lit — there is no power-on reset between runs —
   so without this step you can't tell which light a given step actually
   commanded.
4. **Fader.** Commands the CHANNEL_1 fader to 0, then to 127, and asks you
   to confirm the motor moved.
5. **PLAY LED.** Blinks the PLAY button LED and asks you to confirm. Because
   of step 3, PLAY is the only lit button at this point, so any other LED
   lighting is diagnostic, not ambiguous.
6. **Encoder ring.** Sets encoder 1 to fan mode at mid-scale and asks you
   to confirm the ring lit correctly, then turns it back off.
7. **Receive loop.** Prints decoded events while you move the fader, turn
   encoder 1, and press PLAY, then asks whether all three produced events.

On normal exit, the script turns button LEDs and encoder rings off. Cleanup
also attempts this after a failure, but a lost connection can prevent those
commands from reaching the device. Faders stay at their last position.
Each completed stage records a pass/fail/skip; a summary prints after normal
completion. A clean
run through all stages is first-hour proof that the physical device, the
configured channel, and the host kernel's ALSA Sequencer support are all
correct before you build anything on top.

## What This Library Does Not Drive

- Mackie Control / MCU
- Expression-pedal activity LED
- USB and MIDI I/O status LEDs as independent outputs
- Layer A/B indicators as independent LEDs
- Any DAW, GUI, or robot mapping
