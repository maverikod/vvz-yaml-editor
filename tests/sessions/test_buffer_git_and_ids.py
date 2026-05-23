"""Tests for git commits, stable IDs, and file_get content."""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

from ai_editor.formatters.text.formatter import TextFormatter
from ai_editor.session_manager import SessionManager
from ai_editor.sessions.buffer_api import get_buffer_file_content, get_buffer_state, new_buffer
from ai_editor.sessions.session_dir import buffer_file_path, create_session_dir
from ai_editor.sessions.session_git import get_repo


def _line_ids(preview: str) -> list[str]:
    return re.findall(r"\[([0-9a-f-]{36})\] line:", preview)


def test_git_commit_after_file_create(tmp_path: Path) -> None:
    session_key = "git-commit-test"
    create_session_dir(tmp_path, session_key)
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    repo = get_repo(tmp_path / session_key)

    result = new_buffer(
        tmp_path,
        session_key,
        registry,
        initial_content="hello git\n",
        display_name="hello.txt",
        repo_map={"_session": repo},
    )

    buffer_id = result["buffer_id"]
    repo = get_repo(tmp_path / session_key)
    log = repo.git.log("--oneline", "--all").splitlines()
    assert any("new:" in line for line in log), log
    buf_path = buffer_file_path(tmp_path / session_key, buffer_id)
    assert buf_path.is_file()
    assert str(buf_path).startswith(str(tmp_path / session_key / "buffers"))


def test_file_create_and_get_state_share_line_ids(tmp_path: Path) -> None:
    session_key = "stable-id-test"
    create_session_dir(tmp_path, session_key)
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    repo = get_repo(tmp_path / session_key)

    created = new_buffer(
        tmp_path,
        session_key,
        registry,
        initial_content="stable id test\n",
        display_name="stable.txt",
        repo_map={"_session": repo},
    )
    create_view = created.get("view", "")
    create_ids = _line_ids(create_view)

    state = get_buffer_state(
        tmp_path,
        session_key,
        created["buffer_id"],
        MagicMock(),
        registry,
    )
    state_ids = _line_ids(state.preview)

    assert create_ids
    assert create_ids == state_ids


def test_get_buffer_file_content_reads_buf(tmp_path: Path) -> None:
    session_key = "file-get-test"
    session_dir = create_session_dir(tmp_path, session_key)
    buffer_id = "buf-read-1"
    buf_path = buffer_file_path(session_dir, buffer_id)
    buf_path.write_text("file get payload\n", encoding="utf-8")
    settings = {
        "session_key": session_key,
        "ca_session_id": session_key,
        "open_buffers": [
            {
                "buffer_id": buffer_id,
                "relative_path": "tmp/read.txt",
                "file_type": "remote",
                "modified": False,
                "buf_file_path": str(buf_path),
                "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362",
            }
        ],
    }
    (session_dir / "ses_settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )

    result = get_buffer_file_content(tmp_path, session_key, buffer_id, lock=False)

    assert result["success"] is True
    assert result["content"] == "file get payload\n"
    assert result["relative_path"] == "tmp/read.txt"


def test_git_commit_after_mutate_and_undo(tmp_path: Path) -> None:
    session_key = "mutate-git-test"
    create_session_dir(tmp_path, session_key)
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    sm = SessionManager(str(tmp_path), MagicMock(), registry)

    created = sm.new_buffer(
        session_key,
        initial_content="before mutate\n",
        display_name="mut.txt",
    )
    buffer_id = created["buffer_id"]
    sm.repo_map.clear()

    state = sm.get_buffer_state(session_key, buffer_id)
    line_id = _line_ids(state.preview)[0]
    mutate = sm.mutate_batch(
        session_key,
        buffer_id,
        [{"op": "replace_node", "address": line_id, "content": "after mutate\n"}],
    )
    assert mutate.success is True

    repo = get_repo(tmp_path / session_key)
    branch_log = repo.git.log("--oneline", f"buf/{buffer_id}").splitlines()
    assert any("new:" in line for line in branch_log), branch_log
    assert any("mutate_batch" in line for line in branch_log), branch_log

    undo = sm.undo(session_key, buffer_id)
    assert undo.success is True
    buf_path = buffer_file_path(tmp_path / session_key, buffer_id)
    assert buf_path.read_text(encoding="utf-8") == "before mutate\n"
