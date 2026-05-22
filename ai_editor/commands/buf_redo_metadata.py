"""Extended metadata for buf_redo command."""
from __future__ import annotations

from typing import Any, Type


def get_buf_redo_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_redo."""
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
        "detailed_description": (
            "History command buf_redo. Delegates to api.redo (parent tactical step). UNDO_AT_BEGINNING / REDO_AT_END on boundary."
        ),
        "parameters": {
"session_key": {"type": "string", "description": "UUID4 session identifier."},
"buffer_id": {"type": "string", "description": "Open buffer identifier."},
    },
        "return_value": {
            "success": {
                "description": "Operation succeeded.",
                "data": "{result fields from api layer}",
            },
            "error": {
                "description": "Operation failed.",
                "code": "ErrorCode string",
                "message": "Human-readable message",
            },
        },
        "usage_examples": [
            {
                "description": "Typical buf_redo invocation",
                "command": {},
                "explanation": "Returns success envelope with result data.",
            },
        ],
        "error_cases": {
            "OPERATION_FAILED": {
                "description": "Underlying api call returned success=False.",
                "message": "{message from OperationResult}",
                "solution": "Check session_key and buffer_id; verify session is open.",
            },
        },
        "best_practices": [
            "Call init_api() before executing commands (handled by main.py startup).",
            "Use dry_run=True on destructive commands to preview changes.",
        ],
    }
