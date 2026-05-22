"""Session-scoped git repository for per-buffer undo history."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import git
from git import Repo

from ai_editor.contracts import Diagnostic, ErrorCode

logger = logging.getLogger(__name__)


def init_session_git(session_dir: Path) -> Repo:
    """Initialize non-bare git repo under session_dir/git with empty initial commit."""
    git_dir = session_dir / "git"
    git_dir.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(git_dir, bare=False)
    if not repo.head.is_valid():
        repo.index.commit("session: init", allow_empty=True)
    return repo


def get_repo(session_dir: Path) -> Repo:
    """Return existing session git repository."""
    return Repo(session_dir / "git")


def _branch_name(buffer_id: str) -> str:
    return f"buf/{buffer_id}"


def branch_name(buffer_id: str) -> str:
    """Public alias for buffer branch naming."""
    return _branch_name(buffer_id)


def create_buffer_branch(repo: Repo, buffer_id: str, buf_file_path: Path) -> None:
    """Create branch buf/<buffer_id> tracking buf file (no commit yet)."""
    name = _branch_name(buffer_id)
    if name in [h.name for h in repo.heads]:
        repo.git.checkout(name)
        return
    repo.git.checkout("-b", name)


def commit_buffer(
    repo: Repo,
    buffer_id: str,
    buf_file_path: Path,
    message: str,
) -> None:
    """Stage buf file and commit on buf/<buffer_id>; fault-tolerant."""
    try:
        name = _branch_name(buffer_id)
        repo.git.checkout(name)
        repo.index.add([str(buf_file_path)])
        commit = repo.index.commit(message)
        repo.heads[name].set_commit(commit)
    except Exception as exc:
        logger.warning("git commit failed: %s", exc)


def delete_buffer_branch(repo: Repo, buffer_id: str) -> None:
    """Delete buf/<buffer_id> branch if present."""
    name = _branch_name(buffer_id)
    if name not in [h.name for h in repo.heads]:
        return
    repo.git.checkout("master")
    repo.git.branch("-D", name)


def history_diagnostic(exc: Exception) -> Diagnostic:
    """Build HISTORY_UNAVAILABLE diagnostic (code string, not ErrorCode enum)."""
    return Diagnostic(code="HISTORY_UNAVAILABLE", message=str(exc))
