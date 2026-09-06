"""Shared pytest fixtures: one fake-session factory and the historical YAML."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.helpers import (
    SPEC_PATH,
    FakeTransport,
    SessionBuilder,
    bind_session_builder,
    make_fake_session,
)
from xtouch_compact import InboundDecoder, XTouchCompactSession


@pytest.fixture(scope="session")
def spec_path() -> Path:
    return SPEC_PATH


@pytest.fixture(scope="session")
def device_spec_document(spec_path: Path) -> dict[str, object]:
    """The historical characterization YAML, parsed directly.

    This is evidence, not runtime configuration: see ``specs/README.md``.
    Only tests about that historical artifact itself should use this
    fixture; runtime behavior tests use the fixed Python device map.
    """
    loaded = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def decoder() -> InboundDecoder:
    return InboundDecoder()


@pytest.fixture
def build_session() -> SessionBuilder:
    return bind_session_builder()


@pytest.fixture
def ready_session() -> tuple[XTouchCompactSession, FakeTransport]:
    return make_fake_session(ready=True)
