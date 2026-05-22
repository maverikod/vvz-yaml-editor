"""JSON Schema for buf_redo command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_redo_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_redo."""
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
