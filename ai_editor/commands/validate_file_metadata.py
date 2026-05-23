"""Extended metadata for validate_file command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    error_block,
    example_buffer_id,
    example_project_id,
    example_session_key,
    file_path_param,
    formatter_param,
    project_id_param,
    return_validation_result,
    session_key_param,
)


def get_validate_file_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for validate_file."""
    sk = example_session_key()
    bid = example_buffer_id()
    pid = example_project_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Validate document content without writing files or changing session state. "
            "Provide exactly one of buffer_id (validate in-memory open buffer) or "
            "file_path (parse local/remote path content). formatter=auto resolves by "
            "extension when validating by path. Optional schema applies to YAML/JSON "
            "formatters. Never uploads or modifies buffers."
        ),
        parameters={
            "session_key": session_key_param(),
            "file_path": file_path_param(
                required=False,
            ),
            "buffer_id": buffer_id_param(required=False),
            "project_id": project_id_param(required=False),
            "formatter": formatter_param(),
            "schema": {
                "type": "object",
                "description": "Optional JSON Schema for YAML/JSON document validation.",
                "required": False,
                "examples": [{"type": "object", "properties": {"version": {"type": "integer"}}}],
            },
        },
        return_value=return_validation_result(),
        usage_examples=[
            {
                "description": "Validate open buffer in memory",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Runs formatter linters on the session buffer document.",
            },
            {
                "description": "Validate project file by path",
                "command": {
                    "session_key": sk,
                    "file_path": "config/app.yaml",
                    "project_id": pid,
                    "formatter": "yaml",
                },
                "explanation": "Parses and validates file content; does not open a buffer.",
            },
        ],
        error_cases={
            "VALIDATION_FAILED": error_block(
                "VALIDATION_FAILED",
                "Validation failed",
                "Fix issues in diagnostics.",
                description="Linters reported errors (success=false in data).",
            ),
            "FORMAT_VALIDATION_FAILED": error_block(
                "FORMAT_VALIDATION_FAILED",
                "Format validation failed",
                "Fix structural issues in the document.",
                description="Formatter rejected parsed content.",
            ),
            "FORMATTER_NOT_FOUND": error_block(
                "FORMATTER_NOT_FOUND",
                "Formatter not found",
                "Use formatter=auto or a registered name.",
                description="Could not resolve formatter for path or name.",
            ),
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found",
                "Verify buffer_id when validating in-memory.",
                description="buffer_id not open when used as target.",
            ),
        },
        best_practices=[
            "Provide exactly one of file_path or buffer_id (validate_params enforces this).",
            "Use buf_validate when the buffer is already open; validate_file for paths.",
            "Does not modify state; safe pre-flight before file_send.",
        ],
    )
