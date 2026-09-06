# specs/

`xtouch-compact-midi.yaml` is a **historical characterization artifact**,
not runtime configuration. It was produced during the initial hardware
characterization phase of this project: address values transcribed from the
Behringer X-TOUCH COMPACT Quick Start Guide (V6.0, 2024; TX pages 29-30, RX
page 32), plus fields explicitly tagged `semantics_source:
hardware_observation` for behavior confirmed or corrected against the real
device (see `docs/hardware-observations.md`). It also records device
features the library does not implement (for example the expression-pedal
and MC-mode status LEDs) and two `unverified` open questions from that
characterization work.

As of the fixed-device-map migration, the library's authoritative
operational definition of the factory MIDI profile is the typed Python
table in `src/xtouch_compact/device_map.py`. The runtime does not parse
this YAML file, does not load it from disk or from package data, and does
not accept it (or any replacement) as a device specification. There is no
supported way to substitute an alternate device map at runtime.

This file is kept in the repository, and in source distributions, purely as
evidence: it preserves the manufacturer/manual-derived values and the
measured deviations from them, distinguished by `semantics_source`, in one
place a human can audit against the printed guide and the observation log.
It is **not** installed as package data in the built wheel.

The YAML and `device_map.py` are two independent representations of the
same physical device, maintained separately. They are not required to stay
in sync going forward, and a future correction to one does not imply an
obligation to update the other — that would leave two operational
specifications to maintain, which is exactly what this migration removed.
At the time of the migration, every runtime-consumed value here was
compared against `device_map.py` and found to match (see the Unreleased
changelog entry for how that comparison was performed).
