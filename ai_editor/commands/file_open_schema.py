"""JSON Schema for file_open command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import (
    FILE_PATH_PROP,
    FORMATTER_PROP,
    PROJECT_ID_PROP,
    SESSION_KEY_PROP,
)


def get_file_open_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_open."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "project_id": PROJECT_ID_PROP,
            "file_path": FILE_PATH_PROP,
            "formatter": FORMATTER_PROP,
            "open_as_text": {
                "type": "boolean",
                "default": False,
                "description": "When true, skip formatter tree build and treat file as plain text.",
            },
            "readonly": {
                "type": "boolean",
                "default": False,
                "description": "When true, open without acquiring a CA file lock; mutations will fail.",
            },
        },
        "required": ["session_key", "project_id", "file_path"],
        "additionalProperties": False,
    }
