"""Extended metadata for session_close command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    error_block,
    example_session_key,
    force_param,
    return_operation_result,
    session_key_param,
)


def get_session_close_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for session_close."""
    sk = example_session_key()
    return build_metadata(
        cls,
        detailed_description=(
            "Close a session and remove its on-disk directory. Releases file locks and "
            "calls subordinate_session_delete on the CA server for this editor instance "
            "(registration.instance_uuid). The CA client session (session_id from "
            "session_create) is not deleted. Without force=true the command fails when "
            "any buffer is modified locally or has unsent remote changes."
        ),
        parameters={
            "session_key": session_key_param(),
            "force": force_param(
                description=(
                    "When true, close even if buffers have unsaved local edits or "
                    "unsent remote changes. Unsaved work is discarded."
                ),
            ),
        },
        return_value=return_operation_result(
            data_fields={
                "success": "True when the session directory was removed.",
                "message": "Optional confirmation text.",
            },
            example={"success": True, "message": "session closed"},
        ),
        usage_examples=[
            {
                "description": "Close a clean session",
                "command": {"session_key": sk, "force": False},
                "explanation": "Succeeds only when all buffers are saved and sent.",
            },
            {
                "description": "Force-close with pending edits",
                "command": {"session_key": sk, "force": True},
                "explanation": "Discards unsaved/unsent buffers and deletes the session directory.",
            },
        ],
        error_cases={
            "SESSION_HAS_UNSAVED_BUFFERS": error_block(
                "SESSION_HAS_UNSAVED_BUFFERS",
                "Session has unsaved buffers",
                "Call file_send or buf_write_all for each modified buffer, or pass force=true.",
                description="A buffer has modified=true in session settings.",
            ),
            "SESSION_HAS_UNSENT_FILES": error_block(
                "SESSION_HAS_UNSENT_FILES",
                "Session has unsent files",
                "Upload pending buffers with file_send, or pass force=true.",
                description="A remote buffer has local changes not yet uploaded to CA.",
            ),
        },
        best_practices=[
            "Run session_status and file_send on modified buffers before closing.",
            "Use force=true only when abandoning work intentionally.",
        ],
    )
