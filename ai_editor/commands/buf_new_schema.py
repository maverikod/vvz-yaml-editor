"""JSON Schema for buf_new command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import FORMATTER_PROP, SESSION_KEY_PROP


def get_buf_new_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_new."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "formatter": FORMATTER_PROP,
            "content": {
                "type": "string",
                "default": "",
                "description": "Initial text loaded into the buffer document.",
            },
            "display_name": {
                "type": "string",
                "description": "Optional label shown in session UI (not a file path).",
            },
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
