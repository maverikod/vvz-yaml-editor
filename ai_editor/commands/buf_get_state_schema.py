"""JSON Schema for buf_get_state command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_get_state_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_get_state."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
