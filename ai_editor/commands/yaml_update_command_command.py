"""yaml_update_command MCP command — delegates to ai_editor.api.mutate_batch."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.yaml_update_command_metadata import get_yaml_update_command_metadata
from ai_editor.commands.yaml_update_command_schema import get_yaml_update_command_schema
from ai_editor import api


class YamlUpdateCommandCommand(Command):
    """MCP command: yaml_update_command."""

    name = "yaml_update_command"
    version = "1.0.0"
    descr = "Yaml Update Command"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_yaml_update_command_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.mutate_batch(session_key=params['session_key'], buffer_id=params['buffer_id'], operations=[{'op': 'set', 'address': params['command_name'], 'value': v} for k, v in params['patch'].items()], dry_run=params.get('dry_run', False))
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_yaml_update_command_metadata(cls)
