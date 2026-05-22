"""JSON Schema for buf_paste command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_paste_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_paste."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "target": {"type": "object", "properties": {"buffer_id": {"type": "string"}, "address": {}}, "required": ["buffer_id", "address"], "additionalProperties": False},
            "mode": {"type": "string", "enum": ["set", "replace_block", "append", "insert_before", "insert_after", "insert", "replace_range", "prepend", "replace", "delete"]},
            "dry_run": {"type": "boolean", "default": False, "description": "Preview without mutating state."},
        },
        "required": ["session_key", "target", "mode"],
        "additionalProperties": False,
    }
