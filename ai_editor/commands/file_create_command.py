"""file_create MCP command — delegates to ai_editor.api.new_buffer."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command

from ai_editor.commands.file_create_metadata import get_file_create_metadata
from ai_editor.commands.file_create_schema import get_file_create_schema
from ai_editor import api


class FileCreateCommand(Command):
    """MCP command: file_create."""

    name = "file_create"
    version = "1.0.0"
    descr = "File Create"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_file_create_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> dict[str, Any]:
        result = api.new_buffer(session_key=params['session_key'], formatter_name=params.get('formatter','auto'), initial_content=params.get('content',''), display_name=params.get('display_name'))
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
        return get_file_create_metadata(cls)
