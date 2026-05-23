"""Generic TREE_V1 sidecar load/save for non-CST formatters."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ai_editor.formatters.tree import TreeNode
from ai_editor.writer import Writer

HEADER_RE = re.compile(
    r"^TREE_V1 fmt=(?P<fmt>[^\s]+) sha256=(?P<source>[a-f0-9]{64}) tree_sha256=(?P<tree>[a-f0-9]{64})\s*$"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def session_sidecar_path(session_dir: Path, buffer_id: str) -> Path:
    return session_dir / f"{buffer_id}.tree"


def project_sidecar_path(source_path: Path) -> Path:
    return source_path.parent / ".tree" / f"{source_path.stem}.tree"


def build_header(formatter_name: str, source_sha256: str, tree_sha256: str) -> str:
    return f"TREE_V1 fmt={formatter_name} sha256={source_sha256} tree_sha256={tree_sha256}\n"


def serialise_tree_body(node_map: dict[str, dict[str, Any]]) -> str:
    return json.dumps({"nodes": node_map}, sort_keys=True, separators=(",", ":"))


def parse_tree_body(body: str) -> dict[str, dict[str, Any]]:
    data = json.loads(body)
    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        raise ValueError("invalid sidecar body: missing nodes map")
    return nodes


def sidecar_matches_source(header_line: str, source_content: str) -> bool:
    m = HEADER_RE.match(header_line.strip())
    if not m:
        return False
    return m.group("source") == sha256_text(source_content)


def load_sidecar(path: Path, source_content: str) -> dict[str, dict[str, Any]] | None:
    """Load sidecar if present and source checksum matches; else None."""
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 2:
        return None
    if not sidecar_matches_source(lines[0], source_content):
        return None
    return parse_tree_body("\n".join(lines[1:]))


def save_sidecar(
    path: Path,
    formatter_name: str,
    source_content: str,
    node_map: dict[str, dict[str, Any]],
    writer: Writer | None = None,
) -> str:
    """Atomically write sidecar; return written file text."""
    w = writer or Writer()
    body = serialise_tree_body(node_map)
    header = build_header(formatter_name, sha256_text(source_content), sha256_text(body))
    payload = header + body
    return w.write_result(payload, path)


def _walk(node: TreeNode):
    yield node
    for ch in node.children:
        yield from _walk(ch)


def _serialise_node_entry(node: TreeNode) -> dict[str, Any]:
    return {
        "node_kind": node.node_kind,
        "start_line": node.start_line,
        "end_line": node.end_line,
        "display_text": node.display_text,
        "metadata": dict(node.metadata),
        "children": [c.stable_id for c in node.children if c.stable_id],
    }


def tree_node_map(root: TreeNode) -> dict[str, dict[str, Any]]:
    """Build stable_id -> node entry map from tree root."""
    return {
        node.stable_id: _serialise_node_entry(node)
        for node in _walk(root)
        if node.stable_id
    }


def find_root_stable_id(node_map: dict[str, dict[str, Any]]) -> str | None:
    """Return the sidecar root node stable_id."""
    referenced: set[str] = set()
    for entry in node_map.values():
        for child_id in entry.get("children", []):
            referenced.add(str(child_id))
    roots = [sid for sid in node_map if sid not in referenced]
    if len(roots) == 1:
        return roots[0]
    for sid, entry in node_map.items():
        if entry.get("node_kind") == "root":
            return sid
    return roots[0] if roots else None


def apply_sidecar_ids(
    node: TreeNode,
    stable_id: str,
    node_map: dict[str, dict[str, Any]],
    id_index: dict[str, TreeNode],
) -> None:
    """Assign stable_ids from a TREE_V1 node map onto a parsed tree."""
    entry = node_map.get(stable_id)
    if entry is None:
        raise ValueError(f"sidecar node missing: {stable_id}")
    node.stable_id = stable_id
    id_index[stable_id] = node
    child_ids = [str(child_id) for child_id in entry.get("children", [])]
    if len(child_ids) != len(node.children):
        raise ValueError(
            f"sidecar child count mismatch for {stable_id}: "
            f"{len(child_ids)} != {len(node.children)}"
        )
    for child, child_id in zip(node.children, child_ids, strict=True):
        apply_sidecar_ids(child, child_id, node_map, id_index)


def persist_tree_sidecar(
    path: Path,
    formatter_name: str,
    source_content: str,
    root: TreeNode,
    writer: Writer | None = None,
) -> str:
    """Atomically write TREE_V1 sidecar from tree root."""
    return save_sidecar(path, formatter_name, source_content, tree_node_map(root), writer)
