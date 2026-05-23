"""Tests for CA session liveness validation before command execution."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from code_analysis_client import SessionNotFoundError

from code_analysis_client import SessionNotFoundError
from mcp_proxy_adapter.core.errors import ValidationError

from ai_editor.commands.file_open_command import FileOpenCommand
from ai_editor.commands.session_connect_command import SessionConnectCommand
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.commands.formatter_commands_command import FormatterCommandsCommand
from ai_editor.contracts import ErrorCode


def _write_session(base: Path, session_key: str, ca_session_id: str) -> None:
    session_dir = base / session_key
    session_dir.mkdir(parents=True)
    (session_dir / "git").mkdir()
    settings = {
        "session_key": session_key,
        "ca_session_id": ca_session_id,
        "readonly": False,
        "open_buffers": [],
    }
    import json

    (session_dir / "ses_settings.json").write_text(json.dumps(settings), encoding="utf-8")


@pytest.fixture
def session_env(tmp_path: Path) -> tuple[MagicMock, str, str]:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    ca_session_id = "ca-session-123"
    _write_session(tmp_path, session_key, ca_session_id)

    ca_client = MagicMock()
    ca_client.assert_session_exists = MagicMock()
    manager = MagicMock()
    manager.base_dir = str(tmp_path)
    manager.ca_client = ca_client
    return manager, session_key, ca_session_id


def test_editor_session_command_checks_ca_session(session_env: tuple[MagicMock, str, str]) -> None:
    manager, session_key, ca_session_id = session_env
    cmd = FileOpenCommand()
    params = {
        "session_key": session_key,
        "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362",
        "file_path": "src/main.py",
    }

    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        validated = cmd.validate_params(params)

    manager.ca_client.assert_session_exists.assert_called_once_with(ca_session_id)
    assert validated["session_key"] == session_key


def test_editor_session_command_rejects_missing_local_session(session_env: tuple[MagicMock, str, str]) -> None:
    manager, _, _ = session_env
    cmd = FileOpenCommand()
    params = {
        "session_key": "00000000-0000-0000-0000-000000000000",
        "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362",
        "file_path": "src/main.py",
    }

    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with pytest.raises(ValueError, match=ErrorCode.SESSION_NOT_FOUND.value):
            cmd.validate_params(params)


def test_editor_session_command_rejects_dead_ca_session(session_env: tuple[MagicMock, str, str]) -> None:
    manager, session_key, _ = session_env
    manager.ca_client.assert_session_exists.side_effect = SessionNotFoundError(
        "SESSION_NOT_FOUND", field="session_id", details={}
    )
    cmd = FileOpenCommand()
    params = {
        "session_key": session_key,
        "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362",
        "file_path": "src/main.py",
    }

    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with pytest.raises(ValueError, match=ErrorCode.SESSION_NOT_FOUND.value):
            cmd.validate_params(params)


def _ca_client() -> MagicMock:
    return MagicMock(spec=CodeAnalysisClient)


def test_session_connect_requires_ca_session_id() -> None:
    cmd = SessionConnectCommand()
    with pytest.raises(ValidationError, match="ca_session_id"):
        cmd.validate_params({"readonly": False})


def test_session_connect_verifies_ca_session_via_client() -> None:
    cmd = SessionConnectCommand()
    ca_client = _ca_client()
    manager = MagicMock()
    manager.ca_client = ca_client
    ca_id = "3b82630d-55b2-4fd2-867f-6b4b2d580fbf"

    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        validated = cmd.validate_params({"ca_session_id": ca_id})

    ca_client.assert_session_exists.assert_called_once_with(ca_id)
    assert validated["ca_session_id"] == ca_id


def test_session_connect_rejects_unknown_ca_session() -> None:
    cmd = SessionConnectCommand()
    ca_client = _ca_client()
    ca_client.assert_session_exists.side_effect = SessionNotFoundError(
        "SESSION_NOT_FOUND", field="session_id", details={}
    )
    manager = MagicMock()
    manager.ca_client = ca_client

    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with pytest.raises(ValueError, match=ErrorCode.SESSION_NOT_FOUND.value):
            cmd.validate_params({"ca_session_id": "00000000-0000-0000-0000-000000000000"})


def test_session_connect_skips_editor_session_precheck() -> None:
    cmd = SessionConnectCommand()
    ca_client = _ca_client()
    manager = MagicMock()
    manager.ca_client = ca_client
    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with patch("ai_editor.commands._session_validation.ensure_ca_session_alive") as ensure:
            cmd.validate_params({"ca_session_id": "3b82630d-55b2-4fd2-867f-6b4b2d580fbf"})
    ensure.assert_not_called()


def test_formatter_commands_skips_ca_precheck() -> None:
    cmd = FormatterCommandsCommand()
    with patch("ai_editor.commands._session_validation.ensure_ca_session_alive") as ensure:
        cmd.validate_params({"formatter": "yaml"})
    ensure.assert_not_called()
