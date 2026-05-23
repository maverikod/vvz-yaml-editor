"""session_close MCP command — delegates to ai_editor.api.close_session."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import CommandResult

from ai_editor.commands._command_base import EditorSessionCommand

from ai_editor.commands.session_close_metadata import get_session_close_metadata
from ai_editor.commands.session_close_schema import get_session_close_schema
from ai_editor import api


class SessionCloseCommand(EditorSessionCommand):
    """MCP command: session_close."""

    name = "session_close"
    version = "1.0.0"
    descr = "Session Close"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_session_close_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.close_session(session_key=params['session_key'], force=params.get('force', False))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_session_close_metadata(cls)
