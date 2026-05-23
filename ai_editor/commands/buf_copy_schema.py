"""JSON Schema for buf_copy command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import SESSION_KEY_PROP, SOURCE_PROP


def get_buf_copy_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_copy."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "source": SOURCE_PROP,
        },
        "required": ["session_key", "source"],
        "additionalProperties": False,
    }
