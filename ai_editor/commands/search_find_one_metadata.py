"""Extended metadata for search_find_one command."""
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


def get_search_find_one_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for search_find_one."""
    sk = example_session_key()
    bid = example_buffer_id()
    addr = "550e8400-e29b-41d4-a716-446655440001"
    return build_metadata(
        cls,
        detailed_description=(
            "Search an open buffer and return exactly one matching unit. Fails with "
            "SEARCH_NO_MATCH when none found and SEARCH_NOT_UNIQUE when multiple match. "
            "Does not modify session state."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "query": {
                "type": "object",
                "description": (
                    "Search query. kind is required (contains_text, regex, field_equals, "
                    "node_type, xpath, stable_id)."
                ),
                "required": True,
                "examples": [{"kind": "field_equals", "field": "name", "value": "app"}],
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
                "buffer_id": "Buffer containing the match.",
                "formatter": "Formatter name.",
                "address": "Node stable_id for mutations and clipboard ops.",
                "preview": "Short preview of matched unit.",
                "unit_kind": "Format-defined unit kind.",
                "metadata": "Additional match metadata.",
            },
            example={
                "buffer_id": bid,
                "formatter": "yaml",
                "address": addr,
                "preview": "name: app",
                "unit_kind": "scalar",
                "metadata": {},
            },
        ),
        usage_examples=[
            {
                "description": "Resolve unique field for mutation",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "query": {"kind": "field_equals", "field": "name", "value": "app"},
                },
                "explanation": "Returns single SearchMatch address for buf_mutate_batch.",
            },
            {
                "description": "Lookup node by stable_id",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "query": {"kind": "stable_id", "value": addr},
                },
                "explanation": "Fails with SEARCH_NO_MATCH if the id is absent.",
            },
        ],
        error_cases={
            "SEARCH_QUERY_INVALID": error_block(
                "SEARCH_QUERY_INVALID",
                "Invalid query",
                "Fix query.kind and required fields per kind.",
                description="validate_query failed in validate_params.",
            ),
            "SEARCH_NO_MATCH": error_block(
                "SEARCH_NO_MATCH",
                "no match found",
                "Broaden query or use search_find to list candidates.",
                description="Zero matches for the query.",
            ),
            "SEARCH_NOT_UNIQUE": error_block(
                "SEARCH_NOT_UNIQUE",
                "expected one match, found N",
                "Refine query or use search_find and pick manually.",
                description="More than one unit matched.",
            ),
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found",
                "Verify buffer_id via session_status.",
                description="Unknown buffer_id in session.",
            ),
        },
        best_practices=[
            "Prefer search_find_one over search_find when driving automated edits.",
            "Handle SEARCH_NOT_UNIQUE by refining the query.",
            "Use returned address in buf_copy, buf_cut, and buf_mutate_batch.",
        ],
    )
