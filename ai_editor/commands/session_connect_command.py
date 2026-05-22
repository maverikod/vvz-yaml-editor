"""session_connect MCP command — delegates to ai_editor.api.connect."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.session_connect_metadata import get_session_connect_metadata
from ai_editor.commands.session_connect_schema import get_session_connect_schema
from ai_editor import api


class SessionConnectCommand(Command):
    """MCP command: session_connect."""

    name = "session_connect"
    version = "1.0.0"
    descr = "Session Connect"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_session_connect_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.connect(readonly=params.get('readonly', False))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_session_connect_metadata(cls)
