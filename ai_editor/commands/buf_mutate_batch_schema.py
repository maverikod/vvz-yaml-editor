"""JSON Schema for buf_mutate_batch command parameters."""
from __future__ import annotations

from typing import Any


def get_buf_mutate_batch_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_mutate_batch."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "operations": {"type": "array", "items": {"type": "object", "properties": {"op": {"type": "string"}, "address": {}, "value": {}}, "required": ["op", "address"]}},
            "dry_run": {"type": "boolean", "default": False, "description": "Preview without mutating state."},
        },
        "required": ["session_key", "buffer_id", "operations"],
        "additionalProperties": False,
    }
