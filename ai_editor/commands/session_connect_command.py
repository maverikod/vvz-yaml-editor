"""session_connect MCP command — delegates to ai_editor.api.connect."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.session_connect_metadata import get_session_connect_metadata
from ai_editor.commands.session_connect_schema import get_session_connect_schema
from ai_editor.contracts import ErrorCode
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
        from code_analysis_client import SessionNotFoundError

        from ai_editor.api_init import get_session_manager

        params = super().validate_params(params)
        ca_session_id = str(params.get("ca_session_id") or "").strip()
        if not ca_session_id:
            raise ValueError("ca_session_id is required")
        params["ca_session_id"] = ca_session_id
        try:
            get_session_manager().ca_client.assert_session_exists(ca_session_id)
        except SessionNotFoundError as exc:
            raise ValueError(ErrorCode.SESSION_NOT_FOUND.value) from exc
        params.setdefault("readonly", False)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        try:
            result = api.connect(
                readonly=params.get("readonly", False),
                ca_session_id=params["ca_session_id"],
            )
        except ValueError as exc:
            message = str(exc)
            error_code = message if message in {item.value for item in ErrorCode} else (
                ErrorCode.SESSION_REGISTRATION_FAILED.value
            )
            return CommandResult(
                success=False,
                data={
                    "success": False,
                    "error_code": error_code,
                    "message": message,
                },
                error=message,
            )
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_session_connect_metadata(cls)
