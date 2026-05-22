"""JSON Schema for search_list_units command parameters."""
from __future__ import annotations

from typing import Any


def get_search_list_units_schema() -> dict[str, Any]:
    """Return machine-readable input schema for search_list_units."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "scope": {"type": "string", "description": "Optional search scope."},
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
