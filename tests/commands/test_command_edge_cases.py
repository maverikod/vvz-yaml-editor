"""Command-layer edge cases: schema and semantic validation failures."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mcp_proxy_adapter.core.errors import ValidationError

from ai_editor.commands.buf_undo_command import BufUndoCommand
from ai_editor.commands.file_create_command import FileCreateCommand
from ai_editor.commands.file_open_command import FileOpenCommand
from ai_editor.contracts import ErrorCode


def _session_manager(base: Path, session_key: str, ca_session_id: str) -> MagicMock:
    session_dir = base / session_key
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "git").mkdir(exist_ok=True)
    import json

    (session_dir / "ses_settings.json").write_text(
        json.dumps(
            {
                "session_key": session_key,
                "ca_session_id": ca_session_id,
                "readonly": False,
                "open_buffers": [],
            }
        ),
        encoding="utf-8",
    )
    ca_client = MagicMock()
    ca_client.assert_session_exists = MagicMock()
    manager = MagicMock()
    manager.base_dir = str(base)
    manager.ca_client = ca_client
    return manager


def test_file_open_rejects_missing_required_params() -> None:
    cmd = FileOpenCommand()
    with pytest.raises(ValidationError):
        cmd.validate_params({"session_key": "550e8400-e29b-41d4-a716-446655440000"})


def test_file_create_rejects_empty_content(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    manager = _session_manager(tmp_path, session_key, "ca-1")
    cmd = FileCreateCommand()

    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with pytest.raises(ValidationError):
            cmd.validate_params(
                {
                    "session_key": session_key,
                    "content": "",
                    "display_name": "empty.txt",
                }
            )


def test_buf_undo_rejects_missing_buffer_id(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    manager = _session_manager(tmp_path, session_key, "ca-1")
    cmd = BufUndoCommand()

    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with pytest.raises(ValidationError):
            cmd.validate_params({"session_key": session_key})


def test_file_open_rejects_unknown_project_id_format(tmp_path: Path) -> None:
    session_key = "550e8400-e29b-41d4-a716-446655440000"
    manager = _session_manager(tmp_path, session_key, "ca-1")
    cmd = FileOpenCommand()

    with patch("ai_editor.api_init.get_session_manager", return_value=manager):
        with pytest.raises(ValueError, match=ErrorCode.SESSION_NOT_FOUND.value):
            cmd.validate_params(
                {
                    "session_key": "00000000-0000-0000-0000-000000000000",
                    "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362",
                    "file_path": "tmp/x.txt",
                }
            )
