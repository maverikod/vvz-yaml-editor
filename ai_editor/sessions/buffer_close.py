"""Close single buffer or entire session."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from ai_editor.contracts import ErrorCode, OperationResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.session_dir import read_session_settings, remove_buffer_from_settings
from ai_editor.sessions.session_git import delete_buffer_branch

logger = logging.getLogger(__name__)


def _release_locks(ca_client: CodeAnalysisClient, buffers: list[dict[str, Any]]) -> None:
    """Best-effort unlock_file for session close."""
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


def _cleanup_buffer_files(session_dir: Path, buf_meta: dict[str, Any]) -> None:
    """Remove buf file and generic/cst sidecar artifacts."""
    buf_path = Path(buf_meta["buf_file_path"])
    if buf_path.exists():
        buf_path.unlink()
    buffer_id = buf_meta["buffer_id"]
    for pattern in (f"{buffer_id}.tree", f"{buffer_id}.cst"):
        side = session_dir / pattern
        if side.exists():
            side.unlink()


def close_buffer(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    ca_client: CodeAnalysisClient,
    repo: Any,
    force: bool = False,
) -> OperationResult:
    """Close one buffer; unlock advisory lock when required."""
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_NOT_FOUND,
            message=buffer_id,
        )
    if (
        buf.get("file_type") == "remote"
        and not buf.get("saved")
        and buf.get("modified")
        and not force
        and not buf.get("readonly")
    ):
        return OperationResult(
            success=False,
            error_code=ErrorCode.FILE_HAS_UNSENT_CHANGES,
            message="unsent changes",
        )
    _cleanup_buffer_files(session_dir, buf)
    delete_buffer_branch(repo, buffer_id)
    if (
        buf.get("lock_session_id")
        and buf.get("file_id")
        and not buf.get("saved")
    ):
        try:
            ca_client.unlock_file(
                buf["lock_session_id"], buf["project_id"], buf["file_id"]
            )
        except Exception as exc:
            logger.warning("unlock failed: %s", exc)
    remove_buffer_from_settings(session_dir, buffer_id)
    return OperationResult(success=True, message="closed")


def close_session(
    session_dir: str | Path,
    session_key: str,
    ca_client: CodeAnalysisClient,
    force: bool = False,
) -> OperationResult:
    """Close session directory after checks and lock release."""
    path = Path(session_dir)
    settings = read_session_settings(path)
    if not force:
        for buf in settings.get("open_buffers", []):
            if buf.get("readonly"):
                continue
            if buf.get("modified"):
                return OperationResult(
                    success=False,
                    error_code=ErrorCode.SESSION_HAS_UNSAVED_BUFFERS,
                    message="modified buffers remain",
                )
            if buf.get("file_type") == "remote" and not buf.get("saved"):
                return OperationResult(
                    success=False,
                    error_code=ErrorCode.SESSION_HAS_UNSENT_FILES,
                    message="unsent remote files",
                )
    _release_locks(ca_client, settings.get("open_buffers", []))
    shutil.rmtree(path, ignore_errors=True)
    return OperationResult(success=True, message="session closed")
