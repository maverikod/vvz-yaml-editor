"""Extended metadata for buf_paste command."""
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


def get_buf_paste_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_paste."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Paste session clipboard content at target.address using the specified mode "
            "(set, append, insert_before, etc.). Writes .buf file and git commit on "
            "success. dry_run=true previews without changes. Cross-formatter paste "
            "uses the conversion registry when supported."
        ),
        parameters={
            "session_key": session_key_param(),
            "target": {
                "type": "object",
                "description": "Target location: buffer_id and formatter-specific address.",
                "required": True,
                "examples": [
                    {
                        "buffer_id": bid,
                        "address": "550e8400-e29b-41d4-a716-446655440002",
                    }
                ],
            },
            "mode": {
                "type": "string",
                "description": "Paste mode controlling how clipboard content merges at target.",
                "required": True,
                "enum": [
                    "set",
                    "replace_block",
                    "append",
                    "insert_before",
                    "insert_after",
                    "insert",
                    "replace_range",
                    "prepend",
                    "replace",
                    "delete",
                ],
                "examples": ["append"],
            },
            "dry_run": dry_run_param(),
        },
        return_value={
            **return_operation_result(
                data_fields={
                    "success": "True when paste completed.",
                    "diagnostics": "Optional history/git diagnostics.",
                },
                example={"success": True, "diagnostics": []},
            ),
            "dry_run": return_dry_run_preview(
                note="No buffer or clipboard changes."
            )["success"],
        },
        usage_examples=[
            {
                "description": "Preview paste after cut",
                "command": {
                    "session_key": sk,
                    "target": {"buffer_id": bid, "address": "target-node-id"},
                    "mode": "append",
                    "dry_run": True,
                },
                "explanation": "Returns {success: true, dry_run: true} without modifying buffer.",
            },
            {
                "description": "Append clipboard fragment to target",
                "command": {
                    "session_key": sk,
                    "target": {
                        "buffer_id": bid,
                        "address": "550e8400-e29b-41d4-a716-446655440002",
                    },
                    "mode": "append",
                },
                "explanation": "Requires prior buf_copy or buf_cut in the same session.",
            },
        ],
        error_cases={
            "CLIPBOARD_EMPTY": error_block(
                "CLIPBOARD_EMPTY",
                "Clipboard is empty",
                "Run buf_copy or buf_cut before paste.",
                description="No clipboard.json content in the session.",
            ),
            "CLIPBOARD_FORMAT_MISMATCH": error_block(
                "CLIPBOARD_FORMAT_MISMATCH",
                "Clipboard format mismatch",
                "Copy from the same formatter or use a supported conversion.",
                description="Source and target formatters are incompatible.",
            ),
            "CLIPBOARD_SOURCE_STALE": error_block(
                "CLIPBOARD_SOURCE_STALE",
                "Clipboard source revision changed",
                "Re-copy the fragment after document edits.",
                description="paste_policy reject_if_source_revision_changed failed.",
            ),
            "CLIPBOARD_INVALID_MODE": error_block(
                "CLIPBOARD_INVALID_MODE",
                "Invalid paste mode",
                "Use a mode from formatter_commands or the mode enum.",
                description="Mode is not supported for the target formatter.",
            ),
            "BUFFER_READONLY": error_block(
                "BUFFER_READONLY",
                "readonly",
                "Re-open target buffer without readonly=true.",
                description="Target buffer or session is readonly.",
            ),
            "ADDRESS_INVALID": error_block(
                "ADDRESS_INVALID",
                "Invalid target address",
                "Use search_find_one to resolve a valid target address.",
                description="Target address failed formatter normalization.",
            ),
        },
        best_practices=[
            "Use dry_run=true to validate mode and target before applying.",
            "Check formatter_commands for supported paste modes per formatter.",
            "Cut then paste in one session to move fragments between locations.",
        ],
    )
