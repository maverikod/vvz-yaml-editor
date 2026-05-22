"""Search query validation for universal search."""
from __future__ import annotations

from typing import Any

KNOWN_QUERY_KINDS: frozenset[str] = frozenset(
    {
        "contains_text",
        "regex",
        "field_equals",
        "node_type",
        "xpath",
        "stable_id",
    }
)

_REQUIRED_BY_KIND: dict[str, list[str]] = {
    "contains_text": ["value"],
    "regex": ["value"],
    "field_equals": ["field", "value"],
    "node_type": ["value"],
    "xpath": ["value"],
    "stable_id": ["value"],
}


def validate_query(query: dict[str, Any]) -> list[str]:
    """Validate query shape. Return empty list when valid, else human-readable errors."""
    errors: list[str] = []
    if not isinstance(query, dict):
        return ["query must be a dict"]
    kind = query.get("kind")
    if not kind or not isinstance(kind, str):
        errors.append("query.kind is required and must be a string")
        return errors
    if kind not in KNOWN_QUERY_KINDS:
        errors.append(f"unknown query kind: {kind}")
        return errors
    for field in _REQUIRED_BY_KIND.get(kind, []):
        if field not in query:
            errors.append(f"query.{field} is required for kind={kind}")
    if "options" in query and query["options"] is not None and not isinstance(query["options"], dict):
        errors.append("query.options must be a dict when present")
    return errors
