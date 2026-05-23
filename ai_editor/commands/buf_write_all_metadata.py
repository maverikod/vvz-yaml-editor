"""Extended metadata for buf_write_all command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    dry_run_param,
    error_block,
    example_buffer_id,
    example_session_key,
    force_param,
    return_dry_run_preview,
    return_operation_result,
    session_key_param,
)


def get_buf_write_all_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_write_all."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Upload all eligible modified remote buffers in the session to the CA server. "
            "Skips readonly buffers, local-only buffers (no relative_path), and unmodified "
            "buffers unless force=true. Runs formatter validation per buffer before upload. "
            "dry_run=true returns immediately without uploading."
        ),
        parameters={
            "session_key": session_key_param(),
            "force": force_param(
                description="When true, upload all remote buffers even when modified=false.",
            ),
            "dry_run": dry_run_param(),
        },
        return_value={
            **return_operation_result(
                data_fields={
                    "success": "True when no buffer failed validation or upload.",
                    "written_buffers": "List of buffer_id values uploaded.",
                    "failed_buffers": "List of {buffer_id, error|message} for failures.",
                    "skipped_buffers": "List of buffer_id values not uploaded.",
                    "diagnostics": "Optional history/git diagnostics.",
                },
                example={
                    "success": True,
                    "written_buffers": [bid],
                    "failed_buffers": [],
                    "skipped_buffers": [],
                    "diagnostics": [],
                },
            ),
            "dry_run": return_dry_run_preview(
                note="No CA uploads or modified flag changes."
            )["success"],
        },
        usage_examples=[
            {
                "description": "Preview bulk upload",
                "command": {"session_key": sk, "dry_run": True},
                "explanation": "Returns {success: true, dry_run: true} without uploading.",
            },
            {
                "description": "Upload all modified remote buffers",
                "command": {"session_key": sk, "force": False},
                "explanation": "Validates and uploads each modified buffer with a relative_path.",
            },
        ],
        error_cases={
            "VALIDATION_FAILED": error_block(
                "VALIDATION_FAILED",
                "Validation failed for buffer",
                "Run buf_validate on failed buffers and fix diagnostics.",
                description="A buffer failed formatter validation before upload.",
            ),
            "WRITE_FAILED": error_block(
                "WRITE_FAILED",
                "Upload failed",
                "Check CA connectivity; inspect failed_buffers in the response.",
                description="CA upload raised an exception for one or more buffers.",
            ),
        },
        best_practices=[
            "Run buf_validate on critical buffers before write_all.",
            "Use dry_run=true to confirm which buffers would be uploaded.",
            "Inspect failed_buffers and skipped_buffers in the response.",
        ],
    )
