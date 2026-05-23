"""Base MCP command classes for ai_editor."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command

from ai_editor.commands._session_validation import ensure_ca_session_alive


class EditorSessionCommand(Command):
    """Command that requires a live local + CA session before execution."""

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        session_key = params.get("session_key")
        if session_key:
            ensure_ca_session_alive(str(session_key))
        return params
