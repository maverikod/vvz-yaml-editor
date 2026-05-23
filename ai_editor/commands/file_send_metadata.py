"""Extended metadata for file_send command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    dry_run_param,
    error_block,
    example_buffer_id,
    example_session_key,
    return_dry_run_preview,
    return_operation_result,
    session_key_param,
)


def get_file_send_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for file_send."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Validate and upload the in-memory buffer document to the CA server (save). "
            "For a local-only buffer (no relative_path), pass project_id and file_path "
            "to bind and upload in one step. For an already bound buffer, only "
            "session_key and buffer_id are required. dry_run=true validates without "
            "The CA file lock is kept after upload by default (release_lock=false). "
            "Set release_lock=true to release the advisory lock on CA after a successful upload."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "project_id": {
                "type": "string",
                "description": (
                    "Project UUID. Required with file_path when the buffer has no "
                    "relative_path yet (first upload after file_create)."
                ),
                "required": False,
                "examples": ["84ec55c8-cefd-480d-beb6-fa1d35e60362"],
            },
            "file_path": {
                "type": "string",
                "description": (
                    "Project-relative destination path. Required with project_id for "
                    "first upload of a local-only buffer."
                ),
                "required": False,
                "examples": ["tmp/new_file.txt"],
            },
            "dry_run": dry_run_param(),
            "release_lock": {
                "type": "boolean",
                "description": (
                    "Release advisory lock after successful upload. "
                    "Default false keeps lock; true releases lock on CA."
                ),
                "required": False,
                "default": False,
            },
        },
        return_value={
            **return_operation_result(
                data_fields={
                    "success": "True when upload completed.",
                    "buffer_id": "Saved buffer identifier.",
                    "relative_path": "Project-relative path written on CA.",
                },
                example={"success": True, "buffer_id": bid, "relative_path": "src/main.py"},
            ),
            "dry_run": return_dry_run_preview(
                note="Validation runs; no CA upload or modified flag change."
            )["success"],
        },
        usage_examples=[
            {
                "description": "Preview save validation",
                "command": {"session_key": sk, "buffer_id": bid, "dry_run": True},
                "explanation": "Returns {success: true, dry_run: true} if validation would pass.",
            },
            {
                "description": "First upload of a local-only buffer",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362",
                    "file_path": "tmp/new_file.txt",
                },
                "explanation": "Binds relative_path and uploads content to CA.",
            },
            {
                "description": "Re-upload modified buffer to CA",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Uploads content and sets modified=false on success.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Verify buffer_id via session_status.",
                description="buffer_id is not open in the session.",
            ),
            "BUFFER_INVALID": error_block(
                "BUFFER_INVALID",
                "unsaved local buffer",
                "Pass project_id and file_path together for first upload, or buf_save_as.",
                description="Buffer has no relative_path and file_path was not provided.",
            ),
            "FORMAT_VALIDATION_FAILED": error_block(
                "FORMAT_VALIDATION_FAILED",
                "Format validation failed",
                "Run buf_validate, fix diagnostics, then retry file_send.",
                description="Formatter linters rejected the document before upload.",
            ),
            "WRITE_FAILED": error_block(
                "WRITE_FAILED",
                "Write failed",
                "Check CA connectivity and file permissions.",
                description="CA upload or local buf write failed.",
            ),
        },
        best_practices=[
            "Run buf_validate before file_send on complex edits.",
            "Use dry_run=true to catch validation errors cheaply.",
            "Verify success with file_get (modified should be false).",
        ],
    )
