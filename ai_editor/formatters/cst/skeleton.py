"""Declarative CST skeleton builders."""
from __future__ import annotations

import ast
from typing import Any

from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.tree_node_metadata import TreeNodeMetadata

BODY_PLACEHOLDER = "# ... implementation hidden ..."
VISIBLE_KINDS = frozenset(
    {
        "module",
        "import",
        "class",
        "function",
        "method",
        "property",
        "classmethod",
        "staticmethod",
        "attribute",
        "variable",
    }
)


def _source_for_meta(meta: TreeNodeMetadata, source: str) -> str:
    lines = source.splitlines()
    start = max(1, meta.start_line)
    end = max(start, meta.end_line)
    return "\n".join(lines[start - 1 : end])


def _line_label(meta: TreeNodeMetadata, code: str) -> str:
    """Return `[stable_id] start-end  representation` per C-033."""
    if meta.kind == "import":
        rep = code.strip().splitlines()[0] if code.strip() else "import"
    elif meta.kind in {"function", "method", "property", "classmethod", "staticmethod"}:
        rep = _header_only(code)
    elif meta.kind in {"class", "module"}:
        rep = _header_only(code) or meta.kind
    else:
        rep = code.strip().splitlines()[0] if code.strip() else meta.kind
    return f"[{meta.stable_id}] {meta.start_line}-{meta.end_line}  {rep}"


def _header_only(code: str) -> str:
    """First def/class line through trailing colon; skip # @node-id lines."""
    parts: list[str] = []
    for line in code.splitlines():
        stripped = line.rstrip()
        if stripped.strip().startswith("# @node-id:"):
            continue
        if not stripped and not parts:
            continue
        parts.append(stripped.strip())
        if stripped.strip().endswith(":"):
            break
    return " ".join(parts)


def _docstring_lines(code: str, indent: str) -> list[str]:
    """Render parsed docstring content as triple-quoted lines."""
    try:
        doc = ast.get_docstring(ast.parse(code))
    except SyntaxError:
        return []
    if not doc:
        return []
    return [f'{indent}"""', *[f"{indent}{line}" for line in doc.splitlines()], f'{indent}"""']


def build_declarative_overview(tree: CSTTree) -> tuple[str, list[dict[str, Any]]]:
    """Full module skeleton text and outline node dicts."""
    lines: list[str] = []
    outline: list[dict[str, Any]] = []
    root = tree.root_node_id
    if root:
        _append_overview(tree, root, 0, lines, outline)
    text = "\n".join(lines) + ("\n" if lines else "")
    return text, outline


def build_node_declarative_overview(tree: CSTTree, stable_id: str) -> tuple[str, list[dict[str, Any]]]:
    """Skeleton for one node addressed by stable_id."""
    meta = tree.find_by_stable_id(stable_id)
    if meta is None:
        return "", []
    lines: list[str] = []
    outline: list[dict[str, Any]] = []
    _append_overview(tree, meta.node_id, 0, lines, outline)
    return "\n".join(lines) + ("\n" if lines else ""), outline


def _append_overview(
    tree: CSTTree,
    node_id: str,
    depth: int,
    lines: list[str],
    outline: list[dict[str, Any]],
) -> None:
    """Recursive visible-node renderer with hidden function body placeholder."""
    meta = tree.metadata_map.get(node_id)
    if meta is None:
        return
    source = _source_for_meta(meta, tree.module.code)
    indent = "    " * depth

    if meta.kind in VISIBLE_KINDS:
        label = _line_label(meta, source)
        lines.append(f"{indent}{label}")
        for doc_line in _docstring_lines(source, indent + "    "):
            lines.append(doc_line)
        if meta.kind in {"function", "method", "property", "classmethod", "staticmethod"}:
            lines.append(f"{indent}    {BODY_PLACEHOLDER}")
        outline.append(
            {
                "stable_id": meta.stable_id,
                "kind": meta.kind,
                "name": meta.name,
                "qualname": meta.qualname,
                "start_line": meta.start_line,
                "end_line": meta.end_line,
                "depth": depth,
            }
        )

    child_ids = sorted(
        (cid for cid in meta.children_ids if cid in tree.metadata_map),
        key=lambda cid: (tree.metadata_map[cid].start_line, tree.metadata_map[cid].end_line),
    )
    for child_id in child_ids:
        _append_overview(tree, child_id, depth + 1, lines, outline)
