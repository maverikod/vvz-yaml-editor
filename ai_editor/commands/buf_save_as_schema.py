"""JSON Schema for buf_save_as command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import (
    BUFFER_ID_PROP,
    DRY_RUN_PROP,
    FILE_PATH_PROP,
    SESSION_KEY_PROP,
)


def get_buf_save_as_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_save_as."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "buffer_id": BUFFER_ID_PROP,
            "new_relative_path": {
                **FILE_PATH_PROP,
                "description": "Project-relative path for the new CA file.",
            },
            "overwrite": {
                "type": "boolean",
                "default": False,
                "description": "When true, replace an existing file at new_relative_path.",
            },
            "dry_run": DRY_RUN_PROP,
        },
        "required": ["session_key", "buffer_id", "new_relative_path"],
        "additionalProperties": False,
    }
