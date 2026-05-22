"""
Path helpers for universal file edit draft backup resolution.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

from pathlib import Path

from ai_editor.project import BaseMCPCommand


def project_root_near(path: Path) -> Path:
    """Locate project-like root upward from ``path`` for backups."""
    resolved = path.resolve()
    probe = resolved.parent if resolved.is_file() else resolved
    for candidate in (probe,) + tuple(probe.parents):
        if (candidate / "pyproject.toml").exists() or (
            candidate / "projectid"
        ).exists():
            return candidate
    registered_roots = sorted(
        (Path(root).resolve() for root in BaseMCPCommand._project_roots.values()),
        key=lambda root: len(root.parts),
        reverse=True,
    )
    for root in registered_roots:
        if resolved == root or root in resolved.parents:
            return root
    raise ValueError(f"Cannot resolve project root near {resolved}")
