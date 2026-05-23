"""Extended metadata for buf_validate command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    error_block,
    example_buffer_id,
    example_session_key,
    return_validation_result,
    session_key_param,
)


def get_buf_validate_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_validate."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Run formatter linters on the in-memory document for an open buffer. "
            "Does not write files, upload to CA, or change modified state. Returns "
            "ValidationResult with success=false when diagnostics are present."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
        },
        return_value=return_validation_result(),
        usage_examples=[
            {
                "description": "Validate open YAML buffer",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Returns {success: true, diagnostics: []} when valid.",
            },
            {
                "description": "Pre-flight check before file_send",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Inspect diagnostics before uploading to CA.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Verify buffer_id via session_status.",
                description="Buffer missing; returns success=false with empty diagnostics.",
            ),
            "VALIDATION_FAILED": error_block(
                "VALIDATION_FAILED",
                "Validation failed",
                "Fix issues listed in diagnostics and retry.",
                description="Linters reported errors (success=false in data).",
            ),
            "FORMAT_VALIDATION_FAILED": error_block(
                "FORMAT_VALIDATION_FAILED",
                "Format validation failed",
                "Fix structural or schema issues in the document.",
                description="Formatter-specific validation rejected the tree.",
            ),
            "SCHEMA_VALIDATION_FAILED": error_block(
                "SCHEMA_VALIDATION_FAILED",
                "Schema validation failed",
                "Adjust document to match the YAML/JSON schema.",
                description="Optional schema check failed (YAML formatter).",
            ),
        },
        best_practices=[
            "Run before file_send or buf_save_as on complex edits.",
            "Inspect diagnostics.path and diagnostics.message for fix hints.",
            "Does not modify the buffer; safe to run repeatedly.",
        ],
    )
