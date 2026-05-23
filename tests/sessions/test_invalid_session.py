"""Tests for closing invalid editor sessions (local exists, CA dead)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from code_analysis_client import SessionNotFoundError

from mcp_proxy_adapter.core.errors import ValidationError

from ai_editor.commands.session_close_invalid_command import SessionCloseInvalidCommand
from ai_editor.contracts import ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.invalid_session import (
    close_invalid_session,
    close_invalid_sessions,
    is_ca_session_dead,
    list_invalid_session_keys,
)


def _write_session(
    base: Path,
    session_key: str,
    ca_session_id: str,
    *,
    editor_ca_session_id: str = "",
    subordinate_server_uuid: str = "",
) -> None:
    session_dir = base / session_key
    session_dir.mkdir(parents=True)
    (session_dir / "git").mkdir()
    settings: dict[str, Any] = {
        "session_key": session_key,
        "ca_session_id": ca_session_id,
        "readonly": False,
        "open_buffers": [],
    }
    if editor_ca_session_id:
        settings["editor_ca_session_id"] = editor_ca_session_id
    if subordinate_server_uuid:
        settings["subordinate_server_uuid"] = subordinate_server_uuid
    (session_dir / "ses_settings.json").write_text(json.dumps(settings), encoding="utf-8")


def _ca_client() -> MagicMock:
    return MagicMock(spec=CodeAnalysisClient)


def test_is_ca_session_dead_when_missing_on_ca() -> None:
    ca_client = _ca_client()
    ca_client.assert_session_exists.side_effect = SessionNotFoundError(
        "SESSION_NOT_FOUND", field="session_id", details={}
    )
    assert is_ca_session_dead(ca_client, "dead-id") is True


def test_is_ca_session_dead_when_present_on_ca() -> None:
    ca_client = _ca_client()
    ca_client.assert_session_exists.return_value = None
    assert is_ca_session_dead(ca_client, "live-id") is False


def test_list_invalid_session_keys(tmp_path: Path) -> None:
    _write_session(tmp_path, "live-key", "ca-live")
    _write_session(tmp_path, "dead-key", "ca-dead")

    ca_client = _ca_client()

    def _assert(session_id: str) -> None:
        if session_id == "ca-dead":
            raise SessionNotFoundError("SESSION_NOT_FOUND", field="session_id", details={})

    ca_client.assert_session_exists.side_effect = _assert

    invalid = list_invalid_session_keys(tmp_path, ca_client)
    assert invalid == ["dead-key"]


def test_close_invalid_session_local_only(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    _write_session(tmp_path, session_key, "ca-dead")

    ca_client = _ca_client()
    ca_client.assert_session_exists.side_effect = SessionNotFoundError(
        "SESSION_NOT_FOUND", field="session_id", details={}
    )

    entry = close_invalid_session(
        tmp_path,
        ca_client,
        session_key,
        mode="local_only",
        force=True,
    )
    assert entry.closed is True
    assert not (tmp_path / session_key).exists()
    ca_client.delete_session.assert_not_called()


def test_close_invalid_session_release_ca(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    parent_id = "ca-parent-123"
    _write_session(
        tmp_path,
        session_key,
        parent_id,
        subordinate_server_uuid="srv-uuid",
    )

    ca_client = _ca_client()
    ca_client.assert_session_exists.side_effect = SessionNotFoundError(
        "SESSION_NOT_FOUND", field="session_id", details={}
    )

    entry = close_invalid_session(
        tmp_path,
        ca_client,
        session_key,
        mode="release_ca",
        force=True,
    )
    assert entry.closed is True
    assert entry.ca_notified is True
    ca_client.delete_subordinate_session.assert_called_once_with(
        parent_id,
        "srv-uuid",
    )
    ca_client.delete_session.assert_not_called()
    assert not (tmp_path / session_key).exists()


def test_close_invalid_session_rejects_live_ca(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    _write_session(tmp_path, session_key, "ca-live")

    ca_client = _ca_client()
    ca_client.assert_session_exists.return_value = None

    entry = close_invalid_session(tmp_path, ca_client, session_key, mode="local_only")
    assert entry.closed is False
    assert entry.skipped is False
    assert entry.skip_reason == "CA_SESSION_ALIVE"
    assert (tmp_path / session_key).exists()


def test_close_invalid_sessions_dry_run(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    _write_session(tmp_path, session_key, "ca-dead")

    ca_client = _ca_client()
    ca_client.assert_session_exists.side_effect = SessionNotFoundError(
        "SESSION_NOT_FOUND", field="session_id", details={}
    )

    result = close_invalid_sessions(
        tmp_path, ca_client, session_key=session_key, dry_run=True
    )
    assert result.success is True
    assert result.closed_count == 0
    assert len(result.results) == 1
    assert (tmp_path / session_key).exists()


def test_session_close_invalid_command_requires_session_key() -> None:
    cmd = SessionCloseInvalidCommand()
    with pytest.raises(ValidationError, match="session_key"):
        cmd.validate_params({"mode": "local_only"})


def test_session_close_invalid_command_rejects_missing_local_session(tmp_path: Path) -> None:
    cmd = SessionCloseInvalidCommand()
    manager = MagicMock()
    manager.base_dir = str(tmp_path)
    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with pytest.raises(ValueError, match=ErrorCode.SESSION_NOT_FOUND.value):
            cmd.validate_params(
                {
                    "session_key": "550e8400-e29b-41d4-a716-446655440000",
                    "mode": "local_only",
                }
            )


def test_session_close_invalid_command_rejects_bad_mode(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    _write_session(tmp_path, session_key, "ca-dead")
    cmd = SessionCloseInvalidCommand()
    manager = MagicMock()
    manager.base_dir = str(tmp_path)
    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with pytest.raises(ValueError, match="mode must be one of"):
            cmd.validate_params({"session_key": session_key, "mode": "bad"})


def test_session_close_invalid_command_skips_ca_precheck(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    _write_session(tmp_path, session_key, "ca-dead")
    cmd = SessionCloseInvalidCommand()
    manager = MagicMock()
    manager.base_dir = str(tmp_path)
    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with patch("ai_editor.commands._session_validation.ensure_ca_session_alive") as ensure:
            cmd.validate_params(
                {"session_key": session_key, "mode": "local_only", "dry_run": True}
            )
    ensure.assert_not_called()
