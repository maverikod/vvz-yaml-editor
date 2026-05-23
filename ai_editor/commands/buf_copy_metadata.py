"""Extended metadata for buf_copy command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    error_block,
    example_buffer_id,
    example_session_key,
    return_operation_result,
    session_key_param,
)


def get_buf_copy_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_copy."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Copy a document fragment at source.address into the session clipboard "
            "(clipboard.json). Does not modify the source buffer or write .buf files. "
            "Use buf_paste to insert the clipboard content elsewhere."
        ),
        parameters={
            "session_key": session_key_param(),
            "source": {
                "type": "object",
                "description": "Source fragment: buffer_id and formatter-specific address.",
                "required": True,
                "examples": [
                    {
                        "buffer_id": bid,
                        "address": "550e8400-e29b-41d4-a716-446655440001",
                    }
                ],
            },
        },
        return_value=return_operation_result(
            data_fields={
                "success": "True when fragment was copied to clipboard.",
            },
            example={"success": True},
        ),
        usage_examples=[
            {
                "description": "Copy YAML node to clipboard",
                "command": {
                    "session_key": sk,
                    "source": {
                        "buffer_id": bid,
                        "address": "550e8400-e29b-41d4-a716-446655440001",
                    },
                },
                "explanation": "Stores formatter body in session clipboard for buf_paste.",
            },
            {
                "description": "Copy after search_find_one",
                "command": {
                    "session_key": sk,
                    "source": {"buffer_id": bid, "address": "node-stable-id"},
                },
                "explanation": "Use the address from search_find_one as source.address.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found",
                "Verify source.buffer_id via session_status.",
                description="Source buffer is not open in the session.",
            ),
            "ADDRESS_INVALID": error_block(
                "ADDRESS_INVALID",
                "Invalid address",
                "Use search_find or formatter_commands to discover valid addresses.",
                description="Source address failed formatter normalization.",
            ),
            "ADDRESS_NOT_FOUND": error_block(
                "ADDRESS_NOT_FOUND",
                "Address not found",
                "Confirm the node still exists in the document tree.",
                description="No node at the given address.",
            ),
        },
        best_practices=[
            "Resolve addresses with search_find_one before copy.",
            "Copy is non-destructive; prefer copy over cut when unsure.",
            "Paste within the same formatter or check conversion via buf_paste.",
        ],
    )
