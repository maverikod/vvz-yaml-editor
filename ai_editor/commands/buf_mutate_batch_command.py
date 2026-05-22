"""buf_mutate_batch MCP command — delegates to ai_editor.api.mutate_batch."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.buf_mutate_batch_metadata import get_buf_mutate_batch_metadata
from ai_editor.commands.buf_mutate_batch_schema import get_buf_mutate_batch_schema
from ai_editor import api


class BufMutateBatchCommand(Command):
    """MCP command: buf_mutate_batch."""

    name = "buf_mutate_batch"
    version = "1.0.0"
    descr = "Buf Mutate Batch"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_buf_mutate_batch_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.mutate_batch(session_key=params['session_key'], buffer_id=params['buffer_id'], operations=params['operations'], dry_run=params.get('dry_run',False))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_buf_mutate_batch_metadata(cls)
