"""Basic integrity of preserved evidence, not an alternative runtime specification."""

from pathlib import Path

import yaml


def test_characterization_artifact_remains_readable_and_attributed() -> None:
    root = Path(__file__).resolve().parents[1]
    document = yaml.safe_load(
        (root / "specs" / "xtouch-compact-midi.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    assert {"physical_layout", "transmit", "receive"} <= document.keys()
    # The measured encoding must remain distinguishable from the guide's claim.
    evidence = document["receive"]["button_led_value_semantics"]
    assert evidence["semantics_source"] == "hardware_observation"
    assert evidence["encoded_values"] == {"off": 0, "on": 2, "blink": 3}
    assert evidence["documented_by_manufacturer"] != evidence["effective"]


def test_cited_characterization_docs_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("hardware-observations.md", "xtouch-compact-midi.md"):
        assert (root / "docs" / name).is_file()
