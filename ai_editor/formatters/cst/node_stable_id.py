"""Transient # @node-id comment helpers for libcst re-parse."""
from __future__ import annotations

import re
from typing import Optional

import libcst as cst

_STABLE_ID_RE = re.compile(r"#\s*@node-id:\s*([0-9a-f-]{36})")
_INLINE_NODE_ID_LINE_RE = re.compile(r"^\s*#\s*@node-id:\s*[0-9a-fA-F-]{36}\s*$")
_SUPPORTED = (cst.FunctionDef, cst.ClassDef)


def strip_inline_node_id_lines_from_source(source: str) -> str:
    """Remove standalone `# @node-id: <uuid>` lines; preserve trailing newline."""
    lines = source.splitlines()
    kept = [line for line in lines if not _INLINE_NODE_ID_LINE_RE.match(line)]
    out = "\n".join(kept)
    if source.endswith("\n"):
        out += "\n"
    return out


def get_stable_id(node: cst.CSTNode) -> Optional[str]:
    """Extract UUID from leading_lines comment on FunctionDef/ClassDef; else None."""
    if not isinstance(node, _SUPPORTED):
        return None
    for empty_line in node.leading_lines:
        if empty_line.comment is not None:
            match = _STABLE_ID_RE.match(empty_line.comment.value)
            if match:
                return match.group(1)
    return None
