"""Helpers for MCP command return envelopes."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp_proxy_adapter.commands.base import CommandResult


def command_result_from_api(value: Any) -> CommandResult:
    """Normalize api / session layer return values to CommandResult."""
    if isinstance(value, CommandResult):
        return value
    if hasattr(value, "formatter_instance"):
        from dataclasses import fields

        payload = {
            f.name: getattr(value, f.name)
            for f in fields(value)
            if f.name not in {"formatter_instance", "tree", "formatter_name", "success"}
        }
        payload["success"] = getattr(value, "success", True)
        if not payload["success"]:
            return CommandResult(success=False, data=payload, error="buffer not found")
        return CommandResult(success=True, data=payload)
    if hasattr(value, "__dataclass_fields__"):
        payload = asdict(value)
        error_code = payload.get("error_code")
        if error_code is not None:
            payload["error_code"] = str(error_code)
        success = payload.get("success", True)
        if not success:
            return CommandResult(
                success=False,
                data=payload,
                error=str(payload.get("message") or error_code or "operation failed"),
            )
        return CommandResult(success=True, data=payload)
    if isinstance(value, dict):
        success = value.get("success", True)
        if not success:
            return CommandResult(
                success=False,
                data=value,
                error=str(value.get("message") or value.get("error") or "operation failed"),
            )
        return CommandResult(success=True, data=value)
    return CommandResult(success=True, data={"result": value})
