"""Extended metadata for buf_mutate_batch command."""
from __future__ import annotations

from typing import Any, Type


def get_buf_mutate_batch_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_mutate_batch."""
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
        "detailed_description": "Extended buffer command buf_mutate_batch.",
        "parameters": {
            "session_key": {"type": "string", "description": "UUID4 session identifier.", "required": True},
            "buffer_id": {"type": "string", "description": "Open buffer identifier.", "required": True},
            "operations": {"type": "array", "description": "Mutation operations.", "required": True},
            "dry_run": {"type": "boolean", "description": "Preview only.", "required": False, "default": False},
        },
        "return_value": {"success": {"description": "Operation succeeded.", "data": "{result fields}"}, "error": {"description": "Operation failed.", "code": "ErrorCode string", "message": "Human-readable message"}},
        "usage_examples": [{"description": "Typical buf_mutate_batch invocation", "command": {"session_key": "...", "buffer_id": "...", "operations": []}, "explanation": "Returns success envelope with result data."}],
        "error_cases": {"OPERATION_FAILED": {"description": "Underlying api call returned success=False.", "message": "{message from OperationResult}", "solution": "Check payload and session state."}},
        "best_practices": ["Use dry_run=True for preview on write operations."],
    }
