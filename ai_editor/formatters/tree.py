"""Generic in-memory tree model for all ai_editor formatters."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TreeNode:
    """Single node in a formatter Tree.

    Attributes:
        stable_id: UUID4 string assigned by AbstractFormatter base; empty before assignment.
        node_kind: Format-defined kind string (e.g. paragraph, mapping, root).
        start_line: 1-based inclusive start line in source coordinates.
        end_line: 1-based inclusive end line.
        display_text: Short label for UI/skeleton.
        metadata: Format-specific payload; must not store stable_id for subclass use.
        children: Ordered child nodes.
    """

    stable_id: str
    node_kind: str
    start_line: int
    end_line: int
    display_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[TreeNode] = field(default_factory=list)


@dataclass
class Tree:
    """In-memory tree for one open buffer document.

    Attributes:
        root: Root TreeNode for the document.
    """

    root: TreeNode
