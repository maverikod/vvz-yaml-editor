"""Extended metadata for formatter_commands command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    error_block,
    example_buffer_id,
    formatter_param,
    return_operation_result,
)


def get_formatter_commands_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for formatter_commands."""
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Return the formatter command catalog (list_commands) for discovery of "
            "mutation opcodes, paste modes, and formatter-specific operations. "
            "Provide buffer_id (formatter resolved from open buffer) or formatter "
            "name directly. At least one must be supplied. Does not require "
            "session_key and does not modify state."
        ),
        parameters={
            "buffer_id": buffer_id_param(required=False),
            "formatter": formatter_param(required=False),
        },
        return_value=return_operation_result(
            data_fields={
                "commands": "FormatterCommandCatalog with standard_commands and specific_commands.",
            },
            example={
                "commands": {
                    "formatter_name": "yaml",
                    "formatter_version": "1.0",
                    "standard_commands": [
                        {
                            "name": "insert",
                            "description": "Insert raw block under parent at position",
                            "input_schema": {},
                            "output_schema": {},
                        }
                    ],
                    "specific_commands": [],
                    "openapi_schemas": {},
                }
            },
        ),
        usage_examples=[
            {
                "description": "List commands for open buffer",
                "command": {"buffer_id": bid},
                "explanation": "Formatter is inferred from the open buffer metadata.",
            },
            {
                "description": "List commands by formatter name",
                "command": {"formatter": "yaml"},
                "explanation": "No session required when formatter is explicit.",
            },
        ],
        error_cases={
            "FORMATTER_NOT_FOUND": error_block(
                "FORMATTER_NOT_FOUND",
                "Formatter not found",
                "Use a registered formatter name or a valid buffer_id.",
                description="Unknown formatter or missing buffer.",
            ),
            "FORMATTER_COMMAND_DISCOVERY_FAILED": error_block(
                "FORMATTER_COMMAND_DISCOVERY_FAILED",
                "Command discovery failed",
                "Retry with explicit formatter name.",
                description="list_commands raised an internal error.",
            ),
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found",
                "Verify buffer_id or pass formatter instead.",
                description="buffer_id not found when resolving formatter.",
            ),
        },
        best_practices=[
            "Call before buf_mutate_batch to learn valid op names and address shapes.",
            "Provide buffer_id when working inside a session; formatter alone for docs.",
            "At least one of buffer_id or formatter is required (validate_params).",
        ],
    )
