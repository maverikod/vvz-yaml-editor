"""Diagnostic dataclass for structured validation and error messages."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Diagnostic:
    """Structured diagnostic message from validation or error handling.

    Attributes:
        code: Stable error code string identifying the diagnostic type.
        message: Human-readable description of the diagnostic.
        path: Optional dot-separated or slash-separated location within
            the document where the diagnostic applies. None if not applicable.
        details: Additional key-value diagnostic fields. Empty dict by default.
    """

    code: str
    message: str
    path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
