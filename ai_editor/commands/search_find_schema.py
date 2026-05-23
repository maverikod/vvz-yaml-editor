"""JSON Schema for search_find command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import BUFFER_ID_PROP, QUERY_PROP, SESSION_KEY_PROP


def get_search_find_schema() -> dict[str, Any]:
    """Return machine-readable input schema for search_find."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "buffer_id": BUFFER_ID_PROP,
            "query": QUERY_PROP,
            "scope": {
                "type": "string",
                "description": "Optional formatter-specific scope limiting iteration.",
            },
        },
        "required": ["session_key", "buffer_id", "query"],
        "additionalProperties": False,
    }
