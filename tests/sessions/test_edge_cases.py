"""Edge-case tests: undo/redo limits, close guards, locks, missing files."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_editor.contracts import ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.formatters.text.formatter import TextFormatter
from ai_editor.session_manager import SessionManager
from ai_editor.sessions.buffer_api import close_buffer, open_buffer as open_buffer_api
from ai_editor.sessions.buffer_close import close_buffer as close_buffer_impl, close_session
from ai_editor.sessions.session_dir import buffer_file_path, create_session_dir
from ai_editor.sessions.session_git import get_repo

EDITOR_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _line_ids(preview: str) -> list[str]:
    return re.findall(r"\[([0-9a-f-]{36})\] line:", preview)


def _write_remote_buffer(
    session_dir: Path,
    *,
    buffer_id: str = "remote-buf",
    modified: bool = True,
    saved: bool = False,
    readonly: bool = False,
    lock_session_id: str | None = "ca-sess",
) -> None:
    buf_path = buffer_file_path(session_dir, buffer_id)
    buf_path.write_text("remote content\n", encoding="utf-8")
    settings = {
        "session_key": session_dir.name,
        "ca_session_id": session_dir.name,
        "subordinate_server_uuid": EDITOR_UUID,
        "open_buffers": [
            {
                "buffer_id": buffer_id,
                "relative_path": "tmp/remote.txt",
                "file_type": "remote",
                "modified": modified,
                "saved": saved,
                "readonly": readonly,
                "filename": "remote.txt",
                "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362",
                "file_id": "file-uuid-1",
                "lock_session_id": lock_session_id,
                "buf_file_path": str(buf_path),
            }
        ],
    }
    (session_dir / "ses_settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )


def test_undo_at_beginning_after_all_mutations_reverted(tmp_path: Path) -> None:
    session_key = "undo-boundary"
    create_session_dir(tmp_path, session_key)
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    sm = SessionManager(str(tmp_path), MagicMock(), registry)

    created = sm.new_buffer(
        session_key,
        initial_content="original\n",
        display_name="edge.txt",
    )
    buffer_id = created["buffer_id"]
    line_id = _line_ids(created.get("view", ""))[0]
    sm.mutate_batch(
        session_key,
        buffer_id,
        [{"op": "replace_node", "address": line_id, "content": "changed\n"}],
    )
    sm.undo(session_key, buffer_id)

    at_beginning = sm.undo(session_key, buffer_id)

    assert at_beginning.success is False
    assert at_beginning.error_code == ErrorCode.UNDO_AT_BEGINNING


def test_redo_at_end_on_empty_stack(tmp_path: Path) -> None:
    session_key = "redo-boundary"
    create_session_dir(tmp_path, session_key)
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    sm = SessionManager(str(tmp_path), MagicMock(), registry)
    created = sm.new_buffer(
        session_key,
        initial_content="x\n",
        display_name="x.txt",
    )
    buffer_id = created["buffer_id"]

    result = sm.redo(session_key, buffer_id)

    assert result.success is False
    assert result.error_code == ErrorCode.REDO_AT_END


def test_close_buffer_rejects_unsent_remote_changes(tmp_path: Path) -> None:
    session_key = "close-unsent"
    session_dir = create_session_dir(tmp_path, session_key)
    _write_remote_buffer(session_dir, modified=True, saved=False)
    ca_client = MagicMock(spec=CodeAnalysisClient)
    repo = get_repo(session_dir)

    result = close_buffer_impl(
        session_dir,
        "remote-buf",
        MagicMock(),
        ca_client,
        repo,
        force=False,
    )

    assert result.success is False
    assert result.error_code == ErrorCode.FILE_HAS_UNSENT_CHANGES
    assert (session_dir / "ses_settings.json").exists()


def test_close_buffer_force_discards_unsent_remote(tmp_path: Path) -> None:
    session_key = "close-force"
    session_dir = create_session_dir(tmp_path, session_key)
    _write_remote_buffer(session_dir, modified=True, saved=False)
    ca_client = MagicMock(spec=CodeAnalysisClient)
    repo = get_repo(session_dir)

    result = close_buffer_impl(
        session_dir,
        "remote-buf",
        MagicMock(),
        ca_client,
        repo,
        force=True,
    )

    assert result.success is True
    settings = json.loads((session_dir / "ses_settings.json").read_text())
    assert settings["open_buffers"] == []
    ca_client.unlock_file.assert_called_once()


def test_close_session_rejects_modified_local_buffer(tmp_path: Path) -> None:
    session_key = "sess-modified"
    session_dir = create_session_dir(tmp_path, session_key)
    buf_path = buffer_file_path(session_dir, "local-buf")
    buf_path.write_text("dirty\n", encoding="utf-8")
    settings = {
        "session_key": session_key,
        "ca_session_id": session_key,
        "open_buffers": [
            {
                "buffer_id": "local-buf",
                "relative_path": None,
                "file_type": "local",
                "modified": True,
                "saved": False,
                "readonly": False,
                "filename": "dirty.txt",
                "project_id": "",
                "buf_file_path": str(buf_path),
            }
        ],
    }
    (session_dir / "ses_settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )
    ca_client = MagicMock(spec=CodeAnalysisClient)

    result = close_session(session_dir, session_key, ca_client, force=False)

    assert result.success is False
    assert result.error_code == ErrorCode.SESSION_HAS_UNSAVED_BUFFERS
    assert session_dir.is_dir()


def test_close_session_rejects_unsent_remote_without_force(tmp_path: Path) -> None:
    session_key = "sess-unsent-remote"
    session_dir = create_session_dir(tmp_path, session_key)
    _write_remote_buffer(session_dir, modified=False, saved=False)
    ca_client = MagicMock(spec=CodeAnalysisClient)

    result = close_session(session_dir, session_key, ca_client, force=False)

    assert result.success is False
    assert result.error_code == ErrorCode.SESSION_HAS_UNSENT_FILES
    assert session_dir.is_dir()


def test_open_buffer_file_not_found(tmp_path: Path) -> None:
    session_key = "missing-file"
    session_dir = create_session_dir(tmp_path, session_key)
    ca_client = MagicMock(spec=CodeAnalysisClient)
    ca_client.download_content.side_effect = RuntimeError("file not found in project")
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    registry.get_by_extension.return_value = TextFormatter

    result = open_buffer_api(
        tmp_path,
        session_key,
        "84ec55c8-cefd-480d-beb6-fa1d35e60362",
        "tmp/does_not_exist.txt",
        ca_client,
        registry,
    )

    assert result["success"] is False
    assert result["error_code"] == ErrorCode.PATH_NOT_FOUND


def test_open_buffer_lock_not_verified(tmp_path: Path) -> None:
    session_key = "lock-missing"
    session_dir = create_session_dir(tmp_path, session_key)
    ca_client = MagicMock(spec=CodeAnalysisClient)
    ca_client.download_content.return_value = (b"locked file\n", "file-99")
    ca_client.list_file_locks.return_value = []
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    registry.get_by_extension.return_value = TextFormatter

    result = open_buffer_api(
        tmp_path,
        session_key,
        "84ec55c8-cefd-480d-beb6-fa1d35e60362",
        "tmp/locked.txt",
        ca_client,
        registry,
        readonly=False,
    )

    assert result["success"] is False
    assert result["error_code"] == ErrorCode.SESSION_LOCK_CONFLICT


def test_mutate_remote_buffer_clears_saved_flag(tmp_path: Path) -> None:
    session_key = "remote-saved-flag"
    session_dir = create_session_dir(tmp_path, session_key)
    _write_remote_buffer(session_dir, modified=False, saved=True)
    fmt = TextFormatter()
    tree = fmt.open_tree("remote content\n")
    line_id = tree.root.children[0].children[0].stable_id
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    sm = SessionManager(str(tmp_path), MagicMock(), registry)
    sm._buffer_cache[f"{session_key}:remote-buf"] = (fmt, tree)

    sm.mutate_batch(
        session_key,
        "remote-buf",
        [{"op": "replace_node", "address": line_id, "content": "changed remote\n"}],
    )

    settings = json.loads((session_dir / "ses_settings.json").read_text())
    buf = settings["open_buffers"][0]
    assert buf["modified"] is True
    assert buf["saved"] is False


def test_close_buffer_unknown_id(tmp_path: Path) -> None:
    session_key = "unknown-buf"
    session_dir = create_session_dir(tmp_path, session_key)
    ca_client = MagicMock(spec=CodeAnalysisClient)

    result = close_buffer(
        tmp_path,
        session_key,
        "00000000-0000-0000-0000-000000000000",
        ca_client,
    )

    assert result.success is False
    assert result.error_code == ErrorCode.BUFFER_NOT_FOUND
