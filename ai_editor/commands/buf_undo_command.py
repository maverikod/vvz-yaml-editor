"""buf_undo MCP command — delegates to ai_editor.api.undo."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command

from ai_editor.commands.buf_undo_metadata import get_buf_undo_metadata
from ai_editor.commands.buf_undo_schema import get_buf_undo_schema
from ai_editor import api


class BufUndoCommand(Command):
    """MCP command: buf_undo."""

    name = "buf_undo"
    version = "1.0.0"
    descr = "Buf Undo"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_undo_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> dict[str, Any]:
        result = api.undo(session_key=params['session_key'], buffer_id=params['buffer_id'], steps=params.get('steps', 1))
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
        return get_buf_undo_metadata(cls)
