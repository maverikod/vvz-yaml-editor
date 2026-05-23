"""CA session identity and editor subordinate link helpers."""
from __future__ import annotations

import logging
from typing import Any

from code_analysis_client import SessionNotFoundError

from ai_editor.contracts import ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient

logger = logging.getLogger(__name__)

EDITOR_SUBORDINATE_COMMENT = "ai_editor"


def ca_session_id(settings: dict[str, Any]) -> str:
    """CA session id (same as local session_key)."""
    return str(settings.get("ca_session_id") or settings.get("session_key") or "").strip()


def work_ca_session_id(settings: dict[str, Any]) -> str:
    """CA session id used for file locks and transfers."""
    return ca_session_id(settings)


def verify_ca_session(
    ca_client: CodeAnalysisClient,
    session_id: str,
) -> None:
    """Verify the CA session exists; raise SESSION_NOT_FOUND on failure."""
    sid = str(session_id or "").strip()
    if not sid:
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)
    try:
        ca_client.assert_session_exists(sid)
    except SessionNotFoundError as exc:
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value) from exc


def register_editor_subordinate(
    ca_client: CodeAnalysisClient,
    *,
    ca_session_id: str,
    editor_server_uuid: str,
    comment: str = EDITOR_SUBORDINATE_COMMENT,
) -> str:
    """Register this ai-editor instance as subordinate server for the CA session."""
    verify_ca_session(ca_client, ca_session_id)
    parent = str(ca_session_id).strip()
    server_uuid = str(editor_server_uuid or "").strip()
    if not server_uuid:
        raise ValueError(ErrorCode.SESSION_REGISTRATION_FAILED.value)

    try:
        link = ca_client.create_subordinate_session(
            parent,
            comment,
            server_uuid=server_uuid,
        )
    except Exception as exc:
        raise ValueError(ErrorCode.SESSION_REGISTRATION_FAILED.value) from exc

    linked = str(link.get("server_uuid") or server_uuid).strip()
    if not linked:
        raise ValueError(ErrorCode.SESSION_REGISTRATION_FAILED.value)
    return linked


def release_editor_subordinate(
    ca_client: CodeAnalysisClient,
    settings: dict[str, Any],
) -> None:
    """Remove editor subordinate link on CA (does not delete the parent session)."""
    parent = ca_session_id(settings)
    server_uuid = str(settings.get("subordinate_server_uuid") or "").strip()
    if not parent or not server_uuid:
        return
    try:
        ca_client.delete_subordinate_session(parent, server_uuid)
    except Exception as exc:
        logger.warning("delete_subordinate_session failed: %s", exc)


# Legacy aliases used by older call sites/tests.
parent_ca_session_id = ca_session_id
verify_parent_ca_session = verify_ca_session
release_editor_ca_registration = release_editor_subordinate
