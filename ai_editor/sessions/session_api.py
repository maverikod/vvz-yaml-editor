"""Public session API for command layer."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ai_editor.contracts import BufferDescriptor, ErrorCode, OperationResult, SessionDescriptor
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.registry import FormatterRegistry
from ai_editor.sessions.ca_session import (
    EDITOR_SUBORDINATE_COMMENT,
    register_editor_subordinate,
    verify_ca_session,
)
from ai_editor.sessions.recovery import reconnect_session
from ai_editor.sessions.session_dir import (
    SETTINGS_NAME,
    create_session_dir,
    read_session_settings,
    write_session_settings,
)
from ai_editor.sessions.session_git import ensure_session_git


def _settings_to_descriptor(settings: dict[str, Any]) -> SessionDescriptor:
    """Map ses_settings open_buffers to public BufferDescriptor list."""
    session_key = settings["session_key"]
    open_buffers: list[BufferDescriptor] = []
    for buf in settings.get("open_buffers", []):
        open_buffers.append(
            BufferDescriptor(
                buffer_id=buf["buffer_id"],
                session_key=session_key,
                filename=buf.get("filename", ""),
                relative_path=buf.get("relative_path"),
                formatter=buf.get("formatter", ""),
                project_id=buf.get("project_id", ""),
                modified=bool(buf.get("modified")),
                readonly=bool(buf.get("readonly")),
                buf_file_path=buf.get("buf_file_path", ""),
            )
        )
    return SessionDescriptor(session_key=session_key, open_buffers=open_buffers)


def _ensure_subordinate_link(
    ca_client: CodeAnalysisClient,
    settings: dict[str, Any],
    *,
    editor_server_uuid: str,
) -> dict[str, Any]:
    """Register editor on CA when subordinate link is not yet stored locally."""
    if str(settings.get("subordinate_server_uuid") or "").strip():
        return settings
    session_id = str(settings.get("ca_session_id") or settings["session_key"]).strip()
    linked_uuid = register_editor_subordinate(
        ca_client,
        ca_session_id=session_id,
        editor_server_uuid=editor_server_uuid,
        comment=EDITOR_SUBORDINATE_COMMENT,
    )
    settings["subordinate_server_uuid"] = linked_uuid
    settings["subordinate_comment"] = EDITOR_SUBORDINATE_COMMENT
    return settings


def connect(
    base_dir: str | Path,
    ca_client: CodeAnalysisClient,
    formatter_registry: FormatterRegistry,
    config: dict[str, Any],
    readonly: bool = False,
) -> SessionDescriptor:
    """Create or reopen local session dir keyed by ca_session_id."""
    _ = formatter_registry
    ca_session_id = str(config["ca_session_id"] or "").strip()
    editor_server_uuid = str(config.get("editor_server_uuid") or "").strip()
    if not ca_session_id:
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)
    if not editor_server_uuid:
        raise ValueError(ErrorCode.SESSION_REGISTRATION_FAILED.value)

    verify_ca_session(ca_client, ca_session_id)
    session_key = ca_session_id
    session_dir = Path(base_dir) / session_key

    if session_dir.is_dir() and (session_dir / SETTINGS_NAME).is_file():
        settings = reconnect_session(base_dir, session_key)
        ensure_session_git(session_dir)
        if not str(settings.get("ca_session_id") or "").strip():
            settings["ca_session_id"] = session_key
        settings = _ensure_subordinate_link(
            ca_client,
            settings,
            editor_server_uuid=editor_server_uuid,
        )
        write_session_settings(session_dir, settings)
        return _settings_to_descriptor(settings)

    session_dir = create_session_dir(base_dir, session_key, readonly=readonly)
    ensure_session_git(session_dir)
    try:
        settings = read_session_settings(session_dir)
        settings["ca_session_id"] = session_key
        settings = _ensure_subordinate_link(
            ca_client,
            settings,
            editor_server_uuid=editor_server_uuid,
        )
        write_session_settings(session_dir, settings)
    except Exception:
        shutil.rmtree(session_dir, ignore_errors=True)
        raise
    return _settings_to_descriptor(settings)


def reconnect(
    base_dir: str | Path,
    session_key: str,
    ca_client: CodeAnalysisClient,
) -> SessionDescriptor:
    """Reconnect to existing session directory."""
    _ = ca_client
    settings = reconnect_session(base_dir, session_key)
    return _settings_to_descriptor(settings)


def close_session_api(
    base_dir: str | Path,
    session_key: str,
    ca_client: CodeAnalysisClient,
    force: bool = False,
) -> SessionDescriptor | OperationResult:
    """Close session via buffer_close.close_session."""
    from ai_editor.sessions.buffer_close import close_session

    session_dir = Path(base_dir) / session_key
    result = close_session(session_dir, session_key, ca_client, force=force)
    if not result.success:
        return result
    return SessionDescriptor(session_key=session_key)


def session_status(base_dir: str | Path, session_key: str) -> SessionDescriptor:
    """Read-only session descriptor."""
    session_dir = Path(base_dir) / session_key
    if not session_dir.is_dir():
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)
    return _settings_to_descriptor(read_session_settings(session_dir))
