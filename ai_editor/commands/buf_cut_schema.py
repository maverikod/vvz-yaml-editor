"""JSON Schema for buf_cut command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import DRY_RUN_PROP, SESSION_KEY_PROP, SOURCE_PROP


def get_buf_cut_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_cut."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "source": SOURCE_PROP,
            "dry_run": DRY_RUN_PROP,
        },
        "required": ["session_key", "source"],
        "additionalProperties": False,
    }
