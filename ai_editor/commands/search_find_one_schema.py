"""JSON Schema for search_find_one command parameters."""
from __future__ import annotations

from typing import Any


def get_search_find_one_schema() -> dict[str, Any]:
    """Return machine-readable input schema for search_find_one."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "query": {"type": "object", "properties": {"kind": {"type": "string"}, "value": {}, "options": {"type": "object"}}, "required": ["kind"], "additionalProperties": False},
            "scope": {"type": "string", "description": "Optional search scope."},
        },
        "required": ["session_key", "buffer_id", "query"],
        "additionalProperties": False,
    }
