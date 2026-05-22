"""JSON Schema for file_open command parameters."""
from __future__ import annotations

from typing import Any


def get_file_open_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_open."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "project_id": {"type": "string", "description": "Project UUID (required)."},
            "file_path": {"type": "string"},
            "formatter": {"type": "string", "default": "auto"},
            "open_as_text": {"type": "boolean", "default": False},
            "readonly": {"type": "boolean", "default": False},
        },
        "required": ["session_key", "project_id", "file_path"],
        "additionalProperties": False,
    }
