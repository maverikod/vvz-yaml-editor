"""Extended metadata for file_open command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    error_block,
    example_buffer_id,
    example_project_id,
    example_session_key,
    file_path_param,
    formatter_param,
    project_id_param,
    return_operation_result,
    session_key_param,
)


def get_file_open_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for file_open."""
    sk = example_session_key()
    pid = example_project_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Download a project file from the CA server into a new session buffer, "
            "build the formatter document tree, write the local .buf file, and acquire "
            "a file lock unless readonly=true. Re-opening the same project file while "
            "it is already open returns BUFFER_ALREADY_OPEN. Returns buffer_id and a skeleton view."
        ),
        parameters={
            "session_key": session_key_param(),
            "project_id": project_id_param(required=True),
            "file_path": file_path_param(required=True),
            "formatter": formatter_param(),
            "open_as_text": {
                "type": "boolean",
                "description": "Treat content as plain text without formatter parsing.",
                "required": False,
                "default": False,
                "examples": [False],
            },
            "readonly": {
                "type": "boolean",
                "description": "Open without CA lock; buffer mutations fail with BUFFER_READONLY.",
                "required": False,
                "default": False,
                "examples": [False],
            },
        },
        return_value=return_operation_result(
            data_fields={
                "success": "True when the buffer was opened.",
                "buffer_id": "New buffer identifier for subsequent commands.",
                "view": "Formatter skeleton preview of the document.",
                "formatter": "Resolved formatter name.",
                "relative_path": "Project-relative path that was opened.",
            },
            example={
                "success": True,
                "buffer_id": example_buffer_id(),
                "formatter": "cst",
                "relative_path": "src/main.py",
                "view": "Module(...)",
            },
        ),
        usage_examples=[
            {
                "description": "Open a Python module for editing",
                "command": {
                    "session_key": sk,
                    "project_id": pid,
                    "file_path": "src/main.py",
                    "formatter": "auto",
                    "readonly": False,
                },
                "explanation": "Downloads the file, locks it on CA, and returns buffer_id.",
            },
        ],
        error_cases={
            "FORMATTER_NOT_FOUND": error_block(
                "FORMATTER_NOT_FOUND",
                "Formatter not found: {formatter}",
                "Use formatter=auto or a registered name (yaml, json, cst, text, …).",
                description="Requested formatter is not registered.",
            ),
            "PATH_NOT_FOUND": error_block(
                "PATH_NOT_FOUND",
                "Path not found: {file_path}",
                "Verify project_id and file_path via CA list_files.",
                description="CA server has no file at the given project-relative path.",
            ),
            "BUFFER_ALREADY_OPEN": error_block(
                "BUFFER_ALREADY_OPEN",
                "file already open: {file_path} (buffer_id={buffer_id})",
                "Use the existing buffer_id or file_close it before opening again.",
                description="The same project file is already open in this session.",
            ),
        },
        best_practices=[
            "Call session_connect first and pass the returned session_key.",
            "Use readonly=true only for inspection; editing requires a lock.",
            "Verify buffer_id via session_status after open.",
        ],
    )
