"""yaml_get_verification MCP command — delegates to ai_editor.api.find_one."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command, CommandResult

from ai_editor.commands.yaml_get_verification_metadata import get_yaml_get_verification_metadata
from ai_editor.commands.yaml_get_verification_schema import get_yaml_get_verification_schema
from ai_editor import api


class YamlGetVerificationCommand(Command):
    """MCP command: yaml_get_verification."""

    name = "yaml_get_verification"
    version = "1.0.0"
    descr = "Yaml Get Verification"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_yaml_get_verification_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> CommandResult:
        from ai_editor.commands._result import command_result_from_api

        result = api.find_one(session_key=params['session_key'], buffer_id=params['buffer_id'], query={'kind': 'field_equals', 'field': 'verification', 'value': None})
        return command_result_from_api(result)

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        return get_yaml_get_verification_metadata(cls)
