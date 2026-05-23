"""Tests for in-place mutation persistence."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import git

from ai_editor.formatters.text.formatter import TextFormatter
from ai_editor.session_manager import SessionManager


def test_mutate_batch_sets_modified_for_inplace_tree(tmp_path: Path) -> None:
    session_key = "dcc7e6ca-f244-472a-9f00-62495cf6d916"
    buffer_id = "121b06a0-edcf-4b16-90a1-7d5277a6efdd"
    session_dir = tmp_path / session_key
    session_dir.mkdir()
    buf_path = session_dir / f"{buffer_id}.txt"
    buf_path.write_text("hello\n", encoding="utf-8")
    settings = {
        "session_key": session_key,
        "ca_session_id": session_key,
        "open_buffers": [
            {
                "buffer_id": buffer_id,
                "relative_path": "tmp/test.txt",
                "file_type": "remote",
                "modified": False,
                "saved": True,
                "readonly": False,
                "formatter": "text",
                "buf_file_path": str(buf_path),
                "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362",
                "filename": "test.txt",
                "redo_stack": [],
            }
        ],
    }
    (session_dir / "ses_settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )
    repo = git.Repo.init(session_dir)

    mgr = SessionManager(
        tmp_path,
        MagicMock(),
        MagicMock(),
        editor_server_uuid="550e8400-e29b-41d4-a716-446655440000",
    )
    mgr.repo_map[buffer_id] = repo

    fmt = TextFormatter()
    tree = fmt.open_tree("hello\n")
    line_id = tree.root.children[0].children[0].stable_id
    mgr._buffer_cache[f"{session_key}:{buffer_id}"] = (fmt, tree)

    result = mgr.mutate_batch(
        session_key,
        buffer_id,
        [{"op": "replace_node", "address": line_id, "content": "updated"}],
    )

    assert result.success is True
    assert buf_path.read_text(encoding="utf-8") == "updated\n"
    updated = json.loads((session_dir / "ses_settings.json").read_text(encoding="utf-8"))
    assert updated["open_buffers"][0]["modified"] is True
