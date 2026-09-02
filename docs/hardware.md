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

These limits are part of the supported contract.

**Faders.** Host commands use 0–127. Touch overrides the motor. The session
suppresses motor commands while a fader is touched and sends a differing
desired value once on release. Ordinary host-driven travel does not produce a
reproducible position echo. Incoming position messages are still decoded; the
session does not drop a report because it matches a recent command.

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
locally. The session invalidates last-sent LED state for the whole group on
a decoded press so equal desired states can be sent again. Other button
groups are not given that treatment.

**Disconnect.** A timed `receive()` returning `None` is not proof that the
USB device is gone. After unplug or power-off, call `reconnect()` once the
controller is enumerated again. Reconnect restores button, ring, layer, and
foot-switch LED desired state. It does not move motorized faders.

**Foot controls.** The foot-switch status LED is host-controllable. Expression
pedal and foot-switch **input** is not published as typed events. Pedal range
was not characterized.

## What This Library Does Not Drive

- Mackie Control / MCU
- Expression-pedal activity LED
- USB and MIDI I/O status LEDs as independent outputs
- Layer A/B indicators as independent LEDs
- Any DAW, GUI, or robot mapping
