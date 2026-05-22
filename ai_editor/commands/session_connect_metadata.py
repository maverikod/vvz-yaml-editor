"""Extended metadata for session_connect command."""
from __future__ import annotations

from typing import Any, Type


def get_session_connect_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for session_connect."""
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
        "detailed_description": (
            "Create a new editing session. Command name session_connect; api.connect(readonly=False)."
        ),
        "parameters": {
"readonly": {"description": "Read-only session flag.", "type": "boolean", "required": False, "default": False},
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
                "description": "Typical session_connect invocation",
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
