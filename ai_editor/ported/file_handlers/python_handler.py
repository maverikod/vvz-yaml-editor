"""
python_handler.py - Python file handler using libcst.

Guarded in G-000: CST stack (cst_tree.*) not ported.
Real PythonFileHandler implementation wired in G-003/T-008.
Importing this module succeeds; PythonFileHandler is a stub that raises
NotImplementedError on all methods.
"""
from __future__ import annotations

from typing import Any

try:
    from ai_editor.ported.file_handlers._python_handler_impl import PythonFileHandler  # noqa: F401
except ImportError:
    class PythonFileHandler:  # type: ignore[no-redef]
        """Stub PythonFileHandler - CST not available in G-000."""

        def __getattr__(self, name: str) -> Any:
            raise NotImplementedError(
                f"PythonFileHandler.{name}: CST stack not available in G-000. "
                "Wired in G-003/T-008."
            )

__all__ = ["PythonFileHandler"]
