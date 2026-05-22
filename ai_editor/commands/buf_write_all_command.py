"""buf_write_all MCP command — delegates to ai_editor.api.write_all."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.buf_write_all_metadata import get_buf_write_all_metadata
from ai_editor.commands.buf_write_all_schema import get_buf_write_all_schema
from ai_editor import api


class BufWriteAllCommand(Command):
    """MCP command: buf_write_all."""

    name = "buf_write_all"
    version = "1.0.0"
    descr = "Buf Write All"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_write_all_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.write_all(session_key=params['session_key'], force=params.get('force',False), dry_run=params.get('dry_run',False))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_buf_write_all_metadata(cls)
