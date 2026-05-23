"""Session directory layout and ses_settings.json management."""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_editor.sessions.session_git import ensure_session_git

SETTINGS_NAME = "ses_settings.json"
_BUFFERS_LIVE_DIR = "buffers"
_GIT_WORKTREE_DIR = "git"


def buffer_storage_dir(session_dir: Path) -> Path:
    """Directory for live buffer files (outside the git worktree)."""
    path = session_dir / _BUFFERS_LIVE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def buffer_file_path(session_dir: Path, buffer_id: str, suffix: str = ".txt") -> Path:
    """Return live buf file path edited by formatters and mutations."""
    return buffer_storage_dir(session_dir) / f"{buffer_id}{suffix}"


def git_buffer_track_path(session_dir: Path, buffer_id: str, suffix: str = ".txt") -> Path:
    """Return git-worktree copy used for version control commits."""
    path = session_dir / _GIT_WORKTREE_DIR / _BUFFERS_LIVE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{buffer_id}{suffix}"


def git_buffer_relpath(buffer_id: str, suffix: str = ".txt") -> str:
    """Project-relative path of a buffer file inside the session git worktree."""
    return f"{_BUFFERS_LIVE_DIR}/{buffer_id}{suffix}"


def resolve_buffer_file_path(session_dir: Path, buf: dict[str, Any]) -> Path:
    """Resolve live buf file path, falling back to legacy layouts."""
    stored = Path(str(buf.get("buf_file_path") or ""))
    if stored.is_file():
        return stored
    buffer_id = str(buf.get("buffer_id") or "")
    if not buffer_id:
        return stored
    suffix = stored.suffix or ".txt"
    for candidate in (
        buffer_file_path(session_dir, buffer_id, suffix),
        session_dir / _GIT_WORKTREE_DIR / _BUFFERS_LIVE_DIR / f"{buffer_id}{suffix}",
        session_dir / f"{buffer_id}{suffix}",
    ):
        if candidate.is_file():
            return candidate
    return stored if stored else buffer_file_path(session_dir, buffer_id, suffix)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically via tempfile + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        os.close(fd)
        raise
    os.replace(tmp, path)


def create_session_dir(
    base_dir: str | Path,
    session_key: str | None,
    readonly: bool = False,
) -> Path:
    """Create session directory and initial ses_settings.json.

    Args:
        base_dir: Parent directory for all sessions.
        session_key: Existing key or None to allocate UUID4.
        readonly: Session-level readonly flag.

    Returns:
        Path to the new session directory.
    """
    base = Path(base_dir)
    key = session_key or str(uuid.uuid4())
    session_dir = base / key
    session_dir.mkdir(parents=True, exist_ok=True)
    settings: dict[str, Any] = {
        "session_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "readonly": readonly,
        "open_buffers": [],
    }
    _atomic_write_json(session_dir / SETTINGS_NAME, settings)
    ensure_session_git(session_dir)
    return session_dir


def find_open_buffer_for_path(
    settings: dict[str, Any],
    project_id: str,
    file_path: str,
) -> dict[str, Any] | None:
    """Return open buffer already bound to the same project file, if any."""
    from ai_editor.sessions.project_paths import normalize_project_relative_path

    try:
        rel = normalize_project_relative_path(file_path)
    except ValueError:
        return None
    pid = str(project_id or "").strip()
    for buf in settings.get("open_buffers", []):
        buf_rel = str(buf.get("relative_path") or "").strip()
        buf_pid = str(buf.get("project_id") or "").strip()
        if buf_rel == rel and buf_pid == pid:
            return buf
    return None


def read_session_settings(session_dir: Path) -> dict[str, Any]:
    """Load ses_settings.json from session_dir."""
    path = session_dir / SETTINGS_NAME
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_session_settings(session_dir: Path, settings: dict[str, Any]) -> None:
    """Persist ses_settings.json atomically."""
    _atomic_write_json(session_dir / SETTINGS_NAME, settings)


def _find_buffer_index(buffers: list[dict[str, Any]], buffer_id: str) -> int:
    for i, buf in enumerate(buffers):
        if buf.get("buffer_id") == buffer_id:
            return i
    return -1


def add_buffer_to_settings(session_dir: Path, buf_dict: dict[str, Any]) -> None:
    """Append or replace open_buffers entry by buffer_id."""
    settings = read_session_settings(session_dir)
    buffers = settings.setdefault("open_buffers", [])
    idx = _find_buffer_index(buffers, buf_dict["buffer_id"])
    if idx >= 0:
        buffers[idx] = buf_dict
    else:
        buffers.append(buf_dict)
    write_session_settings(session_dir, settings)


def remove_buffer_from_settings(session_dir: Path, buffer_id: str) -> None:
    """Remove buffer from open_buffers."""
    settings = read_session_settings(session_dir)
    buffers = settings.get("open_buffers", [])
    settings["open_buffers"] = [b for b in buffers if b.get("buffer_id") != buffer_id]
    write_session_settings(session_dir, settings)


def update_buffer_in_settings(
    session_dir: Path,
    buffer_id: str,
    updates: dict[str, Any],
) -> None:
    """Merge updates into one open_buffers entry."""
    settings = read_session_settings(session_dir)
    buffers = settings.get("open_buffers", [])
    idx = _find_buffer_index(buffers, buffer_id)
    if idx < 0:
        raise KeyError(f"buffer not found: {buffer_id}")
    buffers[idx] = {**buffers[idx], **updates}
    write_session_settings(session_dir, settings)
