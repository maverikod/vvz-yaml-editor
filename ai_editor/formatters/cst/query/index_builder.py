"""Index CSTTree nodes for XPath-like query execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider, PositionProvider

from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.node_id_markers import PersistedNodeIds, strip_persisted_node_ids
from ai_editor.formatters.cst.node_stable_id import strip_inline_node_id_lines_from_source
from ai_editor.formatters.cst.tree_builder import create_tree_from_code


@dataclass(frozen=True)
class Match:
    stable_id: str
    kind: str
    node_type: str
    name: Optional[str]
    qualname: Optional[str]
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    code: Optional[str] = None


@dataclass(frozen=True)
class NodeInfo:
    node: cst.CSTNode
    parent: Optional[cst.CSTNode]
    depth: int
    kind: str
    name: Optional[str]
    qualname: Optional[str]
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    stable_id: str
    node_type: str
    extra_attrs: Optional[dict[str, str]] = None


def parse_source_for_query(source: str) -> tuple[str, cst.Module, dict, dict, PersistedNodeIds]:
    """Strip markers, parse module, and collect metadata maps."""
    logical, persisted = strip_persisted_node_ids(source)
    logical = strip_inline_node_id_lines_from_source(logical)
    module = cst.parse_module(logical)
    wrapper = MetadataWrapper(module)
    return (
        logical,
        module,
        wrapper.resolve(PositionProvider),
        wrapper.resolve(ParentNodeProvider),
        persisted,
    )


def build_index_from_tree(tree: CSTTree) -> list[NodeInfo]:
    """Build pre-order node index from CSTTree metadata maps."""
    out: list[NodeInfo] = []

    def _walk(node_id: str, depth: int) -> None:
        meta = tree.metadata_map.get(node_id)
        node = tree.node_map.get(node_id)
        if meta is None or node is None:
            return
        out.append(
            NodeInfo(
                node=node,
                parent=tree.node_map.get(meta.parent_id) if meta.parent_id else None,
                depth=depth,
                kind=meta.kind,
                name=meta.name,
                qualname=meta.qualname,
                start_line=meta.start_line,
                start_col=meta.start_col,
                end_line=meta.end_line,
                end_col=meta.end_col,
                stable_id=meta.stable_id,
                node_type=meta.type,
                extra_attrs=None,
            )
        )
        for child_id in meta.children_ids:
            _walk(child_id, depth + 1)

    if tree.root_node_id:
        _walk(tree.root_node_id, 0)
    return out


def build_index(source: str) -> list[NodeInfo]:
    """Compatibility source-first helper for query_source()."""
    return build_index_from_tree(create_tree_from_code(source))
