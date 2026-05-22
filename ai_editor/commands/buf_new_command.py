"""buf_new MCP command — delegates to ai_editor.api.new_buffer."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.buf_new_metadata import get_buf_new_metadata
from ai_editor.commands.buf_new_schema import get_buf_new_schema
from ai_editor import api


class BufNewCommand(Command):
    """MCP command: buf_new."""

    name = "buf_new"
    version = "1.0.0"
    descr = "Buf New"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_new_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.new_buffer(session_key=params['session_key'], formatter_name=params.get('formatter','auto'), initial_content=params.get('content',''), display_name=params.get('display_name'))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_buf_new_metadata(cls)
