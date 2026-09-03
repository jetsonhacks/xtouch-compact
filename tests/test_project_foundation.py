from pathlib import Path

import xtouch_compact


def test_package_imports() -> None:
    assert xtouch_compact.__version__ == "0.1.0"


def test_cited_characterization_docs_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "hardware-observations.md").is_file()
    assert (root / "docs" / "xtouch-compact-midi.md").is_file()


def test_device_spec_has_separate_physical_tx_and_rx_sections(
    device_spec_document: dict[str, object],
) -> None:
    device_spec = device_spec_document

    assert "physical_layout" in device_spec
    assert "transmit" in device_spec
    assert "receive" in device_spec


def test_device_spec_preserves_button_tx_rx_asymmetry(
    device_spec_document: dict[str, object],
) -> None:
    device_spec = device_spec_document
    transmit = device_spec["transmit"]
    receive = device_spec["receive"]
    assert isinstance(transmit, dict)
    assert isinstance(receive, dict)

    layer_a = transmit["layer_a"]
    assert isinstance(layer_a, dict)
    layer_a_buttons = layer_a["buttons"]
    assert isinstance(layer_a_buttons, dict)
    upper_top_1_tx = layer_a_buttons["upper_top_1"]
    assert isinstance(upper_top_1_tx, dict)

    button_leds = receive["button_leds"]
    assert isinstance(button_leds, dict)
    upper_top_1_rx = button_leds["upper_top_1"]
    assert isinstance(upper_top_1_rx, dict)

    assert upper_top_1_tx["number"] == 16
    assert upper_top_1_rx["number"] == 0


def test_device_spec_keeps_global_rx_channel_distinct_from_tx_channels(
    device_spec_document: dict[str, object],
) -> None:
    device_spec = device_spec_document
    transmit = device_spec["transmit"]
    receive = device_spec["receive"]
    assert isinstance(transmit, dict)
    assert isinstance(receive, dict)

    layer_a = transmit["layer_a"]
    assert isinstance(layer_a, dict)

    assert layer_a["midi_channel"] == 1
    assert receive["channel"] == "GLOBAL_CH"


def test_device_spec_defines_documented_mode_and_preset_commands(
    device_spec_document: dict[str, object],
) -> None:
    device_spec = device_spec_document
    receive = device_spec["receive"]
    assert isinstance(receive, dict)

    operation_mode = receive["operation_mode"]
    preset_layer = receive["preset_layer"]
    assert isinstance(operation_mode, dict)
    assert isinstance(preset_layer, dict)

    assert operation_mode == {
        "type": "control_change",
        "number": 127,
        "values": {
            "standard": 0,
            "mackie_control": 1,
            "ignored": "2-127",
        },
    }
    assert preset_layer == {
        "type": "program_change",
        "applies_in": "standard_mode_only",
        "values": {
            "layer_a": 0,
            "layer_b": 1,
            "ignored": "2-127",
        },
    }


def test_device_spec_records_characterized_tx_value_semantics(
    device_spec_document: dict[str, object],
) -> None:
    device_spec = device_spec_document
    transmit = device_spec["transmit"]
    assert isinstance(transmit, dict)

    for layer_name in ("layer_a", "layer_b"):
        layer = transmit[layer_name]
        assert isinstance(layer, dict)

        faders = layer["faders"]
        encoders = layer["encoders"]
        buttons = layer["buttons"]
        assert isinstance(faders, dict)
        assert isinstance(encoders, dict)
        assert isinstance(buttons, dict)

        for fader in faders.values():
            assert isinstance(fader, dict)
            touch = fader["touch"]
            assert touch["touched_value"] == 127
            assert touch["released_value"] == 0
            assert touch["semantics_source"] == "hardware_observation"

        for encoder in encoders.values():
            assert isinstance(encoder, dict)
            turn = encoder["turn"]
            push = encoder["push"]
            assert turn["value_semantics"] == "absolute_7_bit"
            assert turn["acceleration"] is True
            assert turn["repeated_boundary_values"] is True
            assert push["press_velocity"] == 127
            assert push["release_semantics"] == "note_off_velocity_0"
            assert push["semantics_source"] == "hardware_observation"

        for button in buttons.values():
            assert isinstance(button, dict)
            assert button["press_velocity"] == 127
            assert button["release_semantics"] == "note_off_velocity_0"
            assert button["semantics_source"] == "hardware_observation"


def test_device_spec_uses_characterized_button_led_rx_values(
    device_spec_document: dict[str, object],
) -> None:
    device_spec = device_spec_document
    receive = device_spec["receive"]
    assert isinstance(receive, dict)

    semantics = receive["button_led_value_semantics"]
    button_leds = receive["button_leds"]
    assert isinstance(semantics, dict)
    assert isinstance(button_leds, dict)

    effective_values = {
        "off": "note_on velocity 0-1",
        "on": "note_on velocity 2",
        "blink": "note_on velocity 3",
        "ignored": "note_on velocity 4-127",
    }
    assert semantics["semantics_source"] == "hardware_observation"
    assert semantics["effective"] == effective_values
    assert semantics["documented_by_manufacturer"] == {
        "off": "note_off OR note_on velocity 0",
        "on": "note_on velocity 1",
        "blink": "note_on velocity 2",
        "ignored": "note_on velocity 3-127",
    }

    for button_led in button_leds.values():
        assert isinstance(button_led, dict)
        assert button_led["values"] == effective_values


def test_device_spec_records_group_fader_feedback_behavior(
    device_spec_document: dict[str, object],
) -> None:
    device_spec = device_spec_document
    characterized_runtime = device_spec["characterized_runtime"]
    assert isinstance(characterized_runtime, dict)

    fader_feedback = characterized_runtime["fader_host_feedback"]
    assert fader_feedback == {
        "semantics_source": "hardware_observation",
        "representative_control": "fader_1",
        "representative_layer": "layer_a",
        "touch_motor_policy": "physical_touch_overrides_motor",
        "host_position_while_touched": "deferred",
        "deferred_position_policy": "last_received_wins",
        "deferred_position_applied": "on_touch_release",
        "reproducible_position_echo": False,
        "isolated_observation": (
            "One CC 1 value 0 occurred during an untouched sweep and did not "
            "recur over three endpoint cycles."
        ),
    }
