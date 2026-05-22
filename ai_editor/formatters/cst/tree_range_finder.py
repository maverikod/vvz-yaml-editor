"""Find CST nodes by source line range."""
from __future__ import annotations

from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.tree_node_metadata import TreeNodeMetadata


def find_node_by_range(
    tree: CSTTree,
    start_line: int,
    end_line: int,
    prefer_exact: bool = False,
) -> TreeNodeMetadata | None:
    """Find metadata for the node covering [start_line, end_line] inclusive."""
    if start_line > end_line:
        raise ValueError(f"Invalid range: start_line ({start_line}) > end_line ({end_line})")
    candidates = [
        meta
        for meta in tree.metadata_map.values()
        if meta.start_line <= start_line and end_line <= meta.end_line
    ]
    if not candidates:
        return None
    if prefer_exact:
        for candidate in candidates:
            if candidate.start_line == start_line and candidate.end_line == end_line:
                return candidate
    return min(candidates, key=lambda m: (m.end_line - m.start_line, m.start_line))
