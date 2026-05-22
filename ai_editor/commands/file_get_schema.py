"""JSON Schema for file_get command parameters."""
from __future__ import annotations

from typing import Any


def get_file_get_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_get."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "lock": {"type": "boolean", "default": True, "description": "Acquire advisory lock on the buffer file. True (default) locks; False reads without locking."},
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
