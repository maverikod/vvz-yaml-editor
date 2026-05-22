"""JSON Schema for session_close command parameters."""
from __future__ import annotations

from typing import Any


def get_session_close_schema() -> dict[str, Any]:
    """Return machine-readable input schema for session_close."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "force": {"type": "boolean", "default": False, "description": "Force close with unsaved buffers."},
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
