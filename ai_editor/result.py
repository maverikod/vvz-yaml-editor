"""Shim replacing mcp_proxy_adapter SuccessResult/ErrorResult for standalone use."""
from __future__ import annotations
from typing import Any


def SuccessResult(data: dict[str, Any]) -> dict[str, Any]:
    """Return a success envelope dict matching mcp_proxy_adapter contract.

    Args:
        data: Payload fields to merge into the result.

    Returns:
        dict with success=True and all keys from data.
    """
    return {"success": True, **data}


def ErrorResult(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an error envelope dict matching mcp_proxy_adapter contract.

    Args:
        code: Stable error code string.
        message: Human-readable error message.
        details: Optional additional diagnostic fields.

    Returns:
        dict with success=False, error_code, message, details.
    """
    return {
        "success": False,
        "error_code": code,
        "message": message,
        "details": details or {},
    }
