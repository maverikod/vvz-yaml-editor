"""Extended metadata for yaml_update_command command."""
from __future__ import annotations

from typing import Any, Type


def get_yaml_update_command_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for yaml_update_command."""
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
        "detailed_description": "YAML convenience command yaml_update_command.",
        "parameters": {
            "session_key": {"type": "string", "description": "UUID4 session identifier.", "required": True},
            "buffer_id": {"type": "string", "description": "Open buffer identifier.", "required": True},
            "command_name": {"type": "string", "description": "Command key to update.", "required": True},
            "patch": {"type": "object", "description": "Patch payload.", "required": True},
            "dry_run": {"type": "boolean", "description": "Preview only.", "required": False, "default": False},
        },
        "return_value": {"success": {"description": "Operation succeeded.", "data": "{result fields}"}, "error": {"description": "Operation failed.", "code": "ErrorCode string", "message": "Human-readable message"}},
        "usage_examples": [{"description": "Typical yaml_update_command invocation", "command": {"session_key": "...", "buffer_id": "...", "command_name": "foo", "patch": {}}, "explanation": "Returns success envelope with result data."}],
        "error_cases": {"OPERATION_FAILED": {"description": "Underlying api call returned success=False.", "message": "{message from OperationResult}", "solution": "Check payload and session state."}},
        "best_practices": ["Use dry_run=True for preview on write operations."],
    }
