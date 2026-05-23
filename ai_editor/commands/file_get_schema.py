"""JSON Schema for file_get command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import BUFFER_ID_PROP, SESSION_KEY_PROP


def get_file_get_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_get."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "buffer_id": BUFFER_ID_PROP,
            "lock": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Acquire shared advisory lock on the buffer file while reading. "
                    "False reads without locking."
                ),
            },
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
