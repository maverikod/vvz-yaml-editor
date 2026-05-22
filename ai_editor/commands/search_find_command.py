"""search_find MCP command — delegates to ai_editor.api.find."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.search_find_metadata import get_search_find_metadata
from ai_editor.commands.search_find_schema import get_search_find_schema
from ai_editor import api


class SearchFindCommand(Command):
    """MCP command: search_find."""

    name = "search_find"
    version = "1.0.0"
    descr = "Search Find"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_search_find_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        from ai_editor.search.query import validate_query

        query = params.get("query")
        if query is not None:
            errs = validate_query(query)
            if errs:
                raise ValueError("; ".join(errs))
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.find(session_key=params['session_key'], buffer_id=params['buffer_id'], query=params['query'], scope=params.get('scope'))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_search_find_metadata(cls)
