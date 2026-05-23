"""Explicit save via save pipeline and CA upload."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import ErrorCode, OperationResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.save_pipeline import run_save_as_pipeline, run_save_pipeline
from ai_editor.sessions.ca_session import work_ca_session_id
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
    project_id: str | None = None,
    file_path: str | None = None,
    release_lock: bool = False,
) -> OperationResult:
    """Save buffer to CA; optional unlock+close when close=True."""
    from ai_editor.sessions.project_paths import normalize_project_relative_path

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
    bind_updates: dict[str, Any] = {}
    pid = str(buf.get("project_id") or project_id or "").strip()
    rel_raw = str(buf.get("relative_path") or file_path or "").strip()
    if not rel_raw:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_INVALID,
            message="unsaved local buffer",
        )
    try:
        rel = normalize_project_relative_path(rel_raw)
    except ValueError as exc:
        return OperationResult(
            success=False,
            error_code=ErrorCode.WRITE_FAILED,
            message=str(exc),
        )
    if file_path and not str(buf.get("relative_path") or "").strip():
        bind_updates["relative_path"] = rel
        bind_updates["file_type"] = "remote"
    if project_id and not str(buf.get("project_id") or "").strip():
        bind_updates["project_id"] = pid
    if bind_updates:
        update_buffer_in_settings(session_dir, buffer_id, bind_updates)
        buf = {**buf, **bind_updates}
    if not pid:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_INVALID,
            message="project_id is required",
        )
    file_id = str(buf.get("file_id") or "").strip() or None
    if not file_id:
        try:
            file_id = ca_client.resolve_file_id(pid, rel)
        except ValueError:
            file_id = None
    result = run_save_pipeline(
        formatter,
        document,
        rel,
        ca_client,
        pid,
        file_id,
        commit_message=f"ai_editor: save {rel}",
        ca_session_id=work_ca_session_id(settings),
        unlock=release_lock,
    )
    if not result.success:
        return result
    updates: dict[str, Any] = {"modified": False, "saved": True, "file_id": result.file_id}
    if release_lock:
        updates["lock_mode"] = "none"
        updates["lock_session_id"] = None
    update_buffer_in_settings(
        session_dir,
        buffer_id,
        updates,
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
    if not buf.get("project_id"):
        update_buffer_in_settings(
            session_dir,
            buffer_id,
            {"project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362"},
        )
        buf = {**buf, "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362"}
    result = run_save_as_pipeline(
        formatter,
        document,
        new_relative_path,
        ca_client,
        buf["project_id"],
        buf.get("file_id"),
        overwrite,
        ca_session_id=work_ca_session_id(settings),
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
                "file_id": result.file_id,
            },
        )
    return result
