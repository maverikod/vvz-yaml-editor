"""Extended metadata for buf_write_all command."""
from __future__ import annotations

from typing import Any, Type


def get_buf_write_all_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_write_all."""
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
        "detailed_description": "Extended buffer command buf_write_all.",
        "parameters": {
            "session_key": {"type": "string", "description": "UUID4 session identifier.", "required": True},
            "force": {"type": "boolean", "description": "Force write all buffers.", "required": False, "default": False},
            "dry_run": {"type": "boolean", "description": "Preview only.", "required": False, "default": False},
        },
        "return_value": {"success": {"description": "Operation succeeded.", "data": "{result fields}"}, "error": {"description": "Operation failed.", "code": "ErrorCode string", "message": "Human-readable message"}},
        "usage_examples": [{"description": "Typical buf_write_all invocation", "command": {"session_key": "...", "force": False}, "explanation": "Returns success envelope with result data."}],
        "error_cases": {"OPERATION_FAILED": {"description": "Underlying api call returned success=False.", "message": "{message from OperationResult}", "solution": "Check payload and session state."}},
        "best_practices": ["Use dry_run=True for preview on write operations."],
    }
