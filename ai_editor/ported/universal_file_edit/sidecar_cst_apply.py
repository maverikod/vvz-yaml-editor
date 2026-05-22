"""
sidecar_cst_apply.py — CST sidecar editing.

Guarded in G-000: CST stack is not ported. Real implementation wired in G-003/T-008.
Importing this module succeeds but all public names are None stubs.
"""
from __future__ import annotations

try:
    from ai_editor.ported.universal_file_edit._sidecar_cst_apply_impl import (  # noqa: F401
        run_sidecar_cst_edit_batch,
        validate_sidecar_nested_batch,
    )
except ImportError:
    run_sidecar_cst_edit_batch = None  # type: ignore[assignment]
    validate_sidecar_nested_batch = None  # type: ignore[assignment]

__all__ = ["run_sidecar_cst_edit_batch", "validate_sidecar_nested_batch"]
