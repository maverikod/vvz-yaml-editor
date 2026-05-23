"""Extended metadata for buf_redo command."""
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


def get_buf_redo_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_redo."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Redo one or more previously undone commits from redo_stack (LIFO), "
            "restoring .buf content on the buffer git branch. Does not upload to CA."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "steps": {
                "type": "integer",
                "description": "Number of redo steps to apply (minimum 1).",
                "required": False,
                "default": 1,
                "examples": [1],
            },
        },
        return_value=return_operation_result(
            data_fields={
                "success": "True when redo completed.",
                "message": "Human-readable status.",
            },
            example={"success": True, "message": "redo"},
        ),
        usage_examples=[
            {
                "description": "Redo last undone step",
                "command": {"session_key": sk, "buffer_id": bid, "steps": 1},
                "explanation": "Pops one SHA from redo_stack and restores that commit.",
            },
            {
                "description": "Redo after accidental undo",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Default steps=1 re-applies the most recently undone edit.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Verify buffer_id via session_status.",
                description="buffer_id is not open in the session.",
            ),
            "REDO_AT_END": error_block(
                "REDO_AT_END",
                "redo stack empty",
                "Nothing to redo; perform buf_undo first or make new edits.",
                description="redo_stack has no entries.",
            ),
        },
        best_practices=[
            "Redo stack is cleared on new mutations (buf_mutate_batch, cut, paste).",
            "Verify content with buf_get_state after redo.",
            "New edits after undo invalidate redo beyond the stack semantics.",
        ],
    )
