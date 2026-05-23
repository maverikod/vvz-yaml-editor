"""CA session liveness checks for MCP commands."""
from __future__ import annotations

from pathlib import Path

from code_analysis_client import SessionNotFoundError

from ai_editor.contracts import ErrorCode
from ai_editor.sessions.session_dir import read_session_settings


def ensure_ca_session_alive(session_key: str) -> None:
    """Verify local session exists and its CA session is live on the analysis server.

    Raises:
        ValueError: With ErrorCode.SESSION_NOT_FOUND when the local session
            directory is missing, ca_session_id is absent, or the CA server
            reports the session as unknown/expired.
        RuntimeError: When init_api() has not been called yet.
    """
    from ai_editor.api_init import get_session_manager

    manager = get_session_manager()
    session_dir = Path(manager.base_dir) / session_key
    if not session_dir.is_dir():
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)

    settings = read_session_settings(session_dir)
    ca_session_id = str(settings.get("ca_session_id") or "").strip()
    if not ca_session_id:
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)

    try:
        manager.ca_client.assert_session_exists(ca_session_id)
    except SessionNotFoundError as exc:
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value) from exc
