"""JSON Schema for buf_save_as command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_save_as_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_save_as."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "new_relative_path": {"type": "string"},
            "overwrite": {"type": "boolean", "default": False},
            "dry_run": {"type": "boolean", "default": False, "description": "Preview without mutating state."},
        },
        "required": ["session_key", "buffer_id", "new_relative_path"],
        "additionalProperties": False,
    }
