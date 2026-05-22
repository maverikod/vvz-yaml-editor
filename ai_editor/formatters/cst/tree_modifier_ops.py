"""CST mutation operation helpers."""
from __future__ import annotations

from typing import Any

import libcst as cst

from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.tree_node_metadata import TreeNodeMetadata, validate_docstring_dict

OperationDict = dict[str, object]


def _resolve_node_id(tree: CSTTree, node_id: str) -> str | None:
    alias = tree.node_id_aliases.get(node_id, node_id)
    if alias in tree.metadata_map:
        return alias
    meta = tree.find_by_stable_id(node_id)
    return meta.node_id if meta else None


def _meta_by_id(tree: CSTTree, node_id: str) -> TreeNodeMetadata | None:
    resolved = _resolve_node_id(tree, node_id)
    if resolved is None:
        return None
    return tree.metadata_map.get(resolved)


def sort_operations(operations: list[OperationDict], tree: CSTTree) -> list[OperationDict]:
    """Sort operation list for deterministic mutation order."""
    delete_replace: list[OperationDict] = []
    inserts: list[OperationDict] = []
    others: list[OperationDict] = []
    for op in operations:
        action = str(op.get("action", "")).lower()
        if action in {"delete", "replace", "replace_docstring"}:
            delete_replace.append(op)
        elif action == "insert":
            inserts.append(op)
        else:
            others.append(op)

    def _span_key(op: OperationDict) -> tuple[int, int]:
        node_id = str(op.get("node_id") or op.get("target_node_id") or "")
        meta = _meta_by_id(tree, node_id)
        if meta is None:
            return (0, 0)
        return (meta.start_line, meta.start_col)

    delete_replace.sort(key=_span_key, reverse=True)
    inserts.sort(key=_span_key, reverse=True)
    return [*delete_replace, *inserts, *others]


def _find_parent_for_node(tree: CSTTree, node_id: str) -> str | None:
    """Find nearest parent declaration/container for node_id."""
    current = _resolve_node_id(tree, node_id)
    while current:
        meta = tree.metadata_map.get(current)
        if meta is None:
            return None
        if meta.type in {"Module", "IndentedBlock", "ClassDef", "FunctionDef"}:
            return current
        current = meta.parent_id
    return None


def _source_lines(module: cst.Module) -> list[str]:
    return module.code.splitlines(keepends=True)


def _replace_span(module: cst.Module, start_line: int, end_line: int, replacement: str) -> cst.Module:
    lines = _source_lines(module)
    pre = "".join(lines[: start_line - 1])
    post = "".join(lines[end_line:])
    if replacement and not replacement.endswith("\n"):
        replacement += "\n"
    return cst.parse_module(pre + replacement + post)


def _insert_node(tree: CSTTree, module: cst.Module, op: OperationDict) -> cst.Module:
    """Insert code near parent target based on requested position."""
    code = str(op.get("code", ""))
    parent_id = str(op.get("parent_node_id") or "")
    parent = _meta_by_id(tree, parent_id)
    if parent is None:
        raise ValueError(f"parent_node_id not found: {parent_id!r}")
    position = str(op.get("position", "last"))
    if position == "first":
        line = parent.start_line + 1
    elif position.startswith("after:"):
        after = _meta_by_id(tree, position.split(":", 1)[1])
        line = (after.end_line + 1) if after else (parent.end_line + 1)
    else:
        line = parent.end_line + 1
    lines = _source_lines(module)
    rendered = code if code.endswith("\n") else f"{code}\n"
    merged = "".join(lines[: line - 1]) + rendered + "".join(lines[line - 1 :])
    return cst.parse_module(merged)


def _delete_node(tree: CSTTree, module: cst.Module, op: OperationDict) -> cst.Module:
    """Delete full node span addressed by node_id."""
    node_id = str(op.get("node_id") or op.get("target_node_id") or "")
    meta = _meta_by_id(tree, node_id)
    if meta is None:
        raise ValueError(f"node_id not found: {node_id!r}")
    return _replace_span(module, meta.start_line, meta.end_line, "")


def _replace_node(tree: CSTTree, module: cst.Module, op: OperationDict) -> cst.Module:
    """Replace full node span with provided code."""
    if op.get("header_only"):
        return _replace_node_header(tree, module, op)
    node_id = str(op.get("node_id") or op.get("target_node_id") or "")
    meta = _meta_by_id(tree, node_id)
    if meta is None:
        raise ValueError(f"node_id not found: {node_id!r}")
    return _replace_span(module, meta.start_line, meta.end_line, str(op.get("code", "")))


def _replace_node_header(tree: CSTTree, module: cst.Module, op: OperationDict) -> cst.Module:
    """Replace declaration header while preserving body lines."""
    node_id = str(op.get("node_id") or "")
    meta = _meta_by_id(tree, node_id)
    if meta is None:
        raise ValueError(f"node_id not found: {node_id!r}")
    lines = _source_lines(module)
    body = "".join(lines[meta.start_line: meta.end_line])
    header = str(op.get("code", "")).rstrip("\n")
    replacement = f"{header}\n{body}"
    return _replace_span(module, meta.start_line, meta.end_line, replacement)


def _replace_docstring(tree: CSTTree, module: cst.Module, op: OperationDict) -> cst.Module:
    """Replace node body or metadata docstring payload for a target node."""
    node_id = str(op.get("node_id") or "")
    meta = _meta_by_id(tree, node_id)
    if meta is None:
        raise ValueError(f"node_id not found: {node_id!r}")
    if "docstring_meta" in op:
        raw_meta = op.get("docstring_meta")
        normalized = validate_docstring_dict(raw_meta)
        tree.metadata_map[meta.node_id] = TreeNodeMetadata(
            **{**meta.__dict__, "docstring": normalized}
        )
    if "code" in op:
        return _replace_span(module, meta.start_line, meta.end_line, str(op.get("code", "")))
    return module


def _move_node(tree: CSTTree, module: cst.Module, op: OperationDict) -> cst.Module:
    """Delete node from source location and reinsert under a new target."""
    node_id = str(op.get("node_id") or "")
    meta = _meta_by_id(tree, node_id)
    if meta is None:
        raise ValueError(f"node_id not found: {node_id!r}")
    snippet = "".join(_source_lines(module)[meta.start_line - 1 : meta.end_line])
    deleted = _delete_node(tree, module, op)
    insert_op: dict[str, Any] = {
        "action": "insert",
        "parent_node_id": op.get("parent_node_id") or op.get("target_node_id"),
        "position": op.get("position", "last"),
        "code": snippet,
    }
    return _insert_node(tree, deleted, insert_op)
