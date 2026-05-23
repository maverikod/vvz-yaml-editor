"""buf_copy MCP command — delegates to ai_editor.api.copy."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import CommandResult

from ai_editor.commands._command_base import EditorSessionCommand

from ai_editor.commands.buf_copy_metadata import get_buf_copy_metadata
from ai_editor.commands.buf_copy_schema import get_buf_copy_schema
from ai_editor import api


class BufCopyCommand(EditorSessionCommand):
    """MCP command: buf_copy."""

    name = "buf_copy"
    version = "1.0.0"
    descr = "Buf Copy"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_copy_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.copy(session_key=params['session_key'], source=params['source'])
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_buf_copy_metadata(cls)
