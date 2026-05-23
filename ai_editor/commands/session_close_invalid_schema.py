"""JSON Schema for session_close_invalid command parameters."""
from __future__ import annotations

from typing import Any


def get_session_close_invalid_schema() -> dict[str, Any]:
    """Return machine-readable input schema for session_close_invalid."""
    return {
        "type": "object",
        "properties": {
            "session_key": {
                "type": "string",
                "description": (
                    "UUID4 editor session_key returned by session_connect. The local "
                    "session directory must exist; the command closes it only when "
                    "its ca_session_id is absent on CA."
                ),
            },
            "mode": {
                "type": "string",
                "enum": ["release_ca", "local_only"],
                "default": "local_only",
                "description": (
                    "release_ca: send stored ca_session_id to CA (unlock buffers, "
                    "session_delete with force=true) then remove the local directory. "
                    "local_only: delete the local session directory without CA calls."
                ),
            },
            "force": {
                "type": "boolean",
                "default": False,
                "description": (
                    "When true, close even if buffers have unsaved local edits or "
                    "unsent remote changes."
                ),
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": (
                    "When true, list invalid sessions that would be closed without "
                    "modifying local or CA state."
                ),
            },
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
