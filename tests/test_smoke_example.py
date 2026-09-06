"""Cleanup guarantees for ``examples/smoke.py``: closure and best-effort reset.

Loads the standalone script as a module (it is not part of the package) and
drives its ``run()`` entry point with a mocked session and stubbed steps.
No controller or ALSA device is required, and CLI parsing/operator prompts
are untouched -- only the connect/initialize/steps/cleanup sequence in
``run()`` is exercised here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

from xtouch_compact import (
    LifecycleError,
    SessionState,
    TransportConnectionError,
    XTouchCompactSession,
)

_SMOKE_PATH = Path(__file__).resolve().parent.parent / "examples" / "smoke.py"


def _load_smoke() -> ModuleType:
    spec = importlib.util.spec_from_file_location("examples_smoke", _SMOKE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def smoke() -> ModuleType:
    module = _load_smoke()
    module.RESULTS.clear()
    return module


def _mock_session(state: SessionState) -> Mock:
    session = Mock(spec=XTouchCompactSession)
    session.state = state
    return session


def _stub_steps(smoke: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "step_fader",
        "step_play_led",
        "step_encoder_ring",
        "step_receive_loop",
    ):
        monkeypatch.setattr(smoke, name, Mock())


def test_normal_completion_closes_the_session(
    smoke: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_steps(smoke, monkeypatch)
    reset_surface = Mock()
    monkeypatch.setattr(smoke, "reset_surface", reset_surface)
    session = _mock_session(SessionState.READY)

    exit_code = smoke.run(session)

    session.connect.assert_called_once()
    session.initialize.assert_called_once()
    session.close.assert_called_once()
    assert reset_surface.call_count == 2  # clean-start reset + final reset
    assert exit_code == 0


def test_connect_failure_is_reported_without_closing(
    smoke: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_steps(smoke, monkeypatch)
    session = _mock_session(SessionState.DISCONNECTED)
    session.connect.side_effect = TransportConnectionError("no device")

    exit_code = smoke.run(session)

    session.initialize.assert_not_called()
    # connect() already tears itself down internally on failure; the
    # script does not need to (and cannot usefully) close afterward.
    session.close.assert_not_called()
    assert exit_code == 1


def test_initial_reset_failure_aborts_steps_and_closes(
    smoke: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_steps(smoke, monkeypatch)
    monkeypatch.setattr(
        smoke, "reset_surface", Mock(side_effect=[RuntimeError("initial reset"), None])
    )
    session = _mock_session(SessionState.READY)
    with pytest.raises(RuntimeError, match="initial reset"):
        smoke.run(session)
    smoke.step_fader.assert_not_called()
    session.close.assert_called_once()


@pytest.mark.parametrize("close_error", [None, RuntimeError, KeyboardInterrupt])
def test_initialization_failure_after_connection_still_closes(
    smoke: ModuleType, monkeypatch: pytest.MonkeyPatch, close_error
) -> None:
    _stub_steps(smoke, monkeypatch)
    session = _mock_session(SessionState.STARTUP_LAYER_UNASSERTED)
    session.initialize.side_effect = LifecycleError("initialization failed")
    if close_error is not None:
        session.close.side_effect = close_error("close failed")

    exit_code = smoke.run(session)

    session.connect.assert_called_once()
    session.initialize.assert_called_once()
    session.close.assert_called_once()
    assert exit_code == 1


def test_step_failure_still_triggers_closure(
    smoke: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_steps(smoke, monkeypatch)
    smoke.step_fader.side_effect = ValueError("boom")
    reset_surface = Mock()
    monkeypatch.setattr(smoke, "reset_surface", reset_surface)
    session = _mock_session(SessionState.READY)

    with pytest.raises(ValueError, match="boom"):
        smoke.run(session)

    session.close.assert_called_once()
    assert reset_surface.call_count == 2


def test_keyboard_interrupt_during_a_step_still_triggers_closure(
    smoke: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_steps(smoke, monkeypatch)
    smoke.step_play_led.side_effect = KeyboardInterrupt()
    session = _mock_session(SessionState.READY)

    with pytest.raises(KeyboardInterrupt):
        smoke.run(session)

    session.close.assert_called_once()


@pytest.mark.parametrize(
    "error_type", [TransportConnectionError, RuntimeError, KeyboardInterrupt]
)
@pytest.mark.parametrize("stage", ["reset", "close"])
def test_cleanup_failure_still_attempts_close(
    smoke: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error_type: type[BaseException],
    stage: str,
) -> None:
    _stub_steps(smoke, monkeypatch)
    reset = Mock(side_effect=[None, error_type("gone")] if stage == "reset" else None)
    monkeypatch.setattr(smoke, "reset_surface", reset)
    session = _mock_session(SessionState.READY)
    if stage == "close":
        session.close.side_effect = error_type("gone")

    if error_type is TransportConnectionError:
        assert smoke.run(session) == 0
    else:
        with pytest.raises(error_type, match="gone"):
            smoke.run(session)

    session.close.assert_called_once()
    assert "gone" in capsys.readouterr().out


@pytest.mark.parametrize(
    "error_type", [TransportConnectionError, RuntimeError, KeyboardInterrupt]
)
@pytest.mark.parametrize("primary_type", [RuntimeError, KeyboardInterrupt])
def test_primary_failure_survives_reset_and_close_failures(
    smoke: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error_type: type[BaseException],
    primary_type: type[BaseException],
) -> None:
    _stub_steps(smoke, monkeypatch)
    primary = primary_type("primary failure")
    smoke.step_fader.side_effect = primary
    monkeypatch.setattr(
        smoke, "reset_surface", Mock(side_effect=[None, error_type("reset failure")])
    )
    session = _mock_session(SessionState.READY)
    session.close.side_effect = error_type("close failure")

    with pytest.raises(primary_type) as caught:
        smoke.run(session)

    assert caught.value is primary
    session.close.assert_called_once()
    output = capsys.readouterr().out
    assert "reset failure" in output
    assert "close failure" in output


def test_step_failure_when_not_ready_does_not_attempt_reset(
    smoke: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards the ``session.state is SessionState.READY`` gate: cleanup
    reset is skipped once the session never reached READY, avoiding a
    pointless failing call on an uninitialized session."""
    _stub_steps(smoke, monkeypatch)
    reset_surface = Mock()
    monkeypatch.setattr(smoke, "reset_surface", reset_surface)
    session = _mock_session(SessionState.STARTUP_LAYER_UNASSERTED)
    session.initialize.side_effect = LifecycleError("initialization failed")

    smoke.run(session)

    reset_surface.assert_not_called()
    session.close.assert_called_once()
