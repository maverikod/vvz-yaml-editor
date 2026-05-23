"""Extended metadata for buf_undo command."""
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


def get_buf_undo_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_undo."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Undo one or more git commits on the buffer branch, restoring prior .buf "
            "content and pushing the current HEAD SHA onto redo_stack. Does not upload "
            "to CA; local session state only."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "steps": {
                "type": "integer",
                "description": "Number of history steps to undo (minimum 1).",
                "required": False,
                "default": 1,
                "examples": [1],
            },
        },
        return_value=return_operation_result(
            data_fields={
                "success": "True when undo completed.",
                "message": "Human-readable status (e.g. undo).",
            },
            example={"success": True, "message": "undo"},
        ),
        usage_examples=[
            {
                "description": "Undo last edit",
                "command": {"session_key": sk, "buffer_id": bid, "steps": 1},
                "explanation": "Restores previous .buf content from git history.",
            },
            {
                "description": "Undo three commits",
                "command": {"session_key": sk, "buffer_id": bid, "steps": 3},
                "explanation": "Walks back three commits on the buffer branch.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Verify buffer_id via session_status.",
                description="buffer_id is not open in the session.",
            ),
            "UNDO_AT_BEGINNING": error_block(
                "UNDO_AT_BEGINNING",
                "at first commit",
                "No further undo steps available on this buffer.",
                description="Buffer branch is at the initial commit.",
            ),
        },
        best_practices=[
            "Verify restored content with buf_get_state after undo.",
            "Use buf_redo to re-apply undone steps from redo_stack.",
            "Undo is local only; use file_send to sync CA after manual review.",
        ],
    )
