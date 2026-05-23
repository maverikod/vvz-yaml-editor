"""session_status MCP command — delegates to ai_editor.api.session_status."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import CommandResult

from ai_editor.commands._command_base import EditorSessionCommand

from ai_editor.commands.session_status_metadata import get_session_status_metadata
from ai_editor.commands.session_status_schema import get_session_status_schema
from ai_editor import api


class SessionStatusCommand(EditorSessionCommand):
    """MCP command: session_status."""

    name = "session_status"
    version = "1.0.0"
    descr = "Session Status"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_session_status_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.session_status(session_key=params['session_key'])
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_session_status_metadata(cls)
