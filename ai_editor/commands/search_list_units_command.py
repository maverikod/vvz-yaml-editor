"""search_list_units MCP command — delegates to ai_editor.api.list_units."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import CommandResult

from ai_editor.commands._command_base import EditorSessionCommand

from ai_editor.commands.search_list_units_metadata import get_search_list_units_metadata
from ai_editor.commands.search_list_units_schema import get_search_list_units_schema
from ai_editor import api


class SearchListUnitsCommand(EditorSessionCommand):
    """MCP command: search_list_units."""

    name = "search_list_units"
    version = "1.0.0"
    descr = "Search List Units"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_search_list_units_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.list_units(session_key=params['session_key'], buffer_id=params['buffer_id'], scope=params.get('scope'))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_search_list_units_metadata(cls)
