"""Extended metadata for buf_new command."""
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


def get_buf_new_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_new."""
    sk = example_session_key()
    return build_metadata(
        cls,
        detailed_description=(
            "Create a new local-only buffer in the session with optional initial content "
            "and display name. The buffer has no CA path until buf_save_as. formatter=auto "
            "maps to text. Returns buffer_id and skeleton view. Does not write to CA."
        ),
        parameters={
            "session_key": session_key_param(),
            "formatter": formatter_param(),
            "content": {
                "type": "string",
                "description": "Initial text loaded into the buffer document.",
                "required": False,
                "default": "",
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
                "diagnostics": "Optional history/git diagnostics.",
            },
            example={
                "success": True,
                "buffer_id": example_buffer_id(),
                "formatter": "yaml",
                "view": "root: {...}",
                "diagnostics": [],
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
            {
                "description": "Create plain-text note buffer",
                "command": {
                    "session_key": sk,
                    "formatter": "text",
                    "content": "TODO: draft notes",
                },
                "explanation": "Returns buffer_id for subsequent buf_mutate_batch or search commands.",
            },
        ],
        error_cases={
            "FORMATTER_NOT_FOUND": error_block(
                "FORMATTER_NOT_FOUND",
                "Formatter not found: {formatter}",
                "Use a registered formatter name or auto.",
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
            "Call session_connect first and pass the returned session_key.",
            "Bind to CA with buf_save_as before file_send.",
            "Verify buffer_id via session_status after creation.",
        ],
    )
