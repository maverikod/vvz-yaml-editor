"""Extended metadata for buf_save_as command."""
from __future__ import annotations

from typing import Any, Type


def get_buf_save_as_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_save_as."""
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
        "detailed_description": "Extended buffer command buf_save_as.",
        "parameters": {
            "session_key": {"type": "string", "description": "UUID4 session identifier.", "required": True},
            "buffer_id": {"type": "string", "description": "Open buffer identifier.", "required": True},
            "new_relative_path": {"type": "string", "description": "New relative path.", "required": True},
            "overwrite": {"type": "boolean", "description": "Allow overwrite.", "required": False, "default": False},
            "dry_run": {"type": "boolean", "description": "Preview only.", "required": False, "default": False},
        },
        "return_value": {"success": {"description": "Operation succeeded.", "data": "{result fields}"}, "error": {"description": "Operation failed.", "code": "ErrorCode string", "message": "Human-readable message"}},
        "usage_examples": [{"description": "Typical buf_save_as invocation", "command": {"session_key": "...", "buffer_id": "...", "new_relative_path": "new.txt"}, "explanation": "Returns success envelope with result data."}],
        "error_cases": {"OPERATION_FAILED": {"description": "Underlying api call returned success=False.", "message": "{message from OperationResult}", "solution": "Check payload and session state."}},
        "best_practices": ["Use dry_run=True for preview on write operations."],
    }
