"""JSON Schema for yaml_get_verification command parameters."""
from __future__ import annotations

from typing import Any


def get_yaml_get_verification_schema() -> dict[str, Any]:
    """Return machine-readable input schema for yaml_get_verification."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
