"""
tree_temp_legacy_apply.py — legacy tree-temp apply path.

Guarded in G-000: tree_temp group deferred to G-003.
"""
from __future__ import annotations

try:
    from ai_editor.ported.universal_file_edit._tree_temp_legacy_apply_impl import *  # noqa: F401,F403
except ImportError:
    pass  # All symbols unavailable; callers guard via try/except
