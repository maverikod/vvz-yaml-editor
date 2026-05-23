"""Extended metadata for buf_save_as command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    dry_run_param,
    error_block,
    example_buffer_id,
    example_session_key,
    file_path_param,
    force_param,
    return_dry_run_preview,
    return_operation_result,
    session_key_param,
)


def get_buf_save_as_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_save_as."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Save buffer content to a new project-relative path on the CA server. "
            "Binds a local-only buffer to a remote file or copies an existing buffer "
            "to a new path. overwrite=false rejects existing targets. dry_run=true "
            "returns immediately without CA upload or session settings change."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
            "new_relative_path": file_path_param(
                required=True,
            ),
            "overwrite": force_param(
                description="When true, replace an existing file at new_relative_path.",
            ),
            "dry_run": dry_run_param(),
        },
        return_value={
            **return_operation_result(
                data_fields={
                    "success": "True when save-as completed.",
                    "buffer_id": "Buffer identifier (same as input).",
                    "relative_path": "Project-relative path written on CA.",
                },
                example={
                    "success": True,
                    "buffer_id": bid,
                    "relative_path": "config/new_app.yaml",
                },
            ),
            "dry_run": return_dry_run_preview(
                note="No CA upload or session settings change."
            )["success"],
        },
        usage_examples=[
            {
                "description": "Preview save-as to new path",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "new_relative_path": "config/new_app.yaml",
                    "dry_run": True,
                },
                "explanation": "Returns {success: true, dry_run: true} without uploading.",
            },
            {
                "description": "Persist local buffer to CA",
                "command": {
                    "session_key": sk,
                    "buffer_id": bid,
                    "new_relative_path": "config/new_app.yaml",
                    "overwrite": False,
                },
                "explanation": "Uploads content and sets relative_path on the buffer.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Verify buffer_id via session_status.",
                description="buffer_id is not open in the session.",
            ),
            "SAVE_TARGET_EXISTS": error_block(
                "SAVE_TARGET_EXISTS",
                "Save target already exists",
                "Set overwrite=true or choose a different new_relative_path.",
                description="Target path exists and overwrite=false.",
            ),
            "FORMAT_VALIDATION_FAILED": error_block(
                "FORMAT_VALIDATION_FAILED",
                "Format validation failed",
                "Run buf_validate, fix diagnostics, then retry.",
                description="Formatter linters rejected the document before upload.",
            ),
            "WRITE_FAILED": error_block(
                "WRITE_FAILED",
                "Write failed",
                "Check CA connectivity and file permissions.",
                description="CA upload failed.",
            ),
        },
        best_practices=[
            "Use dry_run=true before first save-as to a production path.",
            "Run buf_validate before save-as on complex edits.",
            "Use overwrite=true only when replacing an existing file intentionally.",
        ],
    )
