"""JSON Schema for file_close command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import BUFFER_ID_PROP, DRY_RUN_PROP, SESSION_KEY_PROP


def get_file_close_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_close."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "buffer_id": BUFFER_ID_PROP,
            "force": {
                "type": "boolean",
                "default": False,
                "description": "When true, close even if the buffer has unsent remote changes.",
            },
            "dry_run": DRY_RUN_PROP,
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
