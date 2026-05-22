"""buf_reload MCP command — delegates to ai_editor.api.reload_buffer."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.buf_reload_metadata import get_buf_reload_metadata
from ai_editor.commands.buf_reload_schema import get_buf_reload_schema
from ai_editor import api


class BufReloadCommand(Command):
    """MCP command: buf_reload."""

    name = "buf_reload"
    version = "1.0.0"
    descr = "Buf Reload"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_reload_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.reload_buffer(session_key=params['session_key'], buffer_id=params['buffer_id'])
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_buf_reload_metadata(cls)
