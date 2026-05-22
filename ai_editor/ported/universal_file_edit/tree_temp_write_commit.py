"""
tree_temp_write_commit.py — tree-temp write and commit.

Guarded in G-000: tree_temp group deferred to G-003.
"""
from __future__ import annotations

try:
    from ai_editor.ported.universal_file_edit._tree_temp_write_commit_impl import *  # noqa: F401,F403
except ImportError:
    pass  # All symbols unavailable; callers guard via try/except
