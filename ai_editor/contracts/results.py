"""Result envelope dataclasses for all ai_editor operations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.contracts.error_codes import ErrorCode


@dataclass
class ResultEnvelope:
    """Universal response wrapper for all editor operations.

    Attributes:
        success: True if the operation succeeded.
        error_code: Typed error code when success is False; None otherwise.
        message: Human-readable result or error description.
        details: Additional key-value fields for the caller.
        diagnostics: List of structured diagnostic messages.
    """

    success: bool
    error_code: ErrorCode | None = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of a validation operation.

    Attributes:
        success: True if validation passed.
        diagnostics: List of validation diagnostics (empty on success).
    """

    success: bool
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class OperationResult:
    """Result of a mutating operation.

    Attributes:
        success: True if the operation succeeded.
        error_code: Typed error code when success is False; None otherwise.
        message: Human-readable result or error description.
        file_id: CA database ``files.id`` when a save created or updated a remote file.
        diagnostics: List of structured diagnostic messages.
    """

    success: bool
    error_code: ErrorCode | None = None
    message: str = ""
    file_id: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class WriteAllResult:
    """Result of a bulk-save (write_all) operation.

    Attributes:
        success: True if all saves succeeded.
        written_buffers: Buffer IDs that were successfully written.
        failed_buffers: Dicts describing each failed buffer (buffer_id + error info).
        skipped_buffers: Buffer IDs skipped (unmodified or readonly).
        diagnostics: List of structured diagnostic messages.
    """

    success: bool
    written_buffers: list[str] = field(default_factory=list)
    failed_buffers: list[dict[str, Any]] = field(default_factory=list)
    skipped_buffers: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
