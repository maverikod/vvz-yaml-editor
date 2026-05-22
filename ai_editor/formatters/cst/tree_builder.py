"""CST tree index builder and source loaders."""
from __future__ import annotations

import uuid
from pathlib import Path

import libcst as cst
from libcst import metadata

from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.node_id_markers import (
    PersistedNodeIds,
    build_marker_path,
    strip_persisted_node_ids,
)
from ai_editor.formatters.cst.node_stable_id import (
    get_stable_id,
    strip_inline_node_id_lines_from_source,
)
from ai_editor.formatters.cst.node_type_utils import (
    _get_decorator_names,
    get_node_kind,
    get_node_name,
    get_node_qualname,
)
from ai_editor.formatters.cst.sidecar import (
    aliases_from_payload,
    load_sidecar,
    metadata_map_from_payload,
    parent_map_from_payload,
    persisted_node_ids_from_payload,
    project_cst_path,
    sidecar_matches_built_tree,
    verify_sidecar_against_source,
)
from ai_editor.formatters.cst.tree_node_metadata import TreeNodeMetadata


def _meta_pos_key(meta: TreeNodeMetadata) -> str:
    return f"{meta.start_line}:{meta.start_col}:{meta.end_line}:{meta.end_col}:{meta.type}"


def _build_tree_index(
    tree: CSTTree,
    *,
    previous_metadata_map: dict[str, TreeNodeMetadata] | None = None,
    previous_obj_to_id: dict[int, str] | None = None,
    persisted_node_ids: PersistedNodeIds | None = None,
) -> None:
    """Rebuild CSTTree indexes and metadata using deterministic stable-id rules."""
    tree.node_map.clear()
    tree.metadata_map.clear()
    tree.parent_map.clear()
    if previous_metadata_map is None:
        tree.node_id_aliases.clear()

    previous_metadata_map = previous_metadata_map or {}
    persisted_node_ids = persisted_node_ids or {}
    prev_by_pos = {_meta_pos_key(meta): node_id for node_id, meta in previous_metadata_map.items()}

    wrapper = metadata.MetadataWrapper(tree.module)
    pos_map = wrapper.resolve(metadata.PositionProvider)
    parent_node_map = wrapper.resolve(metadata.ParentNodeProvider)
    class_stack: list[str] = []
    func_stack: list[str] = []

    node_obj_to_id: dict[int, str] = {}

    def _visit(node: cst.CSTNode, path: tuple[int, ...]) -> None:
        pos = pos_map.get(node)
        if pos is None:
            for index, child in enumerate(node.children):
                _visit(child, (*path, index))
            return

        node_type = type(node).__name__
        pos_key = (
            f"{pos.start.line}:{pos.start.column}:{pos.end.line}:{pos.end.column}:{node_type}"
        )
        node_id = persisted_node_ids.get(build_marker_path(path))
        if not node_id:
            node_id = prev_by_pos.get(pos_key)
        if not node_id:
            node_id = str(uuid.uuid4())

        prev_meta = previous_metadata_map.get(node_id)
        stable_id = prev_meta.stable_id if prev_meta else (get_stable_id(node) or node_id)
        parent = parent_node_map.get(node)
        parent_id = node_obj_to_id.get(id(parent)) if parent is not None else None
        if parent_id is None and previous_obj_to_id and parent is not None:
            parent_id = previous_obj_to_id.get(id(parent))

        kind = get_node_kind(node, class_stack)
        name = get_node_name(node)
        qualname = get_node_qualname(node, class_stack, func_stack)
        decorators = _get_decorator_names(node) if isinstance(node, cst.FunctionDef) else ()

        child_nodes = [child for child in node.children if child in pos_map]
        child_ids = tuple(
            persisted_node_ids.get(build_marker_path((*path, idx)))
            or prev_by_pos.get(
                f"{pos_map[child].start.line}:{pos_map[child].start.column}:{pos_map[child].end.line}:{pos_map[child].end.column}:{type(child).__name__}"
            )
            or ""
            for idx, child in enumerate(node.children)
            if child in pos_map
        )

        tree.node_map[node_id] = node
        node_obj_to_id[id(node)] = node_id
        if parent_id:
            tree.parent_map[node_id] = parent_id
        meta = TreeNodeMetadata(
            node_id=node_id,
            stable_id=stable_id,
            type=node_type,
            kind=kind,
            name=name,
            qualname=qualname,
            decorators=decorators,
            start_line=pos.start.line,
            end_line=pos.end.line,
            start_col=pos.start.column,
            end_col=pos.end.column,
            children_count=len(child_nodes),
            children_ids=child_ids,
            parent_id=parent_id,
            docstring=prev_meta.docstring if prev_meta else None,
        )
        tree.metadata_map[node_id] = meta
        if not tree.root_node_id:
            tree.root_node_id = node_id

        if previous_obj_to_id and id(node) in previous_obj_to_id:
            old_id = previous_obj_to_id[id(node)]
            if old_id != node_id:
                tree.node_id_aliases[old_id] = node_id

        if isinstance(node, cst.ClassDef):
            class_stack.append(node.name.value)
        if isinstance(node, cst.FunctionDef):
            func_stack.append(node.name.value)
        for index, child in enumerate(node.children):
            _visit(child, (*path, index))
        if isinstance(node, cst.FunctionDef):
            func_stack.pop()
        if isinstance(node, cst.ClassDef):
            class_stack.pop()

    tree.root_node_id = ""
    _visit(tree.module, (0,))
    if not tree.metadata_map:
        fallback_id = str(uuid.uuid4())
        tree.node_map[fallback_id] = tree.module
        tree.metadata_map[fallback_id] = TreeNodeMetadata(
            node_id=fallback_id,
            stable_id=fallback_id,
            type="Module",
            kind="module",
            name=None,
            qualname=None,
            decorators=(),
            start_line=1,
            end_line=max(1, tree.module.code.count("\n") + 1),
            start_col=0,
            end_col=0,
            children_count=0,
            children_ids=(),
            parent_id=None,
            docstring=None,
        )
        tree.root_node_id = fallback_id
    if not tree.root_node_id and tree.metadata_map:
        tree.root_node_id = next(iter(tree.metadata_map))


def _read_logical_source(file_path: Path) -> tuple[str, PersistedNodeIds]:
    source = file_path.read_text(encoding="utf-8")
    logical_source, persisted = strip_persisted_node_ids(source)
    logical_source = strip_inline_node_id_lines_from_source(logical_source)
    return logical_source, persisted


def load_file_to_tree(file_path: str | Path) -> CSTTree:
    """Load Python source from file into a rebuilt CSTTree."""
    path = Path(file_path)
    logical_source, persisted_ids = _read_logical_source(path)
    module = cst.parse_module(logical_source)
    tree = CSTTree.create(module)

    payload = load_sidecar(project_cst_path(path), logical_source)
    if payload is not None:
        if not verify_sidecar_against_source(logical_source, payload):
            payload = None
    if payload is not None:
        ordered = payload.get("metadata_node_order")
        order = ordered if isinstance(ordered, list) else None
        prev_metadata = metadata_map_from_payload(payload, preferred_key_order=order)
        sidecar_persisted = persisted_node_ids_from_payload(payload)
        _build_tree_index(
            tree,
            previous_metadata_map=prev_metadata,
            persisted_node_ids=sidecar_persisted or persisted_ids,
        )
        if sidecar_matches_built_tree(tree, payload):
            tree.parent_map = parent_map_from_payload(payload)
            tree.node_id_aliases = aliases_from_payload(payload)
            return tree

    _build_tree_index(tree, persisted_node_ids=persisted_ids)
    return tree


def create_tree_from_code(source_code: str) -> CSTTree:
    """Parse source code and build a new indexed CSTTree."""
    logical_source, persisted = strip_persisted_node_ids(source_code)
    logical_source = strip_inline_node_id_lines_from_source(logical_source)
    module = cst.parse_module(logical_source)
    tree = CSTTree.create(module)
    _build_tree_index(tree, persisted_node_ids=persisted)
    return tree


def reload_tree_from_file(tree: CSTTree, file_path: str | Path) -> CSTTree:
    """Reload file content into existing CSTTree while preserving stable ids."""
    path = Path(file_path)
    logical_source, persisted_ids = _read_logical_source(path)
    previous = tree.metadata_map.copy()
    previous_obj_to_id = {id(node): node_id for node_id, node in tree.node_map.items()}
    tree.module = cst.parse_module(logical_source)
    tree.node_id_aliases.clear()
    _build_tree_index(
        tree,
        previous_metadata_map=previous,
        previous_obj_to_id=previous_obj_to_id,
        persisted_node_ids=persisted_ids,
    )
    return tree
