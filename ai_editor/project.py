"""Shim replacing code_analysis BaseMCPCommand for standalone use."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class BaseMCPCommand:
    """Minimal BaseMCPCommand shim for ai_editor/ported/ standalone operation.

    Replaces code_analysis.commands.base_mcp_command.BaseMCPCommand.
    Subclasses in ported/ call _resolve_project_root to get the project
    root directory and validate_params to pass params through unchanged.
    """

    name: str = ""
    version: str = "1.0"
    descr: str = ""

    # Injected at runtime by Session layer before calling ported commands.
    _project_roots: dict[str, Path] = {}

    @classmethod
    def register_project_root(cls, project_id: str, root: Path) -> None:
        """Register a project root path for a given project_id.

        Args:
            project_id: UUID4 string identifying the project.
            root: Filesystem path to the project root directory.
        """
        cls._project_roots[project_id] = root

    @classmethod
    def _resolve_project_root(cls, project_id: str) -> Path:
        """Return the registered project root for project_id.

        Args:
            project_id: UUID4 string identifying the project.

        Returns:
            Path to the project root directory.

        Raises:
            KeyError: If project_id has not been registered.
        """
        return cls._project_roots[project_id]

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass params through unchanged (no validation in shim).

        Args:
            params: Raw parameter dict from the caller.

        Returns:
            The same params dict unmodified.
        """
        return params
