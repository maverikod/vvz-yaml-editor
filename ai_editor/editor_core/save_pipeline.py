"""Save pipeline - validate, render, and upload buffer content via CA client.

The formatter WritePipeline (export, diff_preview, temp_write, linters,
atomic_rename) runs inside the formatter layer (G-003). This module handles
the post-WritePipeline step: uploading the written file to the CA server.

upload_content never releases the file lock. Lock release is always a
separate explicit unlock_file call during buffer close.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_editor.contracts import Diagnostic, ErrorCode, OperationResult, ValidationResult

if TYPE_CHECKING:
    from ai_editor.editor_core.ca_client import CodeAnalysisClient


def run_validate(formatter: Any, document: Any) -> ValidationResult:
    """Run formatter linters over the current document state.

    Delegates to formatter.validate() which runs all registered linters.

    Args:
        formatter: AbstractFormatter instance owning the document tree.
        document: Current document state (formatter-specific).

    Returns:
        ValidationResult with success flag and list of Diagnostic items.
    """
    try:
        result = formatter.validate(document)
        if isinstance(result, ValidationResult):
            return result
        # Adapt older-style dict result if needed
        return ValidationResult(
            success=bool(result.get("success", True)),
            diagnostics=[
                Diagnostic(code=d.get("code", ""), message=d.get("message", ""))
                for d in result.get("diagnostics", [])
            ],
        )
    except Exception as exc:
        return ValidationResult(
            success=False,
            diagnostics=[Diagnostic(code="VALIDATION_ERROR", message=str(exc))],
        )


def run_save_pipeline(
    formatter: Any,
    document: Any,
    relative_path: str,
    ca_client: "CodeAnalysisClient",
    project_id: str,
    file_id: str | None,
    commit_message: str = "",
    *,
    ca_session_id: str = "",
) -> OperationResult:
    """Run the full save pipeline for a buffer.

    Steps:
      1. Export document via formatter WritePipeline (render, linters, atomic rename).
      2. Read the written file bytes.
      3. Upload to CA server via ca_client.upload_content (content only; no lock release).

    The file lock is NOT released here. Lock release is a separate explicit
    ca_client.unlock_file call during buffer close or save(close=True).

    Args:
        formatter: AbstractFormatter instance owning the document.
        document: Current document state.
        relative_path: Project-relative path of the file being saved.
        ca_client: CodeAnalysisClient gateway to the CA server.
        project_id: UUID of the project.
        file_id: UUID of the file on the CA server, or None for new files.
        commit_message: Commit message for the CA server (advisory).

    Returns:
        OperationResult with success flag and any diagnostics.
    """
    try:
        export_result = formatter.export(document)
        if not export_result.get("success", True):
            return OperationResult(
                success=False,
                error_code=ErrorCode.FORMAT_VALIDATION_FAILED,
                message=export_result.get("message", "Formatter export failed"),
                diagnostics=[
                    Diagnostic(code=d.get("code", ""), message=d.get("message", ""))
                    for d in export_result.get("diagnostics", [])
                ],
            )
        written_path: Path = export_result["path"]
        content = written_path.read_bytes()
        ca_client.upload_content(
            project_id,
            file_id,
            content,
            ca_session_id=ca_session_id,
            file_path=relative_path,
        )
        return OperationResult(success=True, message=f"Saved {relative_path}")
    except Exception as exc:
        return OperationResult(
            success=False,
            error_code=ErrorCode.WRITE_FAILED,
            message=str(exc),
        )


def run_save_as_pipeline(
    formatter: Any,
    document: Any,
    new_relative_path: str,
    ca_client: "CodeAnalysisClient",
    project_id: str,
    file_id: str | None,
    overwrite: bool,
    commit_message: str = "",
    *,
    ca_session_id: str = "",
) -> OperationResult:
    """Run the save-as pipeline, writing content to a new project path.

    Steps:
      1. Check if target path already exists (unless overwrite=True).
      2. Export document via formatter WritePipeline.
      3. Upload content to CA server for the new path via upload_content.
      4. The file lock on the original file is NOT released here.

    Args:
        formatter: AbstractFormatter instance owning the document.
        document: Current document state.
        new_relative_path: New project-relative destination path.
        ca_client: CodeAnalysisClient gateway to the CA server.
        project_id: UUID of the project.
        file_id: UUID of the new file on the CA server, or None if not yet created.
        overwrite: If False and the target path exists, return an error.
        commit_message: Commit message for the CA server (advisory).

    Returns:
        OperationResult with success flag and any diagnostics.
    """
    try:
        existing = ca_client.list_project_files(project_id)
        exists = any(f.get("relative_path") == new_relative_path for f in existing)
        if exists and not overwrite:
            return OperationResult(
                success=False,
                error_code=ErrorCode.SAVE_TARGET_EXISTS,
                message=f"File already exists: {new_relative_path}",
            )
        export_result = formatter.export(document)
        if not export_result.get("success", True):
            return OperationResult(
                success=False,
                error_code=ErrorCode.FORMAT_VALIDATION_FAILED,
                message=export_result.get("message", "Formatter export failed"),
            )
        written_path: Path = export_result["path"]
        content = written_path.read_bytes()
        target_file_id = file_id
        if target_file_id is None:
            for row in ca_client.list_project_files(project_id):
                if row.get("relative_path") == new_relative_path:
                    target_file_id = row.get("file_id") or row.get("id")
                    break
        if target_file_id is not None:
            ca_client.upload_content(
                project_id,
                target_file_id,
                content,
                ca_session_id=ca_session_id,
                file_path=new_relative_path,
            )
            return OperationResult(success=True, message=f"Saved as {new_relative_path}")
        ca_client.upload_content(
            project_id,
            None,
            content,
            ca_session_id=ca_session_id,
            file_path=new_relative_path,
        )
        return OperationResult(success=True, message=f"Saved as {new_relative_path}")
    except Exception as exc:
        return OperationResult(
            success=False,
            error_code=ErrorCode.WRITE_FAILED,
            message=str(exc),
        )
