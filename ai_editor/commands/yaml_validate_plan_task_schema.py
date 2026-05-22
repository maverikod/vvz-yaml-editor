"""JSON Schema for yaml_validate_plan_task command parameters."""
from __future__ import annotations

from typing import Any


def get_yaml_validate_plan_task_schema() -> dict[str, Any]:
    """Return machine-readable input schema for yaml_validate_plan_task."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "file_path": {"type": "string"},
            "project_id": {"type": "string"},
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
