# Changelog

## Unreleased

**Breaking:** replaced the runtime YAML device specification with a fixed,
typed Python device map (`xtouch_compact.device_map`). The library now
supports exactly one factory Standard MIDI profile; there is no
configurable or injectable device specification.

- Removed public specification-loading API: `load_device_specification`,
  `DeviceSpecification`, `DEFAULT_SPEC_PATH`, and `SpecificationError`.
- Removed the `specification` argument from `XTouchCompactSession.__init__`
  and `XTouchCompactSession.open`. Construction is now
  `XTouchCompactSession(transport, *, global_midi_channel, startup_layer=...)`
  or `XTouchCompactSession.open(global_midi_channel=..., ...)`, with no
  device map to load or pass. `transport` injection is unchanged.
- Removed the runtime `PyYAML` dependency and the wheel's packaged copy of
  `specs/xtouch-compact-midi.yaml`; `PyYAML` remains a development-only
  dependency for tests that read the historical YAML directly.
- `specs/xtouch-compact-midi.yaml` remains in the repository as a
  historical characterization artifact (see `specs/README.md`), not as
  runtime configuration. It is not required to stay in sync with
  `xtouch_compact.device_map` going forward.
- No behavioral change to supported MIDI input/output semantics, state
  reconciliation, or lifecycle: this is an internal representation change
  plus the removal of the specification-injection API, verified by an
  address-by-address migration comparison (Layer A/B TX, RX fader/button
  LED/encoder-ring/status-LED/preset-layer mappings) between the old YAML
  loader output and the new fixed map, and by the existing behavioral test
  suite plus new fixed-map invariant tests
  (`tests/test_device_map.py`).

## 0.1.0

First public source release.

- Semantic session API for the Behringer X-TOUCH COMPACT in Standard MIDI mode
- ALSA Sequencer transport with name-based discovery
- Typed fader, encoder, and button input
- Host feedback for motors, button LEDs, encoder rings, layer selection, and
  the foot-switch status LED
- Fader touch ownership and surface-feedback synchronization
- Explicit reconnect; motor positions are not restored automatically
- `XTouchCompactSession.open()` constructs a session with the default ALSA
  transport and bundled device map
- Extracted Standard MIDI map and hardware-observation log
- Session policies described without development-milestone shorthand
