"""Extended metadata for session_reconnect command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    error_block,
    example_session_key,
    return_session_descriptor,
    session_key_param,
)


def get_session_reconnect_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for session_reconnect."""
    sk = example_session_key()
    return build_metadata(
        cls,
        detailed_description=(
            "Attach to an existing session directory by session_key and return its "
            "current SessionDescriptor (open buffers and diagnostics)."
        ),
        parameters={"session_key": session_key_param()},
        return_value=return_session_descriptor(),
        usage_examples=[
            {
                "description": "Reconnect after MCP server restart",
                "command": {"session_key": sk},
                "explanation": "Restores in-memory session state from disk and returns open_buffers.",
            },
        ],
        error_cases={
            "SESSION_NOT_FOUND": error_block(
                "SESSION_NOT_FOUND",
                "Session not found: {session_key}",
                "Call session_connect to create a new session or verify the session_key.",
                description="The session directory does not exist or was already closed.",
            ),
        },
        best_practices=[
            "Prefer reconnect over connect when recovering a known session_key.",
            "Verify open_buffers before assuming buffers survived a crash.",
        ],
    )
