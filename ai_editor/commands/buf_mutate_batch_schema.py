"""JSON Schema for buf_mutate_batch command parameters."""
from __future__ import annotations

from typing import Any

from ai_editor.commands._schema_common import (
    BUFFER_ID_PROP,
    DRY_RUN_PROP,
    MUTATION_OP_ITEM,
    SESSION_KEY_PROP,
)


def get_buf_mutate_batch_schema() -> dict[str, Any]:
    """Return machine-readable input schema for buf_mutate_batch."""
    return {
        "type": "object",
        "properties": {
            "session_key": SESSION_KEY_PROP,
            "buffer_id": BUFFER_ID_PROP,
            "operations": {
                "type": "array",
                "description": "Ordered formatter mutation operations.",
                "items": MUTATION_OP_ITEM,
            },
            "dry_run": DRY_RUN_PROP,
        },
        "required": ["session_key", "buffer_id", "operations"],
        "additionalProperties": False,
    }
