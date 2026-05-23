"""Project-relative path normalization for session buffers."""
from __future__ import annotations

from pathlib import Path


def normalize_project_relative_path(path: str) -> str:
    """Normalize and validate a project-relative file path."""
    norm = str(path or "").strip().replace("\\", "/")
    if not norm:
        raise ValueError("project-relative path is required")
    rel = Path(norm)
    if rel.is_absolute():
        raise ValueError(
            "Absolute file_path is not allowed; use a project-relative path."
        )
    if ".." in rel.parts:
        raise ValueError("Path traversal (..) is not allowed in file_path.")
    return rel.as_posix()
