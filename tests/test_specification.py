from pathlib import Path
from types import MappingProxyType

import pytest
import yaml

from xtouch_compact import (
    Button,
    Encoder,
    Fader,
    FootControl,
    Layer,
    SpecificationError,
    load_device_specification,
)
from xtouch_compact.specification import MidiAddress, MidiMessageType

SPEC_PATH = Path(__file__).parents[1] / "specs" / "xtouch-compact-midi.yaml"


def _modified_spec(tmp_path: Path, modify: object) -> Path:
    with SPEC_PATH.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    modify(document)
    path = tmp_path / "invalid-spec.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def test_loader_builds_separate_immutable_tx_and_rx_indexes() -> None:
    specification = load_device_specification(SPEC_PATH)

    assert isinstance(specification.document, MappingProxyType)
    assert isinstance(specification.tx_index, MappingProxyType)
    assert isinstance(specification.rx_index, MappingProxyType)
    assert isinstance(specification.rx_control_index, MappingProxyType)
    tx = specification.tx_index[MidiAddress(MidiMessageType.NOTE, 16, midi_channel=1)][
        0
    ]
    rx = specification.rx_index[MidiAddress(MidiMessageType.NOTE, 0)]
    assert tx.control is Button.UPPER_TOP_1
    assert rx.control is Button.UPPER_TOP_1
    assert specification.rx_control_index[(Button.UPPER_TOP_1, "led")] is rx
    assert tx.address.number != rx.address.number


def test_loader_represents_every_supported_physical_identity() -> None:
    specification = load_device_specification(SPEC_PATH)
    tx_controls = {
        binding.control
        for bindings in specification.tx_index.values()
        for binding in bindings
    }

    assert set(Fader) <= tx_controls
    assert set(Encoder) <= tx_controls
    assert {
        button for button in Button if button not in {Button.LAYER_A, Button.LAYER_B}
    } <= tx_controls
    assert set(FootControl) <= tx_controls
    assert Button.LAYER_A.value == Layer.A.value
    assert Button.LAYER_B.value == Layer.B.value


def test_loader_rejects_duplicate_tx_addresses(tmp_path: Path) -> None:
    def duplicate_address(document: dict[str, object]) -> None:
        layer = document["transmit"]["layer_a"]
        layer["faders"]["fader_2"]["position"]["number"] = 1

    path = _modified_spec(tmp_path, duplicate_address)

    with pytest.raises(SpecificationError, match="duplicates TX address"):
        load_device_specification(path)


def test_loader_rejects_missing_physical_mapping(tmp_path: Path) -> None:
    def remove_mapping(document: dict[str, object]) -> None:
        del document["transmit"]["layer_b"]["buttons"]["upper_top_1"]

    path = _modified_spec(tmp_path, remove_mapping)

    with pytest.raises(SpecificationError, match="does not match physical controls"):
        load_device_specification(path)


def test_loader_rejects_out_of_range_midi_address(tmp_path: Path) -> None:
    def invalidate_address(document: dict[str, object]) -> None:
        document["receive"]["faders"]["fader_1"]["number"] = 128

    path = _modified_spec(tmp_path, invalidate_address)

    with pytest.raises(SpecificationError, match="0 through 127"):
        load_device_specification(path)


def test_loader_rejects_incomplete_semantic_encodings(tmp_path: Path) -> None:
    def remove_encoding(document: dict[str, object]) -> None:
        del document["receive"]["button_led_value_semantics"]["encoded_values"][
            "blink"
        ]

    path = _modified_spec(tmp_path, remove_encoding)

    with pytest.raises(SpecificationError, match="encoded values are incomplete"):
        load_device_specification(path)
