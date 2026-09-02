"""Load the validated, immutable X-TOUCH device description."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from ._specification_common import (
    DeviceSpecification,
    Interaction,
    MidiAddress,
    MidiMessageType,
    RxBinding,
    SpecificationError,
    TxBinding,
    _freeze,
    _mapping,
)
from ._specification_rx import build_rx_index, validate_semantic_values
from ._specification_tx import build_tx_index
from .controls import Button, Encoder, Fader, MappedControl

__all__ = [
    "DEFAULT_SPEC_PATH",
    "DeviceSpecification",
    "Interaction",
    "MidiAddress",
    "MidiMessageType",
    "RxBinding",
    "SpecificationError",
    "TxBinding",
    "load_device_specification",
]

_PACKAGED_SPEC_PATH = Path(__file__).parent / "data" / "xtouch-compact-midi.yaml"
_REPOSITORY_SPEC_PATH = (
    Path(__file__).parents[2] / "specs" / "xtouch-compact-midi.yaml"
)
DEFAULT_SPEC_PATH = (
    _PACKAGED_SPEC_PATH if _PACKAGED_SPEC_PATH.is_file() else _REPOSITORY_SPEC_PATH
)


def _validate_physical_layout(document: dict[str, Any]) -> None:
    layout = _mapping(document.get("physical_layout"), "physical_layout")
    expected = {
        "faders": {member.value for member in Fader},
        "encoders": {member.value for member in Encoder},
        "buttons": {
            member.value
            for member in Button
            if member not in {Button.LAYER_A, Button.LAYER_B}
        },
    }
    for group, expected_ids in expected.items():
        entries = layout.get(group)
        if not isinstance(entries, list):
            raise SpecificationError(f"physical_layout.{group} must be a list")
        actual_ids: list[str] = []
        for index, entry_value in enumerate(entries):
            entry = _mapping(entry_value, f"physical_layout.{group}[{index}]")
            physical_id = entry.get("id")
            if not isinstance(physical_id, str):
                raise SpecificationError(
                    f"physical_layout.{group}[{index}].id must be a string"
                )
            actual_ids.append(physical_id)
        if len(actual_ids) != len(set(actual_ids)):
            raise SpecificationError(f"physical_layout.{group} contains duplicate ids")
        if set(actual_ids) != expected_ids:
            raise SpecificationError(
                f"physical_layout.{group} does not match the supported controls"
            )


def load_device_specification(
    path: Path | str = DEFAULT_SPEC_PATH,
) -> DeviceSpecification:
    """Load and validate the complete machine-readable device description."""
    spec_path = Path(path)
    try:
        with spec_path.open(encoding="utf-8") as stream:
            loaded = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise SpecificationError(
            f"cannot load device specification {spec_path}"
        ) from error
    document = _mapping(loaded, "document")
    required_sections = {
        "device",
        "physical_layout",
        "transmit",
        "receive",
        "unverified",
        "characterized_runtime",
    }
    if set(document) != required_sections:
        raise SpecificationError(
            "document has missing or unexpected top-level sections"
        )
    _mapping(document["device"], "device")
    if not isinstance(document["unverified"], list):
        raise SpecificationError("unverified must be a list")
    _mapping(document["characterized_runtime"], "characterized_runtime")
    _validate_physical_layout(document)
    validate_semantic_values(document)
    tx_index = build_tx_index(document)
    rx_index = build_rx_index(document)
    rx_control_index: dict[tuple[MappedControl | None, str], RxBinding] = {}
    for binding in rx_index.values():
        key = (binding.control, binding.operation)
        if key in rx_control_index:
            raise SpecificationError(f"duplicate RX control operation {key}")
        rx_control_index[key] = binding
    return DeviceSpecification(
        _freeze(document),
        tx_index,
        rx_index,
        MappingProxyType(rx_control_index),
    )
