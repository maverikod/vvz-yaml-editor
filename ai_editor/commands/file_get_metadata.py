"""Extended metadata for file_get command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    error_block,
    example_buffer_id,
    example_session_key,
    session_key_param,
)


def get_file_get_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for file_get."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Read the local buffer file for an open buffer (no CA server call). "
            "Returns content, relative_path, file_type, and modified flag. "
            "lock=true (default) acquires a shared advisory flock during the read."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "lock": {
                "type": "boolean",
                "description": "Shared advisory lock while reading the buf file.",
                "required": False,
                "default": True,
            },
        },
        return_value={
            "success": {
                "description": "True when content was read.",
                "data": {
                    "content": "Full buffer file text.",
                    "relative_path": "Bound project path or null for local-only buffers.",
                    "file_type": "local or remote.",
                    "modified": "Whether the buffer has unsaved local changes.",
                },
                "example": {
                    "success": True,
                    "content": "hello\n",
                    "relative_path": "src/main.py",
                    "file_type": "remote",
                    "modified": False,
                },
            },
        },
        usage_examples=[
            {
                "description": "Read buffer content with default shared lock",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Returns content and modified flag from the local buf file.",
            },
            {
                "description": "Read without locking",
                "command": {"session_key": sk, "buffer_id": bid, "lock": False},
                "explanation": "Same payload without acquiring flock on the buf file.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Use session_status to list open buffer_id values.",
                description="Unknown buffer_id or missing buf file on disk.",
            ),
        },
        best_practices=[
            "Use buf_get_state for skeleton preview and formatter metadata.",
            "Use file_get when you need the raw buffer file content.",
        ],
    )
