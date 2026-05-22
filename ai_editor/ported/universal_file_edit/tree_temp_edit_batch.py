"""
tree_temp_edit_batch.py — tree-temp batch mutation.

Guarded in G-000: yaml_tree/json_tree stack not ported. Wired in G-003.
"""
from __future__ import annotations

try:
    from ai_editor.ported.universal_file_edit._tree_temp_edit_batch_impl import (  # noqa: F401
        apply_tree_temp_mutations,
    )
except ImportError:
    def apply_tree_temp_mutations(*args, **kwargs):  # type: ignore[misc]
        raise NotImplementedError("tree_temp_edit_batch not available in G-000; wired in G-003")

__all__ = ["apply_tree_temp_mutations"]
