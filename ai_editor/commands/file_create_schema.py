"""JSON Schema for file_create command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import FORMATTER_PROP, SESSION_KEY_PROP


def get_file_create_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_create."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "formatter": FORMATTER_PROP,
            "content": {
                "type": "string",
                "minLength": 1,
                "description": "Initial document text loaded into the new buffer (required, non-empty).",
            },
            "display_name": {
                "type": "string",
                "description": "Optional UI label for unsaved buffers (not a file path).",
            },
        },
        "required": ["session_key", "content"],
        "additionalProperties": False,
    }
