"""JSON Schema for formatter_commands command parameters."""
from __future__ import annotations

from typing import Any


def get_formatter_commands_schema() -> dict[str, Any]:
    """Return machine-readable input schema for formatter_commands."""
    return {
        "type": "object",
        "properties": {
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "formatter": {"type": "string"},
        },
        "additionalProperties": False,
    }
