"""formatter_commands MCP command — delegates to ai_editor.api.formatter_commands."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.formatter_commands_metadata import get_formatter_commands_metadata
from ai_editor.commands.formatter_commands_schema import get_formatter_commands_schema
from ai_editor import api


class FormatterCommandsCommand(Command):
    """MCP command: formatter_commands."""

    name = "formatter_commands"
    version = "1.0.0"
    descr = "Formatter Commands"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_formatter_commands_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.formatter_commands(buffer_id=params.get('buffer_id'), formatter=params.get('formatter'))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_formatter_commands_metadata(cls)
