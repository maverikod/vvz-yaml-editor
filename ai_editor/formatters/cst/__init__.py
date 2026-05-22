"""CST formatter support modules (models, sidecar, stable-id utilities)."""
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
from ai_editor.formatters.cst.sidecar import (
    load_sidecar,
    project_cst_path,
    save_sidecar,
    session_cst_path,
    sidecar_matches_built_tree,
    verify_sidecar_against_source,
)
from ai_editor.formatters.cst.tree_node_metadata import TreeNodeMetadata

__all__ = [
    "CSTTree",
    "PersistedNodeIds",
    "TreeNodeMetadata",
    "build_marker_path",
    "get_stable_id",
    "load_sidecar",
    "project_cst_path",
    "save_sidecar",
    "session_cst_path",
    "sidecar_matches_built_tree",
    "strip_inline_node_id_lines_from_source",
    "strip_persisted_node_ids",
    "verify_sidecar_against_source",
]
