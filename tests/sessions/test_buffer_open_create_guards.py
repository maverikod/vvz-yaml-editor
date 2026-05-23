"""Tests for duplicate file_open and empty file_create guards."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_editor.contracts import ErrorCode
from ai_editor.formatters.text.formatter import TextFormatter
from ai_editor.sessions.buffer_api import new_buffer, open_buffer
from ai_editor.sessions.session_dir import create_session_dir


def _stub_open_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_open(*args: object, **kwargs: object) -> dict[str, object]:
        return {"success": True, "buffer_id": "remote-buffer-id"}

    monkeypatch.setattr(
        "ai_editor.sessions.buffer_api._open_buffer",
        _fake_open,
    )


def test_open_buffer_rejects_already_open_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_key = "sess-dup-open"
    project_id = "84ec55c8-cefd-480d-beb6-fa1d35e60362"
    file_path = "tmp/already_open.txt"
    session_dir = create_session_dir(tmp_path, session_key)
    settings = {
        "session_key": session_key,
        "ca_session_id": session_key,
        "open_buffers": [
            {
                "buffer_id": "buf-existing",
                "relative_path": file_path,
                "project_id": project_id,
                "file_type": "remote",
            }
        ],
    }
    (session_dir / "ses_settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )
    _stub_open_buffer(monkeypatch)
    ca_client = MagicMock()

    result = open_buffer(
        tmp_path,
        session_key,
        project_id,
        file_path,
        ca_client,
        MagicMock(get_by_name=MagicMock(return_value=TextFormatter)),
    )

    assert result["success"] is False
    assert result["error_code"] == ErrorCode.BUFFER_ALREADY_OPEN
    assert "already open" in result["message"]


def test_new_buffer_rejects_empty_content(tmp_path: Path) -> None:
    session_key = "sess-empty-create"
    create_session_dir(tmp_path, session_key)
    repo = MagicMock()

    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter
    result = new_buffer(
        tmp_path,
        session_key,
        registry,
        initial_content="",
        display_name="empty.txt",
        repo_map={"_session": repo},
    )

    assert result["success"] is False
    assert result["error_code"] == ErrorCode.BUFFER_INVALID


def test_new_buffer_accepts_nonempty_content(tmp_path: Path) -> None:
    session_key = "sess-nonempty-create"
    create_session_dir(tmp_path, session_key)
    import git

    real_repo = git.Repo.init((tmp_path / session_key / "git"), bare=False, initial_branch="master")
    real_repo.index.commit("init")
    repo_map: dict[str, object] = {"_session": real_repo}
    registry = MagicMock()
    registry.get_by_name.return_value = TextFormatter

    result = new_buffer(
        tmp_path,
        session_key,
        registry,
        initial_content="hello\n",
        display_name="hello.txt",
        repo_map=repo_map,
    )

    assert "buffer_id" in result
    settings = json.loads((tmp_path / session_key / "ses_settings.json").read_text())
    assert settings["open_buffers"][0]["modified"] is True
