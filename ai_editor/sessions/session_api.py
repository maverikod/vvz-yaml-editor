"""Public session API for command layer."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ai_editor.contracts import BufferDescriptor, ErrorCode, SessionDescriptor
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.registry import FormatterRegistry
from ai_editor.sessions.buffer_close import close_session
from ai_editor.sessions.recovery import reconnect_session
from ai_editor.sessions.session_dir import (
    create_session_dir,
    read_session_settings,
    write_session_settings,
)
from ai_editor.sessions.session_git import init_session_git


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


def connect(
    base_dir: str | Path,
    ca_client: CodeAnalysisClient,
    formatter_registry: FormatterRegistry,
    config: dict[str, Any],
    readonly: bool = False,
) -> SessionDescriptor:
    """Create new session dir + git repo; store ca_session_id in settings."""
    _ = formatter_registry
    session_key = str(uuid.uuid4())
    session_dir = create_session_dir(base_dir, session_key, readonly=readonly)
    init_session_git(session_dir)
    settings = read_session_settings(session_dir)
    settings["ca_session_id"] = config["ca_session_id"]
    write_session_settings(session_dir, settings)
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
) -> SessionDescriptor:
    """Close session via buffer_close.close_session."""
    session_dir = Path(base_dir) / session_key
    close_session(session_dir, session_key, ca_client, force=force)
    return SessionDescriptor(session_key=session_key)


def session_status(base_dir: str | Path, session_key: str) -> SessionDescriptor:
    """Read-only session descriptor."""
    session_dir = Path(base_dir) / session_key
    if not session_dir.is_dir():
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)
    return _settings_to_descriptor(read_session_settings(session_dir))
