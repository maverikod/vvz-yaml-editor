"""validate_file MCP command — delegates to ai_editor.api.validate_file."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import CommandResult

from ai_editor.commands._command_base import EditorSessionCommand

from ai_editor.commands.validate_file_metadata import get_validate_file_metadata
from ai_editor.commands.validate_file_schema import get_validate_file_schema
from ai_editor import api


class ValidateFileCommand(EditorSessionCommand):
    """MCP command: validate_file."""

    name = "validate_file"
    version = "1.0.0"
    descr = "Validate File"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_validate_file_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        has_file = bool(params.get("file_path"))
        has_buffer = bool(params.get("buffer_id"))
        if not has_file and not has_buffer:
            raise ValueError("At least one of file_path or buffer_id must be provided")
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.validate_file(session_key=params['session_key'], file_path=params.get('file_path'), buffer_id=params.get('buffer_id'), project_id=params.get('project_id'), formatter=params.get('formatter','auto'), schema=params.get('schema'))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_validate_file_metadata(cls)
