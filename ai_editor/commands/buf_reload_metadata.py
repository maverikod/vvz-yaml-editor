"""Extended metadata for buf_reload command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    error_block,
    example_buffer_id,
    example_session_key,
    return_operation_result,
    session_key_param,
)


def get_buf_reload_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_reload."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Re-download a remote buffer from the CA server, rebuild the formatter "
            "document tree and local .buf file, and reset modified=false. Local-only "
            "buffers (no relative_path) cannot be reloaded. Discards unsent local edits."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
        },
        return_value=return_operation_result(
            data_fields={
                "success": "True when reload completed.",
                "view": "Skeleton preview of reloaded content.",
                "diagnostics": "Optional history/git diagnostics.",
            },
            example={
                "success": True,
                "view": "root: {...}",
                "diagnostics": [],
            },
        ),
        usage_examples=[
            {
                "description": "Reload remote buffer from CA",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Overwrites local edits with server content; modified becomes false.",
            },
            {
                "description": "Refresh after external CA edit",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Use when another tool changed the file on CA and local buffer is stale.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Verify buffer_id via session_status.",
                description="buffer_id is not open in the session.",
            ),
            "BUFFER_INVALID": error_block(
                "BUFFER_INVALID",
                "local buffer cannot reload",
                "Use buf_save_as first; reload applies only to remote buffers.",
                description="Buffer has no CA binding (local-only).",
            ),
            "PATH_NOT_FOUND": error_block(
                "PATH_NOT_FOUND",
                "Path not found on CA",
                "Verify the file still exists on the CA server.",
                description="CA download failed for the buffer path.",
            ),
            "FORMATTER_NOT_FOUND": error_block(
                "FORMATTER_NOT_FOUND",
                "Formatter not found: {formatter}",
                "Re-open the buffer with a valid formatter.",
                description="Buffer formatter is not registered.",
            ),
            "FORMAT_INVALID_ON_OPEN": error_block(
                "FORMAT_INVALID_ON_OPEN",
                "Invalid content from CA",
                "Fix the remote file or open as text.",
                description="Downloaded content failed formatter parse.",
            ),
        },
        best_practices=[
            "Confirm unsent edits can be discarded before reload.",
            "Verify result with buf_get_state (modified should be false).",
            "Use file_open instead of reload for buffers not yet in session.",
        ],
    )
