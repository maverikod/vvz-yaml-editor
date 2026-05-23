"""session_close_invalid MCP command — close editor sessions dead on CA."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.session_close_invalid_metadata import get_session_close_invalid_metadata
from ai_editor.commands.session_close_invalid_schema import get_session_close_invalid_schema
from ai_editor.contracts import ErrorCode
from ai_editor import api

_CLOSE_MODES = frozenset({"release_ca", "local_only"})


class SessionCloseInvalidCommand(Command):
    """MCP command: session_close_invalid."""

    name = "session_close_invalid"
    version = "1.0.0"
    descr = "Session Close Invalid"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_session_close_invalid_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        from pathlib import Path

        from ai_editor.api_init import get_session_manager

        params = super().validate_params(params)
        session_key = str(params.get("session_key") or "").strip()
        if not session_key:
            raise ValueError("session_key is required")
        params["session_key"] = session_key

        manager = get_session_manager()
        if not (Path(manager.base_dir) / session_key).is_dir():
            raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)

        mode = params.get("mode", "local_only")
        if mode not in _CLOSE_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(_CLOSE_MODES))}")
        params["mode"] = mode
        params.setdefault("force", False)
        params.setdefault("dry_run", False)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.close_invalid_sessions(
            session_key=params["session_key"],
            mode=params["mode"],
            force=params.get("force", False),
            dry_run=params.get("dry_run", False),
        )
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_session_close_invalid_metadata(cls)
