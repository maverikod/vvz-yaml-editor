"""JSON Schema for file_close command parameters."""
from __future__ import annotations

from typing import Any


def get_file_close_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_close."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "force": {"type": "boolean", "default": False},
            "dry_run": {"type": "boolean", "default": False, "description": "Preview without mutating."},
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
