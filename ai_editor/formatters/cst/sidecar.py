"""CST sidecar payload loading, verification, and persistence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.node_id_markers import PersistedNodeIds, build_marker_path
from ai_editor.formatters.cst.tree_node_metadata import TreeNodeMetadata

try:
    from ai_editor.writer import Writer  # type: ignore
except ImportError:  # pragma: no cover - compatibility with current package layout
    from ai_editor.editor_core.writer import Writer

SIDECAR_HEADER_PREFIX = "CST_TREE_V1 sha256="
SIDECAR_FORMAT_VERSION = 1


def sha256_text(text: str) -> str:
    """Compute sha256 hex digest for text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def session_cst_path(session_dir: Path, buffer_id: str) -> Path:
    """Build session-local sidecar path."""
    return session_dir / f"{buffer_id}.cst"


def project_cst_path(py_path: Path) -> Path:
    """Build project sidecar path for a Python source file."""
    return py_path.parent / ".cst" / f"{py_path.stem}.tree"


def flatten_path_to_node_id(
    metadata_map: dict[str, TreeNodeMetadata],
    root_node_id: str,
) -> dict[str, str]:
    """Flatten metadata tree to path-index -> node_id mapping."""
    out: dict[str, str] = {}
    if not root_node_id or root_node_id not in metadata_map:
        return out

    def _walk(node_id: str, path: tuple[int, ...]) -> None:
        out[build_marker_path(path)] = node_id
        children = metadata_map[node_id].children_ids
        for index, child_id in enumerate(children):
            if child_id in metadata_map:
                _walk(child_id, (*path, index))

    _walk(root_node_id, (0,))
    return out


def tree_to_sidecar_payload(tree: CSTTree) -> dict[str, Any]:
    """Build sidecar payload and checksums from a CSTTree."""
    metadata_order = list(tree.metadata_map.keys())
    metadata_blob = {node_id: meta.to_sidecar_dict() for node_id, meta in tree.metadata_map.items()}
    body: dict[str, Any] = {
        "format_version": SIDECAR_FORMAT_VERSION,
        "root_node_id": tree.root_node_id,
        "path_to_node_id": flatten_path_to_node_id(tree.metadata_map, tree.root_node_id),
        "metadata_map": metadata_blob,
        "metadata_node_order": metadata_order,
        "parent_map": dict(tree.parent_map),
        "node_id_aliases": dict(tree.node_id_aliases),
    }
    body_text = json.dumps(body, sort_keys=True, ensure_ascii=False)
    payload = dict(body)
    payload["source_sha256"] = sha256_text(tree.module.code)
    payload["tree_sha256"] = sha256_text(body_text)
    return payload


def metadata_map_from_payload(
    blob: dict[str, Any],
    preferred_key_order: list[str] | None = None,
) -> dict[str, TreeNodeMetadata]:
    """Convert sidecar metadata payload to runtime TreeNodeMetadata map."""
    raw_map = blob.get("metadata_map", {})
    if not isinstance(raw_map, dict):
        return {}
    keys = preferred_key_order or list(raw_map.keys())
    out: dict[str, TreeNodeMetadata] = {}
    for key in keys:
        raw = raw_map.get(key)
        if isinstance(raw, dict):
            out[key] = TreeNodeMetadata.from_sidecar_dict(key, raw)
    return out


def parse_sidecar_file(content: str) -> dict[str, Any] | None:
    """Parse sidecar text with header checksum line plus JSON body."""
    first_nl = content.find("\n")
    if first_nl <= 0:
        return None
    header = content[:first_nl].strip()
    body = content[first_nl + 1 :]
    if not header.startswith(SIDECAR_HEADER_PREFIX):
        return None
    parts = header.split()
    if len(parts) != 3 or not parts[2].startswith("tree_sha256="):
        return None
    source_sha = parts[1].split("=", 1)[1]
    tree_sha = parts[2].split("=", 1)[1]
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    payload["source_sha256"] = source_sha
    payload["tree_sha256"] = tree_sha
    return payload


def load_sidecar(path: Path, logical_source: str) -> dict[str, Any] | None:
    """Load and verify sidecar payload against logical source checksum."""
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    payload = parse_sidecar_file(content)
    if payload is None:
        return None
    if payload.get("source_sha256") != sha256_text(logical_source):
        return None
    body = {k: v for k, v in payload.items() if k not in {"source_sha256", "tree_sha256"}}
    body_text = json.dumps(body, sort_keys=True, ensure_ascii=False)
    if payload.get("tree_sha256") != sha256_text(body_text):
        return None
    return payload


def render_sidecar_file(payload: dict[str, Any]) -> str:
    """Render sidecar with header and deterministic JSON body."""
    body = {k: v for k, v in payload.items() if k not in {"source_sha256", "tree_sha256"}}
    body_text = json.dumps(body, sort_keys=True, ensure_ascii=False)
    source_sha = str(payload.get("source_sha256", ""))
    tree_sha = str(payload.get("tree_sha256", sha256_text(body_text)))
    header = f"{SIDECAR_HEADER_PREFIX}{source_sha} tree_sha256={tree_sha}"
    return f"{header}\n{body_text}\n"


def save_sidecar(path: Path, tree: CSTTree, writer: Writer) -> None:
    """Write sidecar payload via Writer.write_result."""
    payload = tree_to_sidecar_payload(tree)
    text = render_sidecar_file(payload)
    writer.write_result(text, path)


def sidecar_matches_built_tree(tree: CSTTree, payload: dict[str, Any]) -> bool:
    """Check whether payload path map matches current built tree map."""
    payload_map = payload.get("path_to_node_id")
    if not isinstance(payload_map, dict):
        return False
    return flatten_path_to_node_id(tree.metadata_map, tree.root_node_id) == payload_map


def verify_sidecar_against_source(logical_source: str, payload: dict[str, Any]) -> bool:
    """Validate payload source hash against logical source text."""
    return payload.get("source_sha256") == sha256_text(logical_source)


def persisted_node_ids_from_payload(payload: dict[str, Any]) -> PersistedNodeIds:
    """Extract path->node_id mapping from sidecar payload."""
    raw = payload.get("path_to_node_id", {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def parent_map_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    """Extract parent map from sidecar payload."""
    raw = payload.get("parent_map", {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def aliases_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    """Extract node-id alias map from sidecar payload."""
    raw = payload.get("node_id_aliases", {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}
