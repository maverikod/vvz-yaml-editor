"""buf_save_as MCP command — delegates to ai_editor.api.save_as_buffer."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command

from ai_editor.commands.buf_save_as_metadata import get_buf_save_as_metadata
from ai_editor.commands.buf_save_as_schema import get_buf_save_as_schema
from ai_editor import api


class BufSaveAsCommand(Command):
    """MCP command: buf_save_as."""

    name = "buf_save_as"
    version = "1.0.0"
    descr = "Buf Save As"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_save_as_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> dict[str, Any]:
        result = api.save_as_buffer(session_key=params['session_key'], buffer_id=params['buffer_id'], new_relative_path=params['new_relative_path'], overwrite=params.get('overwrite',False), dry_run=params.get('dry_run',False))
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
        return get_buf_save_as_metadata(cls)
