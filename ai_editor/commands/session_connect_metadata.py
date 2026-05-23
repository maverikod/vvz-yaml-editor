"""Extended metadata for session_connect command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    error_block,
    return_session_descriptor,
)
from ai_editor.sessions.ca_session import EDITOR_SUBORDINATE_COMMENT


def get_session_connect_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for session_connect."""
    ca_id = "3b82630d-55b2-4fd2-867f-6b4b2d580fbf"
    return build_metadata(
        cls,
        detailed_description=(
            "Create or reopen a local editing session keyed by ca_session_id and return "
            "a SessionDescriptor. session_key equals ca_session_id (the session_id from "
            "session_create on code-analysis-server). After the local session directory "
            "is created, the editor registers itself on CA via subordinate_session_create "
            f"with comment '{EDITOR_SUBORDINATE_COMMENT}' and registration.instance_uuid "
            "of this ai-editor server. File locks and transfers use the same ca_session_id. "
            "session_close removes the subordinate link and local directory; it does not "
            "delete the CA session. Use readonly=true to forbid mutating commands."
        ),
        parameters={
            "ca_session_id": {
                "type": "string",
                "description": (
                    "Required CA session_id (UUID4) from session_create on the "
                    "code-analysis-server."
                ),
                "required": True,
                "examples": [ca_id],
            },
            "readonly": {
                "type": "boolean",
                "description": "When true, the session rejects buffer mutations.",
                "required": False,
                "default": False,
                "examples": [False],
            },
        },
        return_value=return_session_descriptor(),
        usage_examples=[
            {
                "description": "Attach editor session to an existing CA session",
                "command": {"ca_session_id": ca_id},
                "explanation": (
                    "Verifies ca_session_id on CA; session_key in the response is the "
                    "same value for all subsequent editor commands."
                ),
            },
            {
                "description": "Start a read-only inspection session",
                "command": {"ca_session_id": ca_id, "readonly": True},
                "explanation": "Same as connect but buffer writes and mutations fail with SESSION_READONLY.",
            },
        ],
        error_cases={
            "SESSION_NOT_FOUND": error_block(
                "SESSION_NOT_FOUND",
                "Session '<uuid>' not found.",
                "Call session_create on code-analysis-server and pass the returned session_id.",
                description="ca_session_id is missing on CA (assert_session_exists failed).",
            ),
            "SESSION_REGISTRATION_FAILED": error_block(
                "SESSION_REGISTRATION_FAILED",
                "Subordinate session registration failed.",
                "Verify parent session is alive, registration.instance_uuid is set, and retry session_connect.",
                description=(
                    "subordinate_session_create failed; local session directory is removed on failure."
                ),
            ),
        },
        best_practices=[
            "Always create the CA session first via session_create on code-analysis-server.",
            "Use the returned session_key (same as ca_session_id) for all editor commands.",
            "Use session_reconnect after editor restarts when the local session directory still exists.",
        ],
    )
