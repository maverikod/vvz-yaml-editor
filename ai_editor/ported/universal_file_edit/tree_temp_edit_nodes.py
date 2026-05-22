"""
tree_temp_edit_nodes.py — tree-temp node-level editing.

Guarded in G-000: depends on json_pointer + tree_node; deferred to G-003.
"""
from __future__ import annotations

try:
    from ai_editor.ported.universal_file_edit._tree_temp_edit_nodes_impl import *  # noqa: F401,F403
except ImportError:
    pass  # All symbols unavailable; callers guard against None
