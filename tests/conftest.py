"""Shared pytest fixtures: one fake-session factory and decoder."""

from __future__ import annotations

import pytest

from tests.helpers import FakeTransport, SessionFactory, make_fake_session
from xtouch_compact import InboundDecoder, XTouchCompactSession


@pytest.fixture(scope="session")
def decoder() -> InboundDecoder:
    return InboundDecoder()


@pytest.fixture
def build_session() -> SessionFactory:
    return make_fake_session


@pytest.fixture
def ready_session() -> tuple[XTouchCompactSession, FakeTransport]:
    return make_fake_session(ready=True)
