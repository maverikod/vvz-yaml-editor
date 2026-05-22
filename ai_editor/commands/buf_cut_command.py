"""buf_cut MCP command — delegates to ai_editor.api.cut."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command

from ai_editor.commands.buf_cut_metadata import get_buf_cut_metadata
from ai_editor.commands.buf_cut_schema import get_buf_cut_schema
from ai_editor import api


class BufCutCommand(Command):
    """MCP command: buf_cut."""

    name = "buf_cut"
    version = "1.0.0"
    descr = "Buf Cut"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_cut_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> dict[str, Any]:
        result = api.cut(session_key=params['session_key'], source=params['source'], dry_run=params.get('dry_run', False))
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
        return get_buf_cut_metadata(cls)
