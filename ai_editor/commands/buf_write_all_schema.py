"""JSON Schema for buf_write_all command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import DRY_RUN_PROP, SESSION_KEY_PROP


def get_buf_write_all_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_write_all."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "force": {
                "type": "boolean",
                "default": False,
                "description": "When true, upload all remote buffers even when modified=false.",
            },
            "dry_run": DRY_RUN_PROP,
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
