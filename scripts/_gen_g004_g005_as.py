#!/usr/bin/env python3
"""One-off generator for G-004/G-005 atomic steps. Run once then delete if desired."""
from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/plans/ai_editor"


def yaml_block(d: dict) -> str:
    import yaml

    return yaml.dump(d, sort_keys=False, allow_unicode=True, width=1000)


def write_as(rel_path: str, data: dict) -> None:
    path = PLAN / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_block(data), encoding="utf-8")
    print("wrote", path)


def update_ts_atomic(ts_rel: str, step_ids: list[str]) -> None:
    path = PLAN / ts_rel
    text = path.read_text(encoding="utf-8")
    import re

    new_list = "atomic_steps:\n" + "".join(f"- {s}\n" for s in step_ids)
    text2, n = re.subn(r"atomic_steps:\s*\[\]\s*", new_list, text, count=1)
    if n == 0:
        text2, n = re.subn(r"atomic_steps:.*?(?=\ncascade_note:|\nstatus:|\Z)", new_list, text, count=1, flags=re.S)
    if n == 0:
        raise RuntimeError(f"atomic_steps not updated in {path}")
    path.write_text(text2, encoding="utf-8")
    print("updated TS", path)


# --- G-004 ---

G004_BASE_PY = textwrap.dedent('''
"""AbstractSearch contract and SearchMatch result type."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchMatch:
    """Single search result with a tree stable_id address usable in BufferAddress.

    Attributes:
        buffer_id: Buffer containing the match.
        formatter: Formatter name (e.g. text, yaml, cst).
        address: Node stable_id (UUID str) for all formatters.
        preview: Short human-readable preview of the matched unit.
        unit_kind: Format-defined unit kind string.
        metadata: Additional match metadata from the formatter.
    """

    buffer_id: str
    formatter: str
    address: Any
    preview: str
    unit_kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AbstractSearch(ABC):
    """Search interface over a formatter in-memory Tree.

    Does not open or write files. session_key is diagnostic only.
    Delegates unit iteration and matching to formatter base hooks.
    """

    @abstractmethod
    def find(
        self,
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> list[SearchMatch]:
        """Return all units matching query within optional scope."""

    @abstractmethod
    def find_one(
        self,
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> SearchMatch | dict[str, Any]:
        """Return exactly one match or an error dict (never raises)."""

    @abstractmethod
    def list_units(
        self,
        session_key: str,
        buffer_id: str,
        scope: str | None = None,
    ) -> list[SearchMatch]:
        """List all navigable units in scope without applying a query filter."""
''').strip()

G004_INIT_1 = textwrap.dedent('''
"""Universal search layer."""
from ai_editor.search.base import AbstractSearch, SearchMatch

__all__ = ["AbstractSearch", "SearchMatch"]
''').strip()

G004_QUERY_PY = textwrap.dedent('''
"""Search query validation for universal search."""
from __future__ import annotations

from typing import Any

KNOWN_QUERY_KINDS: frozenset[str] = frozenset({
    "contains_text",
    "regex",
    "field_equals",
    "node_type",
    "xpath",
    "stable_id",
})

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
''').strip()

G004_SEARCH_PY = textwrap.dedent('''
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
''').strip()

G004_INIT_2 = textwrap.dedent('''
"""Universal search layer."""
from ai_editor.search.base import AbstractSearch, SearchMatch
from ai_editor.search.query import KNOWN_QUERY_KINDS, validate_query
from ai_editor.search.search import Search

__all__ = [
    "AbstractSearch",
    "SearchMatch",
    "Search",
    "KNOWN_QUERY_KINDS",
    "validate_query",
]
''').strip()


def g004_prompt(op: str, path: str, content: str, extra: str = "") -> str:
    pre = f"Project: ai_editor. File: {path}. Operation: {op}.\n\n"
    if op == "create_file":
        body = pre + extra + f"\n\nCreate directory ai_editor/search/ if missing. Create {path} with exactly:\n\n```python\n{content}\n```"
    else:
        body = pre + extra + f"\n\nCurrent file content:\n\n```python\n{content}\n```\n\nReplace entire file with:\n\n```python\n{NEW}\n```"
    return body


# Run generation
if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT))
    # G-004 writes
    write_as(
        "G-004-search/T-001-abstract-search/atomic_steps/A-001-search-base-py.yaml",
        {
            "step_id": "A-001",
            "parent_tactical_step": "T-001",
            "name": "Create ai_editor/search/base.py — SearchMatch and AbstractSearch",
            "target_file": "ai_editor/search/base.py",
            "operation": "create_file",
            "priority": 1,
            "depends_on": [],
            "concepts": ["C-035", "C-036"],
            "status": "draft",
            "prompt": (
                "Project: ai_editor. Tactical step G-004/T-001. File: ai_editor/search/base.py. Operation: create_file.\n\n"
                "MRS:\n"
                "  C-035 AbstractSearch: find, find_one, list_units over formatter Tree; no file I/O; session_key diagnostic only.\n"
                "  C-036 SearchMatch: buffer_id, formatter, address (node stable_id for all formatters), preview, unit_kind, metadata.\n\n"
                "Preconditions: ai_editor/contracts/error_codes.py exists (SEARCH_NO_MATCH, SEARCH_MULTIPLE_MATCHES for find_one errors in concrete impl).\n\n"
                f"Create ai_editor/search/ if missing. Create ai_editor/search/base.py with exactly:\n\n```python\n{G004_BASE_PY}\n```\n\n"
                "Constraints: under 120 lines; no concrete Search class here; Google-style docstrings on public types."
            ),
            "verification": {
                "type": "import",
                "target": "ai_editor.search.base",
                "expected": "SearchMatch and AbstractSearch import; SearchMatch has buffer_id, formatter, address, preview, unit_kind, metadata fields.",
            },
        },
    )
    write_as(
        "G-004-search/T-001-abstract-search/atomic_steps/A-002-search-init-py.yaml",
        {
            "step_id": "A-002",
            "parent_tactical_step": "T-001",
            "name": "Create ai_editor/search/__init__.py — export base types",
            "target_file": "ai_editor/search/__init__.py",
            "operation": "create_file",
            "priority": 1,
            "depends_on": [],
            "concepts": ["C-035", "C-036"],
            "status": "draft",
            "prompt": (
                "Project: ai_editor. File: ai_editor/search/__init__.py. Operation: create_file.\n\n"
                "Precondition: ai_editor/search/base.py exists with AbstractSearch and SearchMatch.\n\n"
                f"Create ai_editor/search/__init__.py with exactly:\n\n```python\n{G004_INIT_1}\n```"
            ),
            "verification": {
                "type": "import",
                "target": "ai_editor.search",
                "expected": "from ai_editor.search import AbstractSearch, SearchMatch succeeds.",
            },
        },
    )
    write_as(
        "G-004-search/T-002-query-model/atomic_steps/A-001-search-query-py.yaml",
        {
            "step_id": "A-001",
            "parent_tactical_step": "T-002",
            "name": "Create ai_editor/search/query.py — query validation",
            "target_file": "ai_editor/search/query.py",
            "operation": "create_file",
            "priority": 1,
            "depends_on": [],
            "concepts": ["C-037"],
            "status": "draft",
            "prompt": (
                "Project: ai_editor. G-004/T-002. File: ai_editor/search/query.py. Operation: create_file.\n\n"
                "MRS C-037 SearchQuery: base fields kind, value, options; text kinds contains_text, regex; "
                "yaml kinds field_equals, node_type; cst kinds xpath, stable_id.\n\n"
                f"Create ai_editor/search/query.py with exactly:\n\n```python\n{G004_QUERY_PY}\n```\n\n"
                "Constraints: KNOWN_QUERY_KINDS has exactly six entries; validate_query returns list[str] (empty when valid)."
            ),
            "verification": {
                "type": "import",
                "target": "ai_editor.search.query",
                "expected": "validate_query({'kind':'contains_text','value':'x'}) == []; validate_query({'kind':'bad'}) is non-empty.",
            },
        },
    )
    write_as(
        "G-004-search/T-003-find-find-one/atomic_steps/A-001-search-impl-py.yaml",
        {
            "step_id": "A-001",
            "parent_tactical_step": "T-003",
            "name": "Create ai_editor/search/search.py — Search implementation",
            "target_file": "ai_editor/search/search.py",
            "operation": "create_file",
            "priority": 1,
            "depends_on": [],
            "concepts": ["C-035", "C-036", "C-037"],
            "status": "draft",
            "prompt": (
                "Project: ai_editor. G-004/T-003. File: ai_editor/search/search.py. Operation: create_file.\n\n"
                "MRS: C-035 AbstractSearch concrete impl; C-036 SearchMatch; C-037 validate_query.\n"
                "Uses formatter.iter_units(tree, scope) and formatter.match_unit(unit, query). "
                "SearchMatch.address is unit stable_id. No public select(). find_one returns SearchMatch or error dict "
                "with ErrorCode SEARCH_NO_MATCH | SEARCH_MULTIPLE_MATCHES | SEARCH_INVALID_QUERY.\n\n"
                "Preconditions:\n"
                "  ai_editor/search/base.py, ai_editor/search/query.py exist.\n"
                "  ai_editor/formatters/base.py AbstractFormatter defines iter_units, match_unit.\n\n"
                f"Create ai_editor/search/search.py with exactly:\n\n```python\n{G004_SEARCH_PY}\n```\n\n"
                "Constraints: under 200 lines; no file I/O; session_key passed through but only used in get_buffer_fn call."
            ),
            "verification": {
                "type": "import",
                "target": "ai_editor.search.search",
                "expected": "Search class imports; constructor accepts get_buffer_fn callable.",
            },
        },
    )
    write_as(
        "G-004-search/T-003-find-find-one/atomic_steps/A-002-search-init-exports.yaml",
        {
            "step_id": "A-002",
            "parent_tactical_step": "T-003",
            "name": "Modify ai_editor/search/__init__.py — export Search and query helpers",
            "target_file": "ai_editor/search/__init__.py",
            "operation": "modify_file",
            "priority": 2,
            "depends_on": ["A-001"],
            "concepts": ["C-035", "C-037"],
            "status": "draft",
            "prompt": (
                "Project: ai_editor. File: ai_editor/search/__init__.py. Operation: modify_file.\n\n"
                "Preconditions: ai_editor/search/search.py exists with Search class; ai_editor/search/query.py exists.\n\n"
                "Current file content:\n\n```python\n"
                + G004_INIT_1
                + "\n```\n\nReplace entire file with:\n\n```python\n"
                + G004_INIT_2
                + "\n```"
            ),
            "verification": {
                "type": "import",
                "target": "ai_editor.search",
                "expected": "from ai_editor.search import Search, validate_query, KNOWN_QUERY_KINDS succeeds.",
            },
        },
    )
    update_ts_atomic("G-004-search/T-001-abstract-search/README.yaml", ["A-001", "A-002"])
    update_ts_atomic("G-004-search/T-002-query-model/README.yaml", ["A-001"])
    update_ts_atomic("G-004-search/T-003-find-find-one/README.yaml", ["A-001", "A-002"])
    print("G-004 done")
