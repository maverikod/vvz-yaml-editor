"""file_send MCP command — delegates to ai_editor.api.save_buffer."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.file_send_metadata import get_file_send_metadata
from ai_editor.commands.file_send_schema import get_file_send_schema
from ai_editor import api


class FileSendCommand(Command):
    """MCP command: file_send."""

    name = "file_send"
    version = "1.0.0"
    descr = "File Send"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_file_send_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.save_buffer(session_key=params['session_key'], buffer_id=params['buffer_id'], dry_run=params.get('dry_run',False))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_file_send_metadata(cls)
