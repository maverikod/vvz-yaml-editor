"""JSON Schema for buf_paste command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import (
    DRY_RUN_PROP,
    PASTE_MODES,
    SESSION_KEY_PROP,
    TARGET_PROP,
)


def get_buf_paste_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_paste."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "target": TARGET_PROP,
            "mode": {
                "type": "string",
                "enum": PASTE_MODES,
                "description": "Paste mode controlling how clipboard content merges at target.",
            },
            "dry_run": DRY_RUN_PROP,
        },
        "required": ["session_key", "target", "mode"],
        "additionalProperties": False,
    }
