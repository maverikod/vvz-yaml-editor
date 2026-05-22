"""JSON Schema for yaml_update_command command parameters."""
from __future__ import annotations

from typing import Any


def get_yaml_update_command_schema() -> dict[str, Any]:
    """Return machine-readable input schema for yaml_update_command."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "command_name": {"type": "string", "description": "Command name to update."},
            "patch": {"type": "object", "description": "Patch object to merge."},
            "dry_run": {
                "type": "boolean",
                "description": "Preview update without mutating state.",
                "default": False,
            },
        },
        "required": ["session_key", "buffer_id", "command_name", "patch"],
        "additionalProperties": False,
    }
