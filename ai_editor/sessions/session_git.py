"""Session-scoped git repository for per-buffer undo history."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import git
from git import Repo

from ai_editor.contracts import Diagnostic, ErrorCode

logger = logging.getLogger(__name__)

DEFAULT_BRANCH = "master"
_GIT_DIR_NAME = "git"


def _head_names(repo: Repo) -> list[str]:
    return [h.name for h in repo.heads]


def _initial_commit(repo: Repo) -> None:
    """Create the session root commit on DEFAULT_BRANCH."""
    if repo.head.is_valid():
        return
    try:
        repo.index.commit("session: init")
    except Exception:
        repo.git.commit("--allow-empty", "-m", "session: init")


def _normalize_default_branch(repo: Repo) -> None:
    """Ensure DEFAULT_BRANCH exists (migrate legacy main-only repos)."""
    heads = _head_names(repo)
    if DEFAULT_BRANCH in heads:
        if repo.head.is_detached or repo.active_branch.name != DEFAULT_BRANCH:
            repo.git.checkout(DEFAULT_BRANCH)
        return
    if not heads:
        _initial_commit(repo)
        return
    legacy = "main" if "main" in heads else heads[0]
    repo.git.branch("-m", legacy, DEFAULT_BRANCH)
    repo.git.checkout(DEFAULT_BRANCH)


def init_session_git(session_dir: Path) -> Repo:
    """Initialize non-bare git repo under session_dir/git with empty initial commit."""
    git_dir = session_dir / _GIT_DIR_NAME
    git_dir.mkdir(parents=True, exist_ok=True)

    if (git_dir / "HEAD").exists():
        repo = Repo(git_dir)
        _normalize_default_branch(repo)
        return repo

    try:
        repo = Repo.init(git_dir, bare=False, initial_branch=DEFAULT_BRANCH)
    except TypeError:
        repo = Repo.init(git_dir, bare=False)
    _initial_commit(repo)
    _normalize_default_branch(repo)
    return repo


def ensure_session_git(session_dir: Path) -> Repo:
    """Return session git repo, initializing it when missing or empty."""
    git_dir = session_dir / _GIT_DIR_NAME
    if not git_dir.is_dir() or not (git_dir / "HEAD").exists():
        return init_session_git(session_dir)
    repo = Repo(git_dir)
    _normalize_default_branch(repo)
    if not repo.head.is_valid():
        _initial_commit(repo)
        _normalize_default_branch(repo)
    return repo


def destroy_session_git(session_dir: Path) -> None:
    """Remove session git repository from disk."""
    git_dir = session_dir / _GIT_DIR_NAME
    if git_dir.is_dir():
        shutil.rmtree(git_dir, ignore_errors=True)


def get_repo(session_dir: Path) -> Repo:
    """Return existing session git repository."""
    return ensure_session_git(session_dir)


def _branch_name(buffer_id: str) -> str:
    return f"buf/{buffer_id}"


def branch_name(buffer_id: str) -> str:
    """Public alias for buffer branch naming."""
    return _branch_name(buffer_id)


def create_buffer_branch(repo: Repo, buffer_id: str, buf_file_path: Path) -> None:
    """Create branch buf/<buffer_id> tracking buf file (no commit yet)."""
    _normalize_default_branch(repo)
    name = _branch_name(buffer_id)
    if name in _head_names(repo):
        repo.git.checkout(name)
        return
    repo.git.checkout("-b", name)


def _git_add_buf_file(repo: Repo, buf_file_path: Path) -> None:
    """Stage a buffer file that lives inside the session git worktree."""
    work = Path(repo.working_dir).resolve()
    path = buf_file_path.resolve()
    try:
        rel = path.relative_to(work)
    except ValueError as exc:
        raise ValueError(
            f"buffer file {path} is outside git worktree {work}"
        ) from exc
    repo.index.add([str(rel)])


def _git_track_path(session_dir: Path, buffer_id: str, suffix: str) -> Path:
    path = session_dir / _GIT_DIR_NAME / "buffers"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{buffer_id}{suffix}"


def commit_buffer(
    repo: Repo,
    buffer_id: str,
    buf_file_path: Path,
    message: str,
    *,
    session_dir: Path | None = None,
) -> None:
    """Stage buf file and commit on buf/<buffer_id>; fault-tolerant."""
    try:
        name = _branch_name(buffer_id)
        live = Path(buf_file_path)
        track = live
        if session_dir is not None:
            suffix = live.suffix or ".txt"
            track = _git_track_path(session_dir, buffer_id, suffix)
        _normalize_default_branch(repo)
        repo.git.checkout(name)
        if session_dir is not None:
            shutil.copy2(live, track)
        _git_add_buf_file(repo, track)
        commit = repo.index.commit(message)
        repo.heads[name].set_commit(commit)
        _normalize_default_branch(repo)
        if session_dir is not None and track.exists():
            track.unlink()
    except Exception as exc:
        logger.warning("git commit failed: %s", exc)


def delete_buffer_branch(repo: Repo, buffer_id: str) -> None:
    """Delete buf/<buffer_id> branch if present."""
    name = _branch_name(buffer_id)
    if name not in _head_names(repo):
        return
    _normalize_default_branch(repo)
    repo.git.checkout(DEFAULT_BRANCH)
    repo.git.branch("-D", name)


def history_diagnostic(exc: Exception) -> Diagnostic:
    """Build HISTORY_UNAVAILABLE diagnostic (code string, not ErrorCode enum)."""
    return Diagnostic(code="HISTORY_UNAVAILABLE", message=str(exc))
