"""Extended metadata for buf_cut command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    dry_run_param,
    error_block,
    example_buffer_id,
    example_session_key,
    return_dry_run_preview,
    return_operation_result,
    session_key_param,
)


def get_buf_cut_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_cut."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Cut a document fragment: copy to session clipboard, remove from source "
            "document, write .buf file, and git commit. dry_run=true previews without "
            "modifying buffer or clipboard. Readonly buffers fail with BUFFER_READONLY."
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
            "dry_run": dry_run_param(),
        },
        return_value={
            **return_operation_result(
                data_fields={
                    "success": "True when fragment was cut and clipboard updated.",
                },
                example={"success": True},
            ),
            "dry_run": return_dry_run_preview(
                note="No buffer or clipboard changes."
            )["success"],
        },
        usage_examples=[
            {
                "description": "Preview cut operation",
                "command": {
                    "session_key": sk,
                    "source": {"buffer_id": bid, "address": "node-id-1"},
                    "dry_run": True,
                },
                "explanation": "Returns {success: true, dry_run: true} without removing content.",
            },
            {
                "description": "Cut node to clipboard",
                "command": {
                    "session_key": sk,
                    "source": {
                        "buffer_id": bid,
                        "address": "550e8400-e29b-41d4-a716-446655440001",
                    },
                },
                "explanation": "Removes node from document; use buf_paste to insert elsewhere.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found",
                "Verify source.buffer_id via session_status.",
                description="Source buffer is not open in the session.",
            ),
            "BUFFER_READONLY": error_block(
                "BUFFER_READONLY",
                "readonly",
                "Re-open without readonly=true before cutting.",
                description="Buffer or session is readonly.",
            ),
            "ADDRESS_INVALID": error_block(
                "ADDRESS_INVALID",
                "Invalid address",
                "Use search_find_one to resolve a valid address.",
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
            "Use dry_run=true before destructive cuts.",
            "Follow cut with buf_paste in the same session to avoid clipboard loss.",
            "Use buf_copy when you only need a duplicate, not removal.",
        ],
    )
