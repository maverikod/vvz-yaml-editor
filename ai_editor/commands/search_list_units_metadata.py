"""Extended metadata for search_list_units command."""
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


def get_search_list_units_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for search_list_units."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "List all navigable units in an open buffer document tree via formatter "
            "iter_units. Returns SearchMatch-shaped records without applying a query "
            "filter. Does not modify session state."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "scope": {
                "type": "string",
                "description": "Optional formatter-specific scope limiting iteration.",
                "required": False,
                "examples": ["root"],
            },
        },
        return_value=return_operation_result(
            data_fields={
                "units": "List of SearchMatch records for every unit in scope.",
            },
            example={
                "units": [
                    {
                        "buffer_id": bid,
                        "formatter": "yaml",
                        "address": "550e8400-e29b-41d4-a716-446655440001",
                        "preview": "version: 1",
                        "unit_kind": "scalar",
                        "metadata": {},
                    }
                ]
            },
        ),
        usage_examples=[
            {
                "description": "List all units in buffer",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Returns every navigable unit with stable_id addresses.",
            },
            {
                "description": "List units under a scope",
                "command": {"session_key": sk, "buffer_id": bid, "scope": "root"},
                "explanation": "Scope syntax depends on the buffer formatter.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found",
                "Verify buffer_id via session_status.",
                description="Unknown buffer returns empty list.",
            ),
            "SEARCH_SCOPE_INVALID": error_block(
                "SEARCH_SCOPE_INVALID",
                "Invalid scope",
                "Omit scope or use a formatter-valid scope string.",
                description="Formatter rejected the scope parameter.",
            ),
            "FORMATTER_SEARCH_UNSUPPORTED": error_block(
                "FORMATTER_SEARCH_UNSUPPORTED",
                "iter_units not supported",
                "Use formatter_commands for navigation on this formatter.",
                description="Formatter does not implement iter_units.",
            ),
        },
        best_practices=[
            "Use before search_find when exploring document structure.",
            "Combine with search_find to filter listed units.",
            "Addresses from units feed buf_mutate_batch and clipboard commands.",
        ],
    )
