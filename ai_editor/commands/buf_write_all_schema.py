"""JSON Schema for buf_write_all command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_write_all_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_write_all."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "force": {"type": "boolean", "default": False},
            "dry_run": {"type": "boolean", "default": False, "description": "Preview without mutating state."},
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
