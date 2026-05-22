"""JSON Schema for buf_new command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_new_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_new."""
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
