"""file_open MCP command — delegates to ai_editor.api.open_buffer."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import CommandResult

from ai_editor.commands._command_base import EditorSessionCommand

from ai_editor.commands.file_open_metadata import get_file_open_metadata
from ai_editor.commands.file_open_schema import get_file_open_schema
from ai_editor import api


class FileOpenCommand(EditorSessionCommand):
    """MCP command: file_open."""

    name = "file_open"
    version = "1.0.0"
    descr = "File Open"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_file_open_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.open_buffer(
            session_key=params["session_key"],
            project_id=params["project_id"],
            file_path=params["file_path"],
            formatter=params.get("formatter", "auto"),
            open_as_text=params.get("open_as_text", False),
            readonly=params.get("readonly", False),
        )
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_file_open_metadata(cls)
