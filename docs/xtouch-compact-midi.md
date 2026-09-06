# X-TOUCH COMPACT Standard MIDI Map

**Source:** Behringer *X-TOUCH COMPACT Quick Start Guide*, V6.0 (2024)
**Relevant printed pages:** 29 — Preset Layer A; 30 — Preset Layer B; 32 — RX MIDI DATA

This document is a human-readable extraction of the Standard MIDI mappings in the Behringer guide. It deliberately separates:

- **Transmit (TX):** messages produced when a person operates the X-TOUCH.
- **Receive (RX):** messages a host sends to move faders or control LEDs/modes.
- **Physical identity:** stable control names independent of MIDI numbers.

This document labels details from hardware characterization as empirical rather
than attributing them to the guide.

## Physical control names

| Group | IDs | Count |
|---|---|---:|
| Channel faders | `fader_1` … `fader_8` | 8 |
| Master fader | `master_fader` | 1 |
| Encoders | `encoder_1` … `encoder_16` | 16 |
| Upper top buttons | `upper_top_1` … `upper_top_8` | 8 |
| Upper middle buttons | `upper_mid_1` … `upper_mid_8` | 8 |
| Upper bottom buttons | `upper_bottom_1` … `upper_bottom_8` | 8 |
| Lower buttons | `lower_1` … `lower_9` | 9 |
| Right-area buttons | `right_1` … `right_6` | 6 |

The guide describes 9 touch-sensitive motorized 100 mm faders, 16 push encoders with 13-segment LED rings, and 39 illuminated buttons.

## TX — Preset Layer A “Mixer Control”

**MIDI Channel: 1**

### Faders

| Physical control | Position | Touch |
|---|---:|---:|
| `fader_1` | CC 1 | CC 101 |
| `fader_2` | CC 2 | CC 102 |
| `fader_3` | CC 3 | CC 103 |
| `fader_4` | CC 4 | CC 104 |
| `fader_5` | CC 5 | CC 105 |
| `fader_6` | CC 6 | CC 106 |
| `fader_7` | CC 7 | CC 107 |
| `fader_8` | CC 8 | CC 108 |
| `master_fader` | CC 9 | CC 109 |

Fader position uses values **0–127**. The MIDI map identifies touch as CC but does not state the touch/release values; those should be measured.

### Encoders

| Physical control | Turn | Push |
|---|---:|---:|
| `encoder_1` | CC 10 | Note 0 |
| `encoder_2` | CC 11 | Note 1 |
| `encoder_3` | CC 12 | Note 2 |
| `encoder_4` | CC 13 | Note 3 |
| `encoder_5` | CC 14 | Note 4 |
| `encoder_6` | CC 15 | Note 5 |
| `encoder_7` | CC 16 | Note 6 |
| `encoder_8` | CC 17 | Note 7 |
| `encoder_9` | CC 18 | Note 8 |
| `encoder_10` | CC 19 | Note 9 |
| `encoder_11` | CC 20 | Note 10 |
| `encoder_12` | CC 21 | Note 11 |
| `encoder_13` | CC 22 | Note 12 |
| `encoder_14` | CC 23 | Note 13 |
| `encoder_15` | CC 24 | Note 14 |
| `encoder_16` | CC 25 | Note 15 |

The guide does not fully specify rotation values for a configured encoder mode.
Hardware characterization of the current presets found absolute 0–127 values,
acceleration, clamping, and repeated values at either boundary. See
[hardware-observations.md](hardware-observations.md); these semantics are
empirical rather than a manufacturer claim.

### Buttons

| Physical group | Physical IDs | TX Notes |
|---|---|---:|
| Upper top | `upper_top_1` … `upper_top_8` | 16–23 |
| Upper middle | `upper_mid_1` … `upper_mid_8` | 24–31 |
| Upper bottom | `upper_bottom_1` … `upper_bottom_8` | 32–39 |
| Lower | `lower_1` … `lower_9` | 40–48 |
| Right area | `right_1` … `right_6` | 49–54 |

Every encoder push and button push is documented as a **Note** command.

On the characterized unit, encoder pushes and ordinary buttons sent Note On
velocity 127 for press and Note Off velocity 0 for release. The physical Layer
A/B buttons sent no MIDI messages; they selected presets locally. These are
hardware observations rather than claims from the guide.

### Foot controls

| Control | TX |
|---|---:|
| Expression pedal | CC 26 |
| Foot switch | CC 27 |

## TX — Preset Layer B “Instrument Control”

**MIDI Channel: 1**

### Faders

| Physical control | Position | Touch |
|---|---:|---:|
| `fader_1` | CC 28 | CC 111 |
| `fader_2` | CC 29 | CC 112 |
| `fader_3` | CC 30 | CC 113 |
| `fader_4` | CC 31 | CC 114 |
| `fader_5` | CC 32 | CC 115 |
| `fader_6` | CC 33 | CC 116 |
| `fader_7` | CC 34 | CC 117 |
| `fader_8` | CC 35 | CC 118 |
| `master_fader` | CC 36 | CC 119 |

### Encoders

| Physical control | Turn | Push |
|---|---:|---:|
| `encoder_1` | CC 37 | Note 55 |
| `encoder_2` | CC 38 | Note 56 |
| `encoder_3` | CC 39 | Note 57 |
| `encoder_4` | CC 40 | Note 58 |
| `encoder_5` | CC 41 | Note 59 |
| `encoder_6` | CC 42 | Note 60 |
| `encoder_7` | CC 43 | Note 61 |
| `encoder_8` | CC 44 | Note 62 |
| `encoder_9` | CC 45 | Note 63 |
| `encoder_10` | CC 46 | Note 64 |
| `encoder_11` | CC 47 | Note 65 |
| `encoder_12` | CC 48 | Note 66 |
| `encoder_13` | CC 49 | Note 67 |
| `encoder_14` | CC 50 | Note 68 |
| `encoder_15` | CC 51 | Note 69 |
| `encoder_16` | CC 52 | Note 70 |

### Buttons

| Physical group | Physical IDs | TX Notes |
|---|---|---:|
| Upper top | `upper_top_1` … `upper_top_8` | 71–78 |
| Upper middle | `upper_mid_1` … `upper_mid_8` | 79–86 |
| Upper bottom | `upper_bottom_1` … `upper_bottom_8` | 87–94 |
| Lower | `lower_1` … `lower_9` | 95–103 |
| Right area | `right_1` … `right_6` | 104–109 |

### Foot controls

| Control | TX |
|---|---:|
| Expression pedal | CC 63 |
| Foot switch | CC 64 |

## RX — Host to X-TOUCH

The Behringer RX table labels these messages as using **GLOBAL CH**. They are independent of the editable Layer A/B TX preset mappings.

### Operation mode

| Function | RX command | Values |
|---|---|---|
| Operation mode | CC 127 | 0 = Standard; 1 = MC; 2–127 ignored |
| Preset layer | Program Change | 0 = Layer A; 1 = Layer B; 2–127 ignored; Standard mode only |

Changing the preset layer also selects the corresponding Layer A/B LED.

### Motorized faders

| Physical control | RX | Values |
|---|---:|---|
| `fader_1` | CC 1 | 0–127, bottom to top |
| `fader_2` | CC 2 | 0–127, bottom to top |
| `fader_3` | CC 3 | 0–127, bottom to top |
| `fader_4` | CC 4 | 0–127, bottom to top |
| `fader_5` | CC 5 | 0–127, bottom to top |
| `fader_6` | CC 6 | 0–127, bottom to top |
| `fader_7` | CC 7 | 0–127, bottom to top |
| `fader_8` | CC 8 | 0–127, bottom to top |
| `master_fader` | CC 9 | 0–127, bottom to top |

### Encoder-ring behavior

| Physical control | RX CC |
|---|---:|
| `encoder_1` | CC 10 |
| `encoder_2` | CC 11 |
| `encoder_3` | CC 12 |
| `encoder_4` | CC 13 |
| `encoder_5` | CC 14 |
| `encoder_6` | CC 15 |
| `encoder_7` | CC 16 |
| `encoder_8` | CC 17 |
| `encoder_9` | CC 18 |
| `encoder_10` | CC 19 |
| `encoder_11` | CC 20 |
| `encoder_12` | CC 21 |
| `encoder_13` | CC 22 |
| `encoder_14` | CC 23 |
| `encoder_15` | CC 24 |
| `encoder_16` | CC 25 |

Behavior values:

| Value | Ring mode |
|---:|---|
| 0 | Single |
| 1 | Pan |
| 2 | Fan |
| 3 | Spread |
| 4 | Trim |
| 5–127 | ignored |

### Encoder-ring value

| Physical control | RX CC |
|---|---:|
| `encoder_1` | CC 26 |
| `encoder_2` | CC 27 |
| `encoder_3` | CC 28 |
| `encoder_4` | CC 29 |
| `encoder_5` | CC 30 |
| `encoder_6` | CC 31 |
| `encoder_7` | CC 32 |
| `encoder_8` | CC 33 |
| `encoder_9` | CC 34 |
| `encoder_10` | CC 35 |
| `encoder_11` | CC 36 |
| `encoder_12` | CC 37 |
| `encoder_13` | CC 38 |
| `encoder_14` | CC 39 |
| `encoder_15` | CC 40 |
| `encoder_16` | CC 41 |

Value semantics:

| Value | Result |
|---:|---|
| 0 | all LEDs off |
| 1–13 | LED 1 (left) through LED 13 (right) on |
| 14–26 | LED 1 through LED 13 blinking |
| 27 | all LEDs on |
| 28 | all LEDs blinking |
| 29–127 | ignored |

### Button LED remote control

RX Note numbers address the **39 physical illuminated buttons independently of the Layer A/B TX note numbers**.

| Physical group | Physical IDs | RX Notes |
|---|---|---:|
| Upper top | `upper_top_1` … `upper_top_8` | 0–7 |
| Upper middle | `upper_mid_1` … `upper_mid_8` | 8–15 |
| Upper bottom | `upper_bottom_1` … `upper_bottom_8` | 16–23 |
| Lower | `lower_1` … `lower_9` | 24–32 |
| Right area | `right_1` … `right_6` | 33–38 |

Button LED values:

The manufacturer table specifies:

| Message | Result |
|---|---|
| Note Off | off |
| Note On velocity 0 | off |
| Note On velocity 1 | on |
| Note On velocity 2 | blinking |
| Note On velocity 3–127 | ignored |

Hardware testing on firmware 1.14 found different effective values:

| Message | Observed result |
|---|---|
| Note On velocity 0 | off |
| Note On velocity 1 | off |
| Note On velocity 2 | on |
| Note On velocity 3 | blinking |
| Note On velocity 4–127 | ignored |

The current implementation should encode off as velocity 0, on as velocity 2,
and blink as velocity 3. The machine-readable map retains both sets and marks
the observed values as the effective hardware semantics.

Layer A/B LEDs are not directly assignable; they follow the selected preset layer.

### Status LEDs

| LED | RX command | Semantics |
|---|---:|---|
| Foot switch | CC 42 | 0–63 off; 64–127 on |
| Expression pedal | CC 43 | on only while data/value change is occurring |
| MC Mode | not assignable | reflects operation mode |
| USB | not assignable | active with valid host connection |
| MIDI I/O | not assignable | active during data transfer |

## Important asymmetry

The physical buttons have **different TX and RX note numbers**.

For example, in Layer A:

- `upper_top_1` transmits **Note 16** when operated.
- Its LED is remotely controlled with **Note 0**.

The device-description layer should therefore model input and feedback mappings separately rather than assuming one MIDI address per physical control.

## Hardware-Characterized TX Semantics

The Quick Start Guide omits several TX value details. Tests on firmware 1.14
with the factory Layer A/B mappings found:

1. Fader touch uses value 127 for touched and 0 for released.
2. Encoder rotation uses an accelerated absolute 0–127 value. Values clamp at
   the boundaries, and later detents continue to send repeated 0 or 127 values.
3. Encoder pushes and ordinary buttons use Note On velocity 127 for press and
   Note Off velocity 0 for release.
4. The physical Layer A/B buttons emit no host-visible MIDI message.

Representative fader testing found no reproducible position echo from ordinary
or deferred host-driven motor travel. One isolated Layer A CC 1 value 0 remains
unexplained. Representative testing confirmed that remote OFF, ON, and
BLINK take effect while a physical button is held; releasing after BLINK turns
the LED off. Testing also confirmed that physical Layer A/B changes have no
dedicated host-visible event. An explicit host layer selection must therefore
be sent even when cached host state already names that layer. See
[hardware-observations.md](hardware-observations.md) for the measured
procedures and their limits.

## Runtime device map and historical artifact

The fixed Python map in
[`device_map.py`](../src/xtouch_compact/device_map.py) is the sole operational
source of truth. It defines the factory mappings and builds the validated
TX and RX indexes used at runtime.

[`xtouch-compact-midi.yaml`](../specs/xtouch-compact-midi.yaml) preserves the
historical characterization evidence. It is not loaded at runtime or
packaged in the wheel; see [`specs/README.md`](../specs/README.md).
