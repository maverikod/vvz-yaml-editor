"""MdNode: document model node for MarkdownFormatter."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MdNode:
    """Represents one structural node in a Markdown document tree."""

    node_type: str
    content: str = ""
    level: int | None = None
    children: list[MdNode] = field(default_factory=list)
    attrs: dict[str, Any] = field(default_factory=dict)
    source_pos: tuple[int, int] | None = None
