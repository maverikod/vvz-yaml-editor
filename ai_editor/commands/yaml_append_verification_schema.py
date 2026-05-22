"""JSON Schema for yaml_append_verification command parameters."""
from __future__ import annotations

from typing import Any


def get_yaml_append_verification_schema() -> dict[str, Any]:
    """Return machine-readable input schema for yaml_append_verification."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "item": {"type": "object", "description": "Verification item payload."},
            "dedupe": {"type": "boolean", "default": True, "description": "Skip duplicates."},
            "dry_run": {
                "type": "boolean",
                "description": "Preview append without mutating state.",
                "default": False,
            },
        },
        "required": ["session_key", "buffer_id", "item"],
        "additionalProperties": False,
    }
