"""Extended metadata for file_send command."""
from __future__ import annotations

from typing import Any, Type


def get_file_send_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for file_send."""
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
        "detailed_description": "File command file_send via api.save_buffer.",
        "parameters": {
            "session_key": {"type": "string", "description": "UUID4 session identifier.", "required": True},
            "buffer_id": {"type": "string", "description": "Open buffer identifier.", "required": True},
        },
        "return_value": {
            "success": {"description": "Operation succeeded.", "data": "{result fields from api layer}"},
            "error": {"description": "Operation failed.", "code": "ErrorCode string", "message": "Human-readable message"},
        },
        "usage_examples": [
            {
                "description": "Typical file_send invocation",
                "command": {"session_key": "...", "buffer_id": "..."},
                "explanation": "Returns success envelope with result data.",
            }
        ],
        "error_cases": {
            "OPERATION_FAILED": {
                "description": "Underlying api call returned success=False.",
                "message": "{message from OperationResult}",
                "solution": "Check session_key and buffer_id; verify session is open.",
            }
        },
        "best_practices": [
            "Call init_api() before executing commands (handled by main.py startup).",
            "Use dry_run=True on destructive commands to preview changes.",
        ],
    }
