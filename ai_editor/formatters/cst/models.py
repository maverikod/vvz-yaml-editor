"""CSTTree - in-memory Python CST document model."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import libcst as cst

from ai_editor.formatters.cst.tree_node_metadata import TreeNodeMetadata


@dataclass
class CSTTree:
    """CST specialisation of generic Tree for one open .py document."""

    tree_id: str
    module: cst.Module
    metadata_map: dict[str, TreeNodeMetadata] = field(default_factory=dict)
    node_map: dict[str, cst.CSTNode] = field(default_factory=dict)
    parent_map: dict[str, str] = field(default_factory=dict)
    node_id_aliases: dict[str, str] = field(default_factory=dict)
    root_node_id: str = ""

    @classmethod
    def create(cls, module: cst.Module) -> CSTTree:
        """Create CSTTree with a fresh runtime tree_id UUID4 string."""
        return cls(tree_id=str(uuid.uuid4()), module=module)

    def find_by_stable_id(self, stable_id: str) -> TreeNodeMetadata | None:
        """Return metadata for stable_id or None."""
        for meta in self.metadata_map.values():
            if meta.stable_id == stable_id:
                return meta
        return None
