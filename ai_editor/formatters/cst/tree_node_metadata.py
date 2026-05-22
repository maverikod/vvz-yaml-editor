"""CST TreeNodeMetadata and sidecar serialisation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

DOCSTRING_KEYS = ("summary", "args", "returns", "attributes", "docstring_body")


def validate_docstring_dict(value: Any) -> Optional[dict[str, Any]]:
    """Validate and normalize a sidecar docstring payload."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("docstring must be dict or null")
    unknown = set(value) - set(DOCSTRING_KEYS)
    if unknown:
        raise ValueError(f"unknown docstring keys: {sorted(unknown)}")

    normalized: dict[str, Any] = {}
    summary = str(value.get("summary", "") or "").strip()
    returns = str(value.get("returns", "") or "").strip()
    body = str(value.get("docstring_body", "") or "").strip()

    args_raw = value.get("args", {})
    attrs_raw = value.get("attributes", {})
    if args_raw is None:
        args_raw = {}
    if attrs_raw is None:
        attrs_raw = {}
    if not isinstance(args_raw, dict) or not isinstance(attrs_raw, dict):
        raise ValueError("docstring args/attributes must be dict")

    args = {str(k): str(v) for k, v in args_raw.items() if str(v)}
    attributes = {str(k): str(v) for k, v in attrs_raw.items() if str(v)}

    if summary:
        normalized["summary"] = summary
    if args:
        normalized["args"] = args
    if returns:
        normalized["returns"] = returns
    if attributes:
        normalized["attributes"] = attributes
    if body:
        normalized["docstring_body"] = body
    return normalized


@dataclass(frozen=True)
class TreeNodeMetadata:
    """Per-node CST metadata; sidecar stores stable_id/start_line/end_line/docstring subset."""

    node_id: str
    stable_id: str
    type: str
    kind: str
    name: Optional[str] = None
    qualname: Optional[str] = None
    decorators: tuple[str, ...] = ()
    start_line: int = 1
    end_line: int = 1
    start_col: int = 0
    end_col: int = 0
    children_count: int = 0
    children_ids: tuple[str, ...] = ()
    parent_id: Optional[str] = None
    docstring: Optional[dict[str, Any]] = None

    def to_sidecar_dict(self) -> dict[str, Any]:
        """Serialise sidecar-facing fields only (C-032 / C-034)."""
        return {
            "stable_id": self.stable_id,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "docstring": self.docstring,
        }

    @classmethod
    def from_sidecar_dict(
        cls,
        node_id: str,
        data: Mapping[str, Any],
        *,
        type: str = "Module",
        kind: str = "module",
    ) -> TreeNodeMetadata:
        """Rebuild runtime metadata from sidecar entry; fills index fields with defaults."""
        doc_raw = data.get("docstring")
        doc = validate_docstring_dict(doc_raw) if doc_raw is not None else None
        stable = str(data.get("stable_id") or node_id)
        return cls(
            node_id=node_id,
            stable_id=stable,
            type=type,
            kind=kind,
            start_line=int(data.get("start_line", 1)),
            end_line=int(data.get("end_line", 1)),
            docstring=doc,
        )
