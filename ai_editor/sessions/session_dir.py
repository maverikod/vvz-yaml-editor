"""Session directory layout and ses_settings.json management."""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SETTINGS_NAME = "ses_settings.json"


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
    (session_dir / "git").mkdir(exist_ok=True)
    settings: dict[str, Any] = {
        "session_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "readonly": readonly,
        "open_buffers": [],
    }
    _atomic_write_json(session_dir / SETTINGS_NAME, settings)
    return session_dir


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
