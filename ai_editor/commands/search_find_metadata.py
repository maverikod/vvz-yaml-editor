"""Extended metadata for search_find command."""
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


def get_search_find_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for search_find."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Search an open buffer document tree for all units matching query. "
            "Returns a list of SearchMatch records with buffer_id, formatter, address, "
            "preview, unit_kind, and metadata. Does not modify session state. Empty list "
            "when no matches or buffer not found."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "query": {
                "type": "object",
                "description": (
                    "Search query. kind is required (contains_text, regex, field_equals, "
                    "node_type, xpath, stable_id). Additional fields depend on kind."
                ),
                "required": True,
                "examples": [{"kind": "contains_text", "value": "database"}],
            },
            "scope": {
                "type": "string",
                "description": "Optional formatter-specific scope limiting iteration.",
                "required": False,
                "examples": ["root"],
            },
        },
        return_value=return_operation_result(
            data_fields={
                "matches": "List of SearchMatch objects (may be empty).",
            },
            example={
                "matches": [
                    {
                        "buffer_id": bid,
                        "formatter": "yaml",
                        "address": "550e8400-e29b-41d4-a716-446655440001",
                        "preview": "database: postgres",
                        "unit_kind": "mapping",
                        "metadata": {},
                    }
                ]
            },
        ),
        usage_examples=[
            {
                "description": "Find YAML keys containing text",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "query": {"kind": "contains_text", "value": "database"},
                },
                "explanation": "Returns all matching units with stable_id addresses.",
            },
            {
                "description": "Find by stable_id",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "query": {
                        "kind": "stable_id",
                        "value": "550e8400-e29b-41d4-a716-446655440001",
                    },
                },
                "explanation": "Direct lookup when the node UUID is known.",
            },
        ],
        error_cases={
            "SEARCH_QUERY_INVALID": error_block(
                "SEARCH_QUERY_INVALID",
                "Invalid query",
                "Fix query.kind and required fields per kind.",
                description="validate_query failed in validate_params.",
            ),
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found",
                "Verify buffer_id via session_status.",
                description="Unknown buffer returns empty matches list.",
            ),
            "FORMATTER_SEARCH_UNSUPPORTED": error_block(
                "FORMATTER_SEARCH_UNSUPPORTED",
                "Search not supported",
                "Use list_units or formatter-specific navigation.",
                description="Formatter does not implement iter_units/match_unit.",
            ),
        },
        best_practices=[
            "Use search_find_one when exactly one match is required.",
            "Use returned address values in buf_mutate_batch and clipboard commands.",
            "Narrow with scope when documents are large.",
        ],
    )
