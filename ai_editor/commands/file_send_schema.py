"""JSON Schema for file_send command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import (
    BUFFER_ID_PROP,
    DRY_RUN_PROP,
    FILE_PATH_PROP,
    PROJECT_ID_PROP,
    SESSION_KEY_PROP,
)


def get_file_send_schema() -> dict[str, Any]:
    """Return machine-readable input schema for file_send."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "buffer_id": BUFFER_ID_PROP,
            "project_id": PROJECT_ID_PROP,
            "file_path": FILE_PATH_PROP,
            "dry_run": DRY_RUN_PROP,
            "release_lock": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Release advisory lock after successful upload. "
                    "False (default) keeps lock; True releases lock on CA."
                ),
            },
        },
        "required": ["session_key", "buffer_id"],
        "additionalProperties": False,
    }
