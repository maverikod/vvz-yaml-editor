"""CST mutation orchestration helpers."""
from __future__ import annotations

from typing import Any

import libcst as cst

from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.node_id_markers import strip_persisted_node_ids
from ai_editor.formatters.cst.node_stable_id import strip_inline_node_id_lines_from_source
from ai_editor.formatters.cst.tree_builder import _build_tree_index
from ai_editor.formatters.cst.tree_modifier_ops import (
    _delete_node,
    _insert_node,
    _move_node,
    _replace_docstring,
    _replace_node,
    _replace_node_header,
    sort_operations,
)


def _apply_libcst_codegen_compat() -> None:
    """Patch SimpleStatementLine._codegen_impl to ignore extra kwargs."""
    original = getattr(cst.SimpleStatementLine, "_codegen_impl", None)
    if original is None or getattr(original, "_ai_editor_compat", False):
        return

    def _wrapped(self: cst.SimpleStatementLine, state: Any, **kwargs: Any) -> None:
        return original(self, state)

    setattr(_wrapped, "_ai_editor_compat", True)
    cst.SimpleStatementLine._codegen_impl = _wrapped  # type: ignore[assignment]


def _choose_path(operations: list[dict], tree: CSTTree) -> str:
    """Choose mutation strategy path based on operation profile."""
    del tree  # reserved for future fine-grained choices
    replace_or_insert = sum(1 for op in operations if op.get("action") in {"replace", "insert"})
    has_delete = any(op.get("action") == "delete" for op in operations)
    has_complex = any(op.get("action") in {"move", "replace_range"} for op in operations)
    if has_complex or (replace_or_insert > 1) or has_delete:
        return "batch"
    return "sequential"


def _apply_one(tree: CSTTree, module: cst.Module, op: dict[str, object]) -> cst.Module:
    action = str(op.get("action", "")).lower()
    if action == "insert":
        return _insert_node(tree, module, op)
    if action == "delete":
        return _delete_node(tree, module, op)
    if action == "replace":
        if bool(op.get("docstring_only")):
            return _replace_docstring(tree, module, op)
        if bool(op.get("header_only")):
            return _replace_node_header(tree, module, op)
        return _replace_node(tree, module, op)
    if action == "move":
        return _move_node(tree, module, op)
    raise ValueError(f"Unsupported action: {action!r}")


def _rebuild_after_apply(
    tree: CSTTree,
    previous: dict[str, Any],
    persisted_node_ids: dict[str, str] | None = None,
) -> None:
    previous_metadata = previous.get("metadata_map")
    previous_obj_map = previous.get("obj_to_id")
    _build_tree_index(
        tree,
        previous_metadata_map=previous_metadata,
        previous_obj_to_id=previous_obj_map,
        persisted_node_ids=persisted_node_ids,
    )


def _apply_sequential(tree: CSTTree, operations: list[dict]) -> CSTTree:
    """Apply operations with rebuild between each step."""
    for op in operations:
        previous = {
            "metadata_map": tree.metadata_map.copy(),
            "obj_to_id": {id(node): node_id for node_id, node in tree.node_map.items()},
        }
        tree.module = _apply_one(tree, tree.module, op)
        _rebuild_after_apply(tree, previous)
    return tree


def _apply_batch(tree: CSTTree, operations: list[dict]) -> CSTTree:
    """Apply operations in one source pass and rebuild once."""
    previous = {
        "metadata_map": tree.metadata_map.copy(),
        "obj_to_id": {id(node): node_id for node_id, node in tree.node_map.items()},
    }
    module = tree.module
    for op in operations:
        module = _apply_one(tree, module, op)
    tree.module = module
    _rebuild_after_apply(tree, previous)
    return tree


def modify_tree(tree: CSTTree, operations: list[dict]) -> CSTTree:
    """Apply validated operation batch to CSTTree and return the same tree."""
    for op in operations:
        if "action" not in op:
            raise ValueError("operation must include 'action'")
    sorted_ops = sort_operations(operations, tree)
    path = _choose_path(sorted_ops, tree)
    updated = _apply_batch(tree, sorted_ops) if path == "batch" else _apply_sequential(tree, sorted_ops)
    compile(updated.module.code, "<cst>", "exec")
    return updated


def rollback_tree_to_code(tree: CSTTree, source: str) -> CSTTree:
    """Rollback tree to source text while preserving stable-id metadata when possible."""
    logical, persisted = strip_persisted_node_ids(source)
    logical = strip_inline_node_id_lines_from_source(logical)
    previous = tree.metadata_map.copy()
    obj_map = {id(node): node_id for node_id, node in tree.node_map.items()}
    tree.module = cst.parse_module(logical)
    _rebuild_after_apply(
        tree,
        {"metadata_map": previous, "obj_to_id": obj_map},
        persisted_node_ids=persisted,
    )
    return tree


_apply_libcst_codegen_compat()
