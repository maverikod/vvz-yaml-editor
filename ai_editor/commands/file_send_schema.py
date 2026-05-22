"""JSON Schema for file_send command parameters."""
from __future__ import annotations

from typing import Any


def get_file_send_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_send."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "dry_run": {"type": "boolean", "default": False, "description": "Preview without mutating."},
            "release_lock": {"type": "boolean", "default": False, "description": "Release advisory lock after successful upload. False (default) keeps lock; True releases lock so another client can acquire it."},
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
