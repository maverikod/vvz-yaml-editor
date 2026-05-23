"""JSON Schema for validate_file command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import (
    BUFFER_ID_PROP,
    FILE_PATH_PROP,
    FORMATTER_PROP,
    PROJECT_ID_PROP,
    SESSION_KEY_PROP,
)


def get_validate_file_schema() -> dict[str, Any]:
    """Return machine-readable input schema for validate_file."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "file_path": FILE_PATH_PROP,
            "buffer_id": BUFFER_ID_PROP,
            "project_id": PROJECT_ID_PROP,
            "formatter": FORMATTER_PROP,
            "schema": {
                "type": "object",
                "description": "Optional JSON Schema for YAML/JSON document validation.",
            },
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
