"""buf_paste MCP command — delegates to ai_editor.api.paste."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import CommandResult

from ai_editor.commands._command_base import EditorSessionCommand

from ai_editor.commands.buf_paste_metadata import get_buf_paste_metadata
from ai_editor.commands.buf_paste_schema import get_buf_paste_schema
from ai_editor import api


class BufPasteCommand(EditorSessionCommand):
    """MCP command: buf_paste."""

    name = "buf_paste"
    version = "1.0.0"
    descr = "Buf Paste"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_paste_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.paste(session_key=params['session_key'], target=params['target'], mode=params['mode'], dry_run=params.get('dry_run', False))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_buf_paste_metadata(cls)
