"""JSON Schema for session_connect command parameters."""
from __future__ import annotations

from typing import Any


def get_session_connect_schema() -> dict[str, Any]:
    """Return machine-readable input schema for session_connect."""
    return {
        "type": "object",
        "properties": {
            "ca_session_id": {
                "type": "string",
                "description": (
                    "CA session_id (UUID4) from session_create on the analysis server. "
                    "Must be registered on CA; verified via the CA client before connect."
                ),
            },
            "readonly": {"type": "boolean", "default": False, "description": "Open session read-only."},
        },
        "required": ["ca_session_id"],
        "additionalProperties": False,
    }
