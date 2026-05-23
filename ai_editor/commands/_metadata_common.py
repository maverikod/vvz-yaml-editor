"""Shared helpers for ai_editor MCP command metadata() dictionaries."""
from __future__ import annotations

from typing import Any, Type

_EXAMPLE_SESSION = "550e8400-e29b-41d4-a716-446655440000"
_EXAMPLE_PROJECT = "84ec55c8-cefd-480d-beb6-fa1d35e60362"
_EXAMPLE_BUFFER = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def example_session_key() -> str:
    return _EXAMPLE_SESSION


def example_project_id() -> str:
    return _EXAMPLE_PROJECT


def example_buffer_id() -> str:
    return _EXAMPLE_BUFFER


def session_key_param(*, required: bool = True) -> dict[str, Any]:
    return {
        "type": "string",
        "description": "UUID4 session identifier returned by session_connect.",
        "required": required,
        "examples": [_EXAMPLE_SESSION],
        "notes": (
            "Commands validate that the local session directory exists and that its "
            "ca_session_id is still registered on the CA server before execution."
        ),
    }


def buffer_id_param(*, required: bool = True) -> dict[str, Any]:
    return {
        "type": "string",
        "description": "Open buffer identifier from file_open, file_create, or buf_new.",
        "required": required,
        "examples": [_EXAMPLE_BUFFER],
    }


def project_id_param(*, required: bool = False) -> dict[str, Any]:
    return {
        "type": "string",
        "description": "Project UUID. Use list_projects on the CA server to discover valid values.",
        "required": required,
        "examples": [_EXAMPLE_PROJECT],
    }


def file_path_param(*, required: bool = False) -> dict[str, Any]:
    return {
        "type": "string",
        "description": "Literal project-relative file path. Wildcards are not allowed.",
        "required": required,
        "examples": ["src/main.py"],
    }


def dry_run_param(*, required: bool = False) -> dict[str, Any]:
    return {
        "type": "boolean",
        "description": (
            "When true, preview the operation without modifying session state, "
            "local buffer files, or remote files."
        ),
        "required": required,
        "default": False,
        "examples": [True],
    }


def formatter_param(*, required: bool = False) -> dict[str, Any]:
    return {
        "type": "string",
        "description": (
            "Formatter name or auto to detect by file extension "
            "(yaml, json, cst, markdown, xml, html, text)."
        ),
        "required": required,
        "default": "auto",
        "enum": ["auto", "text", "yaml", "json", "cst", "markdown", "xml", "html"],
        "examples": ["yaml"],
    }


def force_param(*, description: str, required: bool = False) -> dict[str, Any]:
    return {
        "type": "boolean",
        "description": description,
        "required": required,
        "default": False,
        "examples": [False],
    }


def metadata_header(cls: Type[Any]) -> dict[str, Any]:
    return {
        "name": cls.name,
        "version": cls.version,
        "description": cls.descr,
        "category": cls.category,
        "author": cls.author,
        "email": cls.email,
    }


def error_block(code: str, message: str, solution: str, *, description: str) -> dict[str, Any]:
    return {
        "description": description,
        "message": message,
        "solution": solution,
    }


def return_session_descriptor() -> dict[str, Any]:
    return {
        "success": {
            "description": "Session descriptor with session_key and open buffer list.",
            "data": {
                "session_key": "UUID4 session identifier.",
                "open_buffers": "List of BufferDescriptor records (buffer_id, relative_path, formatter, modified, readonly, …).",
                "diagnostics": "Optional Diagnostic list from status collection.",
            },
            "example": {
                "session_key": _EXAMPLE_SESSION,
                "open_buffers": [
                    {
                        "buffer_id": _EXAMPLE_BUFFER,
                        "session_key": _EXAMPLE_SESSION,
                        "filename": "main.py",
                        "relative_path": "src/main.py",
                        "formatter": "cst",
                        "project_id": _EXAMPLE_PROJECT,
                        "modified": False,
                        "readonly": False,
                        "buf_file_path": "/tmp/sessions/.../buffers/7c9e....buf",
                    }
                ],
                "diagnostics": [],
            },
        },
        "error": {
            "description": "Command failed before returning a session descriptor.",
            "code": "ErrorCode string when applicable.",
            "message": "Human-readable failure reason.",
            "details": "Additional fields from OperationResult when present.",
        },
    }


def return_buffer_state() -> dict[str, Any]:
    return {
        "success": {
            "description": "Buffer state snapshot for an open buffer.",
            "data": {
                "buffer_id": "Buffer identifier.",
                "formatter": "Formatter name.",
                "preview": "Skeleton render of the document tree.",
                "modified": "True when local edits are not yet sent to CA.",
                "readonly": "True when opened without a file lock.",
                "file_path": "Project-relative path when bound to a remote file.",
                "relative_path": "Same as file_path when present.",
            },
            "example": {
                "buffer_id": _EXAMPLE_BUFFER,
                "formatter": "yaml",
                "preview": "root: {...}",
                "modified": True,
                "readonly": False,
                "file_path": "config/app.yaml",
                "relative_path": "config/app.yaml",
            },
        },
        "error": {
            "description": "Buffer not found returns success=False in data without always raising.",
            "code": "May be absent; check data.success.",
            "message": "Human-readable note when buffer_id is unknown.",
        },
    }


def return_operation_result(*, data_fields: dict[str, str], example: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": {
            "description": "Operation completed successfully.",
            "data": data_fields,
            "example": example,
        },
        "error": {
            "description": "Operation failed.",
            "code": "ErrorCode enum value as string.",
            "message": "Human-readable failure reason.",
            "details": "Optional diagnostics list.",
        },
    }


def return_validation_result() -> dict[str, Any]:
    return {
        "success": {
            "description": "Validation finished; success=False when linters report issues.",
            "data": {
                "success": "True when no diagnostics.",
                "diagnostics": "List of Diagnostic objects (severity, message, location).",
            },
            "example": {"success": True, "diagnostics": []},
        },
        "error": {
            "description": "Validation could not run (missing buffer/file).",
            "code": "VALIDATION_FAILED or FORMAT_VALIDATION_FAILED when applicable.",
            "message": "Human-readable failure reason.",
        },
    }


def return_dry_run_preview(*, note: str) -> dict[str, Any]:
    return {
        "success": {
            "description": "Dry-run preview; no state was modified.",
            "data": {
                "success": "Always true for dry_run.",
                "dry_run": "Always true.",
                "note": note,
            },
            "example": {"success": True, "dry_run": True},
        },
        "error": {
            "description": "Invalid parameters detected before preview.",
            "code": "Validation error code when applicable.",
            "message": "Human-readable failure reason.",
        },
    }


def build_metadata(
    cls: Type[Any],
    *,
    detailed_description: str,
    parameters: dict[str, Any],
    return_value: dict[str, Any],
    usage_examples: list[dict[str, Any]],
    error_cases: dict[str, dict[str, str]],
    best_practices: list[str],
) -> dict[str, Any]:
    """Assemble a metadata() dictionary conforming to docs/metadatastd.md."""
    return {
        **metadata_header(cls),
        "detailed_description": detailed_description,
        "parameters": parameters,
        "return_value": return_value,
        "usage_examples": usage_examples,
        "error_cases": error_cases,
        "best_practices": best_practices,
    }
