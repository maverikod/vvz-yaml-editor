"""JSON Schema for formatter_commands command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import BUFFER_ID_PROP, FORMATTER_PROP


def get_formatter_commands_schema() -> dict[str, Any]:
    """Return machine-readable input schema for formatter_commands."""
    return {
        "type": "object",
        "properties": {
            "buffer_id": BUFFER_ID_PROP,
            "formatter": {
                **FORMATTER_PROP,
                "description": (
                    "Formatter name. When omitted with buffer_id, resolved from the open buffer."
                ),
            },
        },
        "additionalProperties": False,
    }
