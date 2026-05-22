"""Shim replacing code_analysis git_integration for standalone use.

commit_after_write is a no-op stub in G-000.
Real SessionGit integration is wired in G-005/T-002.
"""
from __future__ import annotations

from pathlib import Path


def commit_after_write(path: Path, message: str = "") -> None:
    """No-op stub for commit_after_write.

    The real implementation in G-005 commits the written file to the
    per-buffer branch in SessionGit. This stub allows ported/ write_command.py
    to function without a git repository present.

    Args:
        path: Path to the file that was written (ignored in stub).
        message: Commit message (ignored in stub).
    """
    return
