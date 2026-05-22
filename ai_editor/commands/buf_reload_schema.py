"""JSON Schema for buf_reload command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_reload_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_reload."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
