"""Tests for session-scoped git initialization and branch lifecycle."""
from __future__ import annotations

from pathlib import Path

from ai_editor.sessions.session_dir import buffer_file_path, create_session_dir
from ai_editor.sessions.session_git import (
    DEFAULT_BRANCH,
    commit_buffer,
    create_buffer_branch,
    delete_buffer_branch,
    destroy_session_git,
    ensure_session_git,
    get_repo,
    init_session_git,
)


def test_create_session_dir_inits_git_with_master(tmp_path: Path) -> None:
    session_dir = create_session_dir(tmp_path, "sess-1")
    repo = get_repo(session_dir)
    assert DEFAULT_BRANCH in [h.name for h in repo.heads]
    assert repo.head.is_valid()


def test_delete_buffer_branch_returns_to_master(tmp_path: Path) -> None:
    session_dir = create_session_dir(tmp_path, "sess-2")
    repo = init_session_git(session_dir)
    buffer_id = "abc-123"
    buf_path = buffer_file_path(session_dir, buffer_id, ".txt")
    buf_path.write_text("hello", encoding="utf-8")
    create_buffer_branch(repo, buffer_id, buf_path)
    commit_buffer(repo, buffer_id, buf_path, "open: test", session_dir=session_dir)
    delete_buffer_branch(repo, buffer_id)
    assert DEFAULT_BRANCH in [h.name for h in repo.heads]
    assert f"buf/{buffer_id}" not in [h.name for h in repo.heads]
    assert repo.active_branch.name == DEFAULT_BRANCH


def test_ensure_session_git_repairs_empty_git_dir(tmp_path: Path) -> None:
    session_dir = tmp_path / "orphan"
    session_dir.mkdir()
    (session_dir / "git").mkdir()
    repo = ensure_session_git(session_dir)
    assert DEFAULT_BRANCH in [h.name for h in repo.heads]


def test_ensure_session_git_migrates_main_to_master(tmp_path: Path) -> None:
    from git import Repo

    session_dir = tmp_path / "legacy"
    git_dir = session_dir / "git"
    repo = Repo.init(git_dir, bare=False, initial_branch="main")
    repo.index.commit("legacy init")
    repo = ensure_session_git(session_dir)
    assert DEFAULT_BRANCH in [h.name for h in repo.heads]
    assert "main" not in [h.name for h in repo.heads]


def test_destroy_session_git_removes_git_dir(tmp_path: Path) -> None:
    session_dir = create_session_dir(tmp_path, "sess-3")
    git_dir = session_dir / "git"
    assert git_dir.is_dir()
    destroy_session_git(session_dir)
    assert not git_dir.exists()
    assert session_dir.is_dir()
    assert (session_dir / "ses_settings.json").is_file()
