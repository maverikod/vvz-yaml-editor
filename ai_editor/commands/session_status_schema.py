"""JSON Schema for session_status command parameters."""
from __future__ import annotations

from typing import Any


def get_session_status_schema() -> dict[str, Any]:
    """Return machine-readable input schema for session_status."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
