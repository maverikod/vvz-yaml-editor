"""Concrete Search implementation delegating to formatter tree hooks."""
from __future__ import annotations

from typing import Any, Callable

from ai_editor.contracts import ErrorCode
from ai_editor.search.base import AbstractSearch, SearchMatch
from ai_editor.search.query import validate_query


class Search(AbstractSearch):
    """Search over in-memory formatter trees via iter_units/match_unit."""

    def __init__(
        self,
        get_buffer_fn: Callable[[str, str], dict[str, Any] | None],
    ) -> None:
        """Args:
            get_buffer_fn: (session_key, buffer_id) -> dict with keys
                formatter (instance), tree, buffer_id, formatter_name; or None if missing.
        """
        self._get_buffer = get_buffer_fn

    def _resolve(self, session_key: str, buffer_id: str) -> tuple[Any, Any, str] | dict[str, Any]:
        ctx = self._get_buffer(session_key, buffer_id)
        if ctx is None:
            return {
                "success": False,
                "error_code": ErrorCode.BUFFER_NOT_FOUND,
                "message": f"buffer not found: {buffer_id}",
            }
        formatter = ctx["formatter"]
        tree = ctx["tree"]
        name = ctx.get("formatter_name") or getattr(formatter, "formatter_name", "")
        return formatter, tree, name

    def _unit_to_match(self, buffer_id: str, formatter_name: str, unit: Any) -> SearchMatch:
        address = getattr(unit, "address", None) or getattr(unit, "stable_id", "")
        preview = getattr(unit, "preview", "") or getattr(unit, "display_text", "")
        unit_kind = getattr(unit, "unit_kind", "") or getattr(unit, "node_kind", "")
        metadata = getattr(unit, "metadata", None) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return SearchMatch(
            buffer_id=buffer_id,
            formatter=formatter_name,
            address=address,
            preview=str(preview),
            unit_kind=str(unit_kind),
            metadata=metadata,
        )

    def list_units(
        self,
        session_key: str,
        buffer_id: str,
        scope: str | None = None,
    ) -> list[SearchMatch]:
        resolved = self._resolve(session_key, buffer_id)
        if isinstance(resolved, dict):
            return []
        formatter, tree, formatter_name = resolved
        matches: list[SearchMatch] = []
        for unit in formatter.iter_units(tree, scope=scope):
            matches.append(self._unit_to_match(buffer_id, formatter_name, unit))
        return matches

    def find(
        self,
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> list[SearchMatch]:
        errs = validate_query(query)
        if errs:
            return []
        resolved = self._resolve(session_key, buffer_id)
        if isinstance(resolved, dict):
            return []
        formatter, tree, formatter_name = resolved
        out: list[SearchMatch] = []
        for unit in formatter.iter_units(tree, scope=scope):
            if formatter.match_unit(unit, query):
                out.append(self._unit_to_match(buffer_id, formatter_name, unit))
        return out

    def find_one(
        self,
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> SearchMatch | dict[str, Any]:
        errs = validate_query(query)
        if errs:
            return {
                "success": False,
                "error_code": ErrorCode.SEARCH_QUERY_INVALID,
                "message": "; ".join(errs),
            }
        matches = self.find(session_key, buffer_id, query, scope=scope)
        if not matches:
            return {
                "success": False,
                "error_code": ErrorCode.SEARCH_NO_MATCH,
                "message": "no match found",
            }
        if len(matches) > 1:
            return {
                "success": False,
                "error_code": ErrorCode.SEARCH_NOT_UNIQUE,
                "message": f"expected one match, found {len(matches)}",
            }
        return matches[0]
