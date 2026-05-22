"""JSON Schema for buf_undo command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_undo_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_undo."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "steps": {"type": "integer", "default": 1, "minimum": 1, "description": "Number of history steps."},
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
