"""Extended metadata for session_status command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    error_block,
    example_session_key,
    return_session_descriptor,
    session_key_param,
)


def get_session_status_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for session_status."""
    sk = example_session_key()
    return build_metadata(
        cls,
        detailed_description=(
            "Read the current session settings and return a SessionDescriptor listing "
            "every open buffer with formatter, paths, modified, and readonly flags."
        ),
        parameters={"session_key": session_key_param()},
        return_value=return_session_descriptor(),
        usage_examples=[
            {
                "description": "List open buffers before editing",
                "command": {"session_key": sk},
                "explanation": "Returns session_key and open_buffers array for navigation.",
            },
        ],
        error_cases={
            "SESSION_NOT_FOUND": error_block(
                "SESSION_NOT_FOUND",
                "Session not found: {session_key}",
                "Verify session_key or call session_connect.",
                description="Session directory missing or session was closed.",
            ),
        },
        best_practices=[
            "Poll session_status after file_open/file_close to refresh buffer_id list.",
            "Check modified flags before session_close.",
        ],
    )
