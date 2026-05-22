"""Open remote buffer: CA fetch, lock, tree build, buf write, git commit."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.registry import FormatterRegistry
from ai_editor.editor_core.writer import Writer
from ai_editor.formatters.sidecar import persist_tree_sidecar, session_sidecar_path
from ai_editor.sessions.session_dir import add_buffer_to_settings, read_session_settings
from ai_editor.sessions.session_git import commit_buffer, create_buffer_branch, get_repo


def _source_text(formatter: Any, tree: Any) -> str:
    """Full source bytes/text for buf write and upload (never skeleton)."""
    if getattr(formatter, "formatter_name", "") == "cst":
        module = getattr(tree, "module", None) or getattr(tree, "document", None)
        if module is not None and hasattr(module, "code"):
            return module.code
    exported = formatter.export(tree)
    if isinstance(exported, dict) and exported.get("content"):
        return str(exported["content"])
    return formatter.render(tree)


def _resolve_formatter(
    registry: FormatterRegistry,
    file_path: str,
    formatter: str,
    open_as_text: bool,
) -> Any:
    """Pick formatter class by name or extension."""
    if open_as_text:
        cls = registry.get_by_name("text")
    elif formatter != "auto":
        cls = registry.get_by_name(formatter)
    else:
        ext = Path(file_path).suffix.lower()
        cls = registry.get_by_extension(ext)
    if cls is None:
        raise ValueError(ErrorCode.FORMATTER_NOT_FOUND.value)
    return cls()


def open_buffer(
    session_dir: Path,
    session_key: str,
    project_id: str,
    file_path: str,
    ca_client: CodeAnalysisClient,
    formatter_registry: FormatterRegistry,
    repo: Any,
    config: dict[str, Any],
    formatter: str = "auto",
    open_as_text: bool = False,
    readonly: bool = False,
) -> dict[str, Any]:
    """Open file from CA server into session.

    AutoCreateTree: formatter.open_tree immediately after fetch (C-067).
    SourceOfTruth at open: source file until first mutation (C-066).

    Returns:
        buf_dict on success or error dict with success=False.
    """
    settings = read_session_settings(session_dir)
    ca_session_id = settings.get("ca_session_id") or config.get("ca_session_id", "")
    try:
        fmt_cls = _resolve_formatter(formatter_registry, file_path, formatter, open_as_text)
    except ValueError:
        return {
            "success": False,
            "error_code": ErrorCode.FORMATTER_NOT_FOUND,
            "message": f"no formatter for {file_path}",
        }
    formatter_inst = fmt_cls()
    try:
        content_bytes, file_id = ca_client.download_content(
            project_id,
            file_path,
            readonly=readonly,
            ca_session_id=ca_session_id,
        )
    except Exception as exc:
        return {
            "success": False,
            "error_code": ErrorCode.PATH_NOT_FOUND,
            "message": str(exc),
        }
    content = content_bytes.decode("utf-8")
    if file_id is None:
        for row in ca_client.list_project_files(project_id):
            if row.get("relative_path") == file_path:
                file_id = row.get("file_id")
                break
    buffer_id = str(uuid.uuid4())
    suffix = Path(file_path).suffix or ".txt"
    buf_path = session_dir / f"{buffer_id}{suffix}"
    tree = formatter_inst.open_tree(content)
    sidecar_path = session_sidecar_path(session_dir, buffer_id)
    persist_tree_sidecar(sidecar_path, formatter_inst.formatter_name, content, tree.root)
    Writer().write_buf(content, buf_path)
    create_buffer_branch(repo, buffer_id, buf_path)
    commit_buffer(repo, buffer_id, buf_path, f"open: {file_path}")
    buf_dict: dict[str, Any] = {
        "buffer_id": buffer_id,
        "relative_path": file_path,
        "file_type": "remote",
        "lock_mode": "none" if readonly else "full",
        "lock_session_id": None if readonly else ca_session_id,
        "file_id": file_id,
        "modified": False,
        "saved": True,
        "readonly": readonly,
        "formatter": formatter_inst.formatter_name,
        "buf_file_path": str(buf_path),
        "project_id": project_id,
        "filename": Path(file_path).name,
        "redo_stack": [],
    }
    add_buffer_to_settings(session_dir, buf_dict)
    view = formatter_inst.render_skeleton()
    return {
        "success": True,
        "buffer_id": buffer_id,
        "view": view,
        "diagnostics": [],
        "buf_dict": buf_dict,
    }
