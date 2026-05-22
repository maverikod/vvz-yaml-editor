"""yaml_validate_plan_task MCP command — delegates to ai_editor.api.validate_file."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.base import Command

from ai_editor.commands.yaml_validate_plan_task_metadata import get_yaml_validate_plan_task_metadata
from ai_editor.commands.yaml_validate_plan_task_schema import get_yaml_validate_plan_task_schema
from ai_editor import api


class YamlValidatePlanTaskCommand(Command):
    """MCP command: yaml_validate_plan_task."""

    name = "yaml_validate_plan_task"
    version = "1.0.0"
    descr = "Yaml Validate Plan Task"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        return get_yaml_validate_plan_task_schema()

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().validate_params(params)
        return params

    async def execute(self, **params: Any) -> dict[str, Any]:
        result = api.validate_file(session_key=params['session_key'], file_path=params.get('file_path'), buffer_id=params.get('buffer_id'), project_id=params.get('project_id'), formatter='yaml', schema={'format': 'plan_task_v1'})
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
        return get_yaml_validate_plan_task_metadata(cls)
