"""yaml_update_command MCP command — delegates to ai_editor.api.mutate_batch."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command

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

    async def execute(self, **params: Any) -> dict[str, Any]:
        result = api.mutate_batch(session_key=params['session_key'], buffer_id=params['buffer_id'], operations=[{'op': 'set', 'address': params['command_name'], 'value': v} for k, v in params['patch'].items()], dry_run=params.get('dry_run', False))
        if hasattr(result, "__dataclass_fields__"):
            from dataclasses import asdict
            payload = asdict(result)
            if payload.get("error_code") is not None:
                payload["error_code"] = str(payload["error_code"])
            return {"success": payload.get("success", True), "data": payload}
        if isinstance(result, dict):
            return {"success": True, "data": result}
        return {"success": True, "data": result}

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_yaml_update_command_metadata(cls)
