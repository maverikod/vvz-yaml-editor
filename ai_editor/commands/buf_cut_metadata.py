"""Extended metadata for buf_cut command."""
from __future__ import annotations

from typing import Any, Type


def get_buf_cut_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_cut."""
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
        "detailed_description": "Clipboard command buf_cut via api.cut.",
        "parameters": {
            "session_key": {"type": "string", "description": "UUID4 session identifier.", "required": True},
            "source": {"type": "object", "description": "Source address payload.", "required": True},
            "dry_run": {"type": "boolean", "description": "Preview only.", "required": False, "default": False},
        },
        "return_value": {"success": {"description": "Operation succeeded.", "data": "{result fields}"}, "error": {"description": "Operation failed.", "code": "ErrorCode string", "message": "Human-readable message"}},
        "usage_examples": [{"description": "Typical buf_cut invocation", "command": {"session_key": "...", "source": {"buffer_id": "...", "address": {}}}, "explanation": "Returns success envelope with result data."}],
        "error_cases": {"OPERATION_FAILED": {"description": "Underlying api call returned success=False.", "message": "{message from OperationResult}", "solution": "Check input payload and session state."}},
        "best_practices": ["Use dry_run=True for preview on destructive operations."],
    }
