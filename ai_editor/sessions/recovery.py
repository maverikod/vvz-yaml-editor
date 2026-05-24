"""Startup sweep and session reconnect helpers."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.session_dir import (
    SETTINGS_NAME,
    read_session_settings,
    resolve_session_dir,
)

logger = logging.getLogger(__name__)


def release_all_locks_for_session(
    ca_client: CodeAnalysisClient,
    buffers: list[dict[str, Any]],
    allow_foreign_session: bool = False,
) -> None:
    """Best-effort unlock_file per locked buffer."""
    _ = allow_foreign_session
    for buf in buffers:
        lock_id = buf.get("lock_session_id")
        file_id = buf.get("file_id")
        project_id = buf.get("project_id")
        if not lock_id or not file_id or not project_id:
            continue
        try:
            ca_client.unlock_file(lock_id, project_id, file_id)
        except Exception as exc:
            logger.warning("unlock failed: %s", exc)


def startup_sweep(base_dir: str | Path, ca_client: CodeAnalysisClient) -> None:
    """Policy B: drop orphan dirs; release stale locks on valid dirs."""
    base = Path(base_dir)
    if not base.exists():
        return
    for child in base.iterdir():
        if not child.is_dir():
            continue
        settings_path = child / SETTINGS_NAME
        try:
            if not settings_path.exists():
                shutil.rmtree(child, ignore_errors=True)
                continue
            settings = read_session_settings(child)
        except Exception:
            shutil.rmtree(child, ignore_errors=True)
            continue
        buffers = settings.get("open_buffers", [])
        stale = [
            b
            for b in buffers
            if b.get("lock_mode") == "full"
            and not b.get("saved")
            and not b.get("readonly")
            and b.get("lock_session_id")
        ]
        release_all_locks_for_session(ca_client, stale, allow_foreign_session=True)


def reconnect_session(base_dir: str | Path, session_key: str) -> dict[str, Any]:
    """Load ses_settings for existing session directory."""
    session_dir = resolve_session_dir(base_dir, session_key)
    return read_session_settings(session_dir)
