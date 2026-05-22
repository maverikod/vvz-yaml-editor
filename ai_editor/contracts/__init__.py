"""Public contracts package for ai_editor.

Exports all typed contracts used across the editor: error codes, diagnostics,
result envelopes, and session/buffer descriptors.
"""
from __future__ import annotations

from ai_editor.contracts.descriptors import (
    BufferAddress,
    BufferDescriptor,
    SessionDescriptor,
    SessionKey,
)
from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.contracts.error_codes import ErrorCode
from ai_editor.contracts.results import (
    OperationResult,
    ResultEnvelope,
    ValidationResult,
    WriteAllResult,
)

__all__ = [
    "BufferAddress",
    "BufferDescriptor",
    "Diagnostic",
    "ErrorCode",
    "OperationResult",
    "ResultEnvelope",
    "SessionDescriptor",
    "SessionKey",
    "ValidationResult",
    "WriteAllResult",
]
