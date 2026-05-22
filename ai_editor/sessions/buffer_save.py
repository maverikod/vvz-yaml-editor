"""Explicit save via save pipeline and CA upload."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import ErrorCode, OperationResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.save_pipeline import run_save_as_pipeline, run_save_pipeline
from ai_editor.sessions.session_dir import (
    read_session_settings,
    remove_buffer_from_settings,
    update_buffer_in_settings,
)
from ai_editor.sessions.session_git import commit_buffer, delete_buffer_branch


def save_buffer(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    document: Any,
    ca_client: CodeAnalysisClient,
    repo: Any,
    *,
    close: bool = False,
) -> OperationResult:
    """Save buffer to CA; optional unlock+close when close=True."""
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
    rel = buf.get("relative_path")
    if not rel:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_INVALID,
            message="unsaved local buffer",
        )
    result = run_save_pipeline(
        formatter,
        document,
        rel,
        ca_client,
        buf["project_id"],
        buf.get("file_id"),
        commit_message=f"ai_editor: save {rel}",
    )
    if not result.success:
        return result
    update_buffer_in_settings(
        session_dir, buffer_id, {"modified": False, "saved": True}
    )
    if close and buf.get("lock_session_id") and buf.get("file_id"):
        ca_client.unlock_file(
            buf["lock_session_id"], buf["project_id"], buf["file_id"]
        )
        delete_buffer_branch(repo, buffer_id)
        remove_buffer_from_settings(session_dir, buffer_id)
    return result


def save_as_buffer(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    document: Any,
    ca_client: CodeAnalysisClient,
    new_relative_path: str,
    overwrite: bool = False,
    repo: Any | None = None,
) -> OperationResult:
    """Save buffer content to a new project path."""
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
    result = run_save_as_pipeline(
        formatter,
        document,
        new_relative_path,
        ca_client,
        buf["project_id"],
        overwrite,
    )
    if result.success:
        update_buffer_in_settings(
            session_dir,
            buffer_id,
            {
                "relative_path": new_relative_path,
                "modified": False,
                "saved": True,
                "file_type": "remote",
            },
        )
    return result
