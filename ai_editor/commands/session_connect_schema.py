"""JSON Schema for session_connect command parameters."""
from __future__ import annotations

from typing import Any


def get_session_connect_schema() -> dict[str, Any]:
    """Return machine-readable input schema for session_connect."""
    return {
        "type": "object",
        "properties": {
            "readonly": {"type": "boolean", "default": False, "description": "Open session read-only."},
        },
        "additionalProperties": False,
    }
