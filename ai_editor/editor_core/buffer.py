"""AbstractBuffer ABC and BufferState snapshot contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ai_editor.contracts import (
    BufferAddress,
    OperationResult,
    ValidationResult,
    WriteAllResult,
)


@dataclass
class BufferState:
    """Point-in-time snapshot of a buffer's current state.

    Returned by AbstractBuffer.get_state(). Contains a formatter-rendered
    skeleton preview of the current document.

    Attributes:
        buffer_id: Stable UUID4 string for this buffer.
        formatter: Formatter name (e.g. 'yaml', 'text', 'cst').
        preview: Formatter-rendered skeleton or key listing of the document.
        modified: True if the buffer has unsaved mutations.
        readonly: True if the buffer was opened read-only.
        file_path: Project-relative path, or None for unsaved buffers.
        relative_path: Same as file_path; kept for API symmetry.
    """

    buffer_id: str
    formatter: str
    preview: str
    modified: bool
    readonly: bool
    file_path: str | None = None
    relative_path: str | None = None


class AbstractBuffer(ABC):
    """Abstract interface for all buffer implementations.

    Defines the full public contract that the session layer (G-005) implements.
    Formatters and editor core use this interface; no concrete buffer logic
    lives here.

    Invariant: formatter and buffer_id are immutable after open.
    """

    @abstractmethod
    def open(
        self,
        session_key: str,
        project_id: str,
        file_path: str,
        formatter: str = "auto",
        open_as_text: bool = False,
        readonly: bool = False,
    ) -> str:
        """Open a project file and return the buffer_id.

        Args:
            session_key: UUID4 of the owning session.
            project_id: UUID4 of the project.
            file_path: Project-relative path to the file.
            formatter: Formatter name or 'auto' for automatic selection.
            open_as_text: If True, force text formatter regardless of extension.
            readonly: If True, open without acquiring a file lock.

        Returns:
            buffer_id UUID4 string for subsequent operations.
        """

    @abstractmethod
    def new(
        self,
        session_key: str,
        formatter_name: str,
        initial_content: str,
        display_name: str | None = None,
    ) -> str:
        """Create a new unsaved buffer and return its buffer_id.

        Args:
            session_key: UUID4 of the owning session.
            formatter_name: Formatter to use for the new buffer.
            initial_content: Initial document content.
            display_name: Optional display name for the unsaved buffer.

        Returns:
            buffer_id UUID4 string.
        """

    @abstractmethod
    def save(
        self,
        session_key: str,
        buffer_id: str,
        close: bool = False,
    ) -> OperationResult:
        """Save the buffer to its project file.

        Args:
            session_key: UUID4 of the owning session.
            buffer_id: Buffer to save.
            close: If True, close the buffer after saving.

        Returns:
            OperationResult with success flag and any diagnostics.
        """

    @abstractmethod
    def save_as(
        self,
        session_key: str,
        buffer_id: str,
        relative_path: str,
        overwrite: bool = False,
        close: bool = False,
    ) -> OperationResult:
        """Save the buffer to a new project-relative path.

        Args:
            session_key: UUID4 of the owning session.
            buffer_id: Buffer to save.
            relative_path: New project-relative destination path.
            overwrite: If True, overwrite an existing file at that path.
            close: If True, close the buffer after saving.

        Returns:
            OperationResult with success flag and any diagnostics.
        """

    @abstractmethod
    def close(
        self,
        session_key: str,
        buffer_id: str,
        force: bool = False,
    ) -> OperationResult:
        """Close the buffer, releasing any file lock.

        Args:
            session_key: UUID4 of the owning session.
            buffer_id: Buffer to close.
            force: If True, close even if the buffer has unsaved changes.

        Returns:
            OperationResult with success flag.
        """

    @abstractmethod
    def reload(
        self,
        session_key: str,
        buffer_id: str,
    ) -> OperationResult:
        """Reload the buffer content from the project file, discarding mutations.

        Args:
            session_key: UUID4 of the owning session.
            buffer_id: Buffer to reload.

        Returns:
            OperationResult with success flag.
        """

    @abstractmethod
    def get_state(
        self,
        session_key: str,
        buffer_id: str,
    ) -> BufferState:
        """Return a point-in-time snapshot of the buffer state.

        Args:
            session_key: UUID4 of the owning session.
            buffer_id: Buffer to inspect.

        Returns:
            BufferState snapshot including formatter-rendered preview.
        """

    @abstractmethod
    def get_formatter(
        self,
        session_key: str,
        buffer_id: str,
    ) -> Any:
        """Return the formatter instance for this buffer.

        Args:
            session_key: UUID4 of the owning session.
            buffer_id: Buffer to inspect.

        Returns:
            The formatter instance (concrete type depends on implementation).
        """

    @abstractmethod
    def validate(
        self,
        session_key: str,
        buffer_id: str,
    ) -> ValidationResult:
        """Validate the current buffer content using the formatter's linters.

        Args:
            session_key: UUID4 of the owning session.
            buffer_id: Buffer to validate.

        Returns:
            ValidationResult with success flag and any diagnostic messages.
        """

    @abstractmethod
    def write_all(
        self,
        session_key: str,
        force: bool = False,
    ) -> WriteAllResult:
        """Save all modified buffers in the session.

        Args:
            session_key: UUID4 of the owning session.
            force: If True, save even buffers with validation errors.

        Returns:
            WriteAllResult listing written, failed, and skipped buffer IDs.
        """
