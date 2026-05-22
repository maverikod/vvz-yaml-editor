"""Session and buffer descriptor contracts for ai_editor public API."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_editor.contracts.diagnostic import Diagnostic

# SessionKey is a UUID4 string. Defined as a type alias for documentation.
# Invariant: never reused after session close.
SessionKey = str


@dataclass
class BufferDescriptor:
    """Point-in-time snapshot of buffer metadata.

    Returned as part of SessionDescriptor. This is the public API contract,
    NOT the internal buf_meta stored in ses_settings.json.

    Attributes:
        buffer_id: Stable UUID4 string for the buffer lifetime.
        session_key: UUID4 string of the owning session.
        filename: Base filename without directory.
        relative_path: Project-relative path, or None for unsaved buffers.
        formatter: Formatter name (e.g. 'yaml', 'text', 'cst').
        project_id: UUID4 of the project this buffer belongs to.
        modified: True if the buffer has unsaved mutations.
        readonly: True if the buffer was opened read-only.
        buf_file_path: Absolute path to the local session buffer file.
    """

    buffer_id: str
    session_key: str
    filename: str
    relative_path: str | None
    formatter: str
    project_id: str
    modified: bool
    readonly: bool
    buf_file_path: str


@dataclass
class SessionDescriptor:
    """Point-in-time snapshot of session state.

    Returned by connect and session_status operations.

    Attributes:
        session_key: UUID4 string identifying the session.
        open_buffers: Descriptors of all currently open buffers.
        diagnostics: Any diagnostics produced during status collection.
    """

    session_key: SessionKey
    open_buffers: list[BufferDescriptor] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class BufferAddress:
    """Opaque address within a buffer for navigation and mutation.

    The address field is formatter-specific and must never be interpreted
    by editor core. Only the owning formatter may read or produce addresses.

    Attributes:
        buffer_id: Buffer this address belongs to.
        address: Formatter-specific address (stable_id UUID, XPath, CSS selector, etc.).
    """

    buffer_id: str
    address: Any
