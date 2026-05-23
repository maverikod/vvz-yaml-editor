"""Extended metadata for buf_mutate_batch command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    dry_run_param,
    error_block,
    example_buffer_id,
    example_session_key,
    return_dry_run_preview,
    return_operation_result,
    session_key_param,
)


def get_buf_mutate_batch_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_mutate_batch."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Apply a batch of formatter mutation operations to an open buffer in one "
            "transaction. Each operation has op, address, and optional value. On success "
            "writes the local .buf file, session sidecar, and git commit. dry_run=true "
            "returns the operation count without modifying state. Readonly buffers fail "
            "with BUFFER_READONLY."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "operations": {
                "type": "array",
                "description": (
                    "Ordered list of mutation ops. Each item: {op, address, value?}. "
                    "Opcode and address shape depend on the buffer formatter."
                ),
                "required": True,
                "examples": [
                    [
                        {
                            "op": "set",
                            "address": "550e8400-e29b-41d4-a716-446655440001",
                            "value": "new text",
                        }
                    ]
                ],
            },
            "dry_run": dry_run_param(),
        },
        return_value={
            **return_operation_result(
                data_fields={
                    "success": "True when all operations applied.",
                    "diagnostics": "Optional history/git diagnostics.",
                },
                example={"success": True, "diagnostics": []},
            ),
            "dry_run": return_dry_run_preview(
                note="Returns operation count; no buf write or git commit."
            )["success"],
        },
        usage_examples=[
            {
                "description": "Preview mutation batch",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "operations": [
                        {"op": "set", "address": "node-id-1", "value": "updated"}
                    ],
                    "dry_run": True,
                },
                "explanation": "Returns {success: true, dry_run: true, operations: 1}.",
            },
            {
                "description": "Apply YAML field update",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "operations": [
                        {
                            "op": "set",
                            "address": "550e8400-e29b-41d4-a716-446655440001",
                            "value": "production",
                        }
                    ],
                },
                "explanation": "Mutates in-memory tree and persists to local .buf file.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Verify buffer_id via session_status.",
                description="buffer_id is not open in the session.",
            ),
            "BUFFER_READONLY": error_block(
                "BUFFER_READONLY",
                "readonly",
                "Re-open the file without readonly=true or use a writable buffer.",
                description="Buffer or session is readonly.",
            ),
            "ADDRESS_INVALID": error_block(
                "ADDRESS_INVALID",
                "Invalid address",
                "Use search_find or formatter_commands to discover valid addresses.",
                description="Operation address failed formatter normalization.",
            ),
            "MUTATION_ROLLBACK": error_block(
                "MUTATION_ROLLBACK",
                "Mutation rolled back",
                "Fix the failing operation; earlier ops in the batch are reverted.",
                description="Batch failed mid-way; document restored to pre-batch state.",
            ),
            "PRE_WRITE_VALIDATION_FAILED": error_block(
                "PRE_WRITE_VALIDATION_FAILED",
                "Pre-write validation failed",
                "Run buf_validate and fix diagnostics before mutating.",
                description="Formatter rejected the document after mutation.",
            ),
        },
        best_practices=[
            "Discover op names via formatter_commands for the buffer formatter.",
            "Use dry_run=true to validate operation shape before applying.",
            "Resolve target addresses with search_find_one before batch edits.",
        ],
    )
