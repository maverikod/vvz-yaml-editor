"""Extended metadata for file_create command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    error_block,
    example_buffer_id,
    example_session_key,
    formatter_param,
    return_operation_result,
    session_key_param,
)


def get_file_create_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for file_create."""
    sk = example_session_key()
    return build_metadata(
        cls,
        detailed_description=(
            "Create a new local-only buffer in the session with initial content "
            "and optional display name. Empty content is rejected. The buffer has "
            "no CA path until buf_save_as. formatter=auto maps to text. "
            "Returns buffer_id and skeleton view."
        ),
        parameters={
            "session_key": session_key_param(),
            "formatter": formatter_param(),
            "content": {
                "type": "string",
                "description": "Initial text loaded into the buffer document (required, non-empty).",
                "required": True,
                "examples": ["key: value\n"],
            },
            "display_name": {
                "type": "string",
                "description": "Optional label shown in session UI (not a file path).",
                "required": False,
                "examples": ["draft.yaml"],
            },
        },
        return_value=return_operation_result(
            data_fields={
                "success": "True when the buffer was created.",
                "buffer_id": "New buffer identifier.",
                "view": "Skeleton preview of initial content.",
                "formatter": "Resolved formatter name.",
            },
            example={
                "success": True,
                "buffer_id": example_buffer_id(),
                "formatter": "yaml",
                "view": "root: {...}",
            },
        ),
        usage_examples=[
            {
                "description": "Create empty YAML scratch buffer",
                "command": {
                    "session_key": sk,
                    "formatter": "yaml",
                    "content": "version: 1\n",
                    "display_name": "scratch.yaml",
                },
                "explanation": "Opens an unsaved buffer; use buf_save_as to persist to CA.",
            },
        ],
        error_cases={
            "BUFFER_INVALID": error_block(
                "BUFFER_INVALID",
                "initial content is required",
                "Pass non-empty content when creating a buffer.",
                description="file_create rejects empty or whitespace-only content.",
            ),
            "FORMATTER_NOT_FOUND": error_block(
                "FORMATTER_NOT_FOUND",
                "Formatter not found",
                "Use a registered formatter name.",
                description="Unknown formatter requested.",
            ),
            "FORMAT_INVALID_ON_OPEN": error_block(
                "FORMAT_INVALID_ON_OPEN",
                "Invalid content for formatter",
                "Fix initial content or choose text formatter.",
                description="Initial content failed formatter parse.",
            ),
        },
        best_practices=[
            "Prefer file_create or buf_new interchangeably; both call api.new_buffer.",
            "Bind to CA with buf_save_as before file_send.",
        ],
    )
