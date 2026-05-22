"""JSON Schema for yaml_get_command command parameters."""
from __future__ import annotations

from typing import Any


def get_yaml_get_command_schema() -> dict[str, Any]:
    """Return machine-readable input schema for yaml_get_command."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "command_name": {{"type": "string"}},
        },
        "required": ["session_key", "buffer_id", "command_name"],
        "additionalProperties": False,
    }
