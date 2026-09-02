"""Shared pytest fixtures: one spec load, one fake-session factory."""

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
from xtouch_compact import (
    DeviceSpecification,
    InboundDecoder,
    XTouchCompactSession,
    load_device_specification,
)


@pytest.fixture(scope="session")
def spec_path() -> Path:
    return SPEC_PATH


@pytest.fixture(scope="session")
def specification(spec_path: Path) -> DeviceSpecification:
    return load_device_specification(spec_path)


@pytest.fixture(scope="session")
def device_spec_document(spec_path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="session")
def decoder(specification: DeviceSpecification) -> InboundDecoder:
    return InboundDecoder(specification)


@pytest.fixture
def build_session(specification: DeviceSpecification) -> SessionBuilder:
    return bind_session_builder(specification)


@pytest.fixture
def ready_session(
    specification: DeviceSpecification,
) -> tuple[XTouchCompactSession, FakeTransport]:
    return make_fake_session(specification, ready=True)
