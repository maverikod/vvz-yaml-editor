"""JSON Schema for file_create command parameters."""
from __future__ import annotations

from typing import Any


def get_file_create_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_create."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "formatter": {"type": "string", "default": "auto"},
            "content": {"type": "string", "default": ""},
            "display_name": {"type": "string"},
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
