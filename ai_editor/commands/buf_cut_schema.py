"""JSON Schema for buf_cut command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_cut_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_cut."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "source": {"type": "object", "properties": {"buffer_id": {"type": "string"}, "address": {}}, "required": ["buffer_id", "address"], "additionalProperties": False},
            "dry_run": {"type": "boolean", "default": False, "description": "Preview without mutating state."},
        },
        "required": ["session_key", "source"],
        "additionalProperties": False,
    }
