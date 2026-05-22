"""validate_file MCP command — delegates to ai_editor.api.validate_file."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command

from ai_editor.commands.validate_file_metadata import get_validate_file_metadata
from ai_editor.commands.validate_file_schema import get_validate_file_schema
from ai_editor import api


class ValidateFileCommand(Command):
    """MCP command: validate_file."""

    name = "validate_file"
    version = "1.0.0"
    descr = "Validate File"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_validate_file_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> dict[str, Any]:
        result = api.validate_file(session_key=params['session_key'], file_path=params.get('file_path'), buffer_id=params.get('buffer_id'), project_id=params.get('project_id'), formatter=params.get('formatter','auto'), schema=params.get('schema'))
        if hasattr(result, "__dataclass_fields__"):
            from dataclasses import asdict
            payload = asdict(result)
            if payload.get("error_code") is not None:
                payload["error_code"] = str(payload["error_code"])
            return {"success": payload.get("success", True), "data": payload}
        if isinstance(result, dict):
            return {"success": True, "data": result}
        return {"success": True, "data": result}

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_validate_file_metadata(cls)
