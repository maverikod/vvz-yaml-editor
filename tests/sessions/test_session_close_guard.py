"""Tests for session_close guard on unsaved buffers."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_editor.contracts import ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.buffer_close import close_session
from ai_editor.sessions.session_api import close_session_api
from ai_editor.sessions.session_dir import create_session_dir

EDITOR_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _write_session_with_modified_buffer(tmp_path: Path, session_key: str) -> None:
    session_dir = tmp_path / session_key
    session_dir.mkdir()
    settings = {
        "session_key": session_key,
        "ca_session_id": session_key,
        "subordinate_server_uuid": EDITOR_UUID,
        "open_buffers": [
            {
                "buffer_id": "buf-1",
                "relative_path": None,
                "file_type": "local",
                "modified": True,
                "saved": False,
                "readonly": False,
                "filename": "test.txt",
                "project_id": "",
                "buf_file_path": str(session_dir / "buf-1.txt"),
            }
        ],
    }
    (session_dir / "ses_settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )


def test_close_session_api_rejects_modified_buffers_without_force(tmp_path: Path) -> None:
    session_key = "a6ce13b1-fecf-4c93-921d-de7c72fd2579"
    _write_session_with_modified_buffer(tmp_path, session_key)
    ca_client = MagicMock(spec=CodeAnalysisClient)

    result = close_session_api(tmp_path, session_key, ca_client, force=False)

    assert result.success is False
    assert result.error_code == ErrorCode.SESSION_HAS_UNSAVED_BUFFERS
    assert (tmp_path / session_key).is_dir()
    ca_client.delete_subordinate_session.assert_not_called()


def test_close_session_api_force_closes_modified_buffers(tmp_path: Path) -> None:
    session_key = "a6ce13b1-fecf-4c93-921d-de7c72fd2579"
    _write_session_with_modified_buffer(tmp_path, session_key)
    ca_client = MagicMock(spec=CodeAnalysisClient)

    result = close_session_api(tmp_path, session_key, ca_client, force=True)

    assert result.session_key == session_key
    assert not (tmp_path / session_key).exists()
    ca_client.delete_subordinate_session.assert_called_once()


def test_close_session_removes_git_with_session_dir(tmp_path: Path) -> None:
    session_key = "git-teardown"
    session_dir = create_session_dir(tmp_path, session_key)
    assert (session_dir / "git").is_dir()
    ca_client = MagicMock(spec=CodeAnalysisClient)

    result = close_session(session_dir, session_key, ca_client, force=True)

    assert result.success is True
    assert not session_dir.exists()
    assert not (tmp_path / session_key / "git").exists()
