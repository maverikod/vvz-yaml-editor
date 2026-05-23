"""Extended metadata for file_close command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    dry_run_param,
    error_block,
    example_buffer_id,
    example_session_key,
    force_param,
    return_dry_run_preview,
    return_operation_result,
    session_key_param,
)


def get_file_close_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for file_close."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Close one open buffer, release its CA advisory lock when held, and remove "
            "it from session settings. Without force=true the command fails when the "
            "buffer has unsent remote changes. dry_run=true previews closure without "
            "mutating session state."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "force": force_param(
                description="When true, close despite unsent remote changes.",
            ),
            "dry_run": dry_run_param(),
        },
        return_value={
            **return_operation_result(
                data_fields={
                    "success": "True when the buffer was closed.",
                    "buffer_id": "Closed buffer identifier.",
                },
                example={"success": True, "buffer_id": bid},
            ),
            "dry_run": return_dry_run_preview(note="No buffer removed; validates close preconditions.")[
                "success"
            ],
        },
        usage_examples=[
            {
                "description": "Preview buffer close",
                "command": {"session_key": sk, "buffer_id": bid, "dry_run": True},
                "explanation": "Returns {success: true, dry_run: true} without closing.",
            },
            {
                "description": "Close after upload",
                "command": {"session_key": sk, "buffer_id": bid, "force": False},
                "explanation": "Succeeds when file_send already uploaded changes.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Call session_status to list valid buffer_id values.",
                description="buffer_id is not in the session open_buffers list.",
            ),
            "FILE_HAS_UNSENT_CHANGES": error_block(
                "FILE_HAS_UNSENT_CHANGES",
                "Buffer has unsent changes",
                "Call file_send first or pass force=true.",
                description="Remote buffer has local edits not uploaded to CA.",
            ),
        },
        best_practices=[
            "Call file_send before file_close on modified remote buffers.",
            "Use dry_run=true to check whether close would succeed.",
        ],
    )
