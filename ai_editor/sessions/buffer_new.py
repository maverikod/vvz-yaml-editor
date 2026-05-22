"""Create unsaved local buffer from initial content."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
from ai_editor.editor_core.registry import FormatterRegistry
from ai_editor.editor_core.writer import Writer
from ai_editor.formatters.sidecar import save_sidecar, session_sidecar_path
from ai_editor.sessions.session_dir import add_buffer_to_settings
from ai_editor.sessions.session_git import commit_buffer, create_buffer_branch, history_diagnostic


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


def create_new_buffer(
    session_dir: Path,
    session_key: str,
    formatter_name: str,
    initial_content: str,
    display_name: str,
    formatter_registry: FormatterRegistry,
    repo: Any,
) -> dict[str, Any]:
    """Create local unsaved buffer; modified=True from start."""
    diagnostics: list[Diagnostic] = []
    cls = formatter_registry.get_by_name(formatter_name)
    if cls is None:
        return {
            "success": False,
            "error_code": ErrorCode.FORMATTER_NOT_FOUND,
            "message": formatter_name,
        }
    formatter = cls()
    try:
        tree = formatter.open_tree(initial_content)
    except Exception as exc:
        return {
            "success": False,
            "error_code": ErrorCode.FORMAT_INVALID_ON_OPEN,
            "message": str(exc),
        }
    buffer_id = str(uuid.uuid4())
    buf_path = session_dir / f"{buffer_id}.txt"
    source = _source_text(formatter, tree)
    save_sidecar(
        session_sidecar_path(session_dir, buffer_id),
        formatter.formatter_name,
        source,
        tree,
    )
    Writer().write_buf(source, buf_path)
    create_buffer_branch(repo, buffer_id, buf_path)
    try:
        commit_buffer(repo, buffer_id, buf_path, f"new: {display_name or 'untitled'}")
    except Exception as exc:
        diagnostics.append(history_diagnostic(exc))
    buf_dict = {
        "buffer_id": buffer_id,
        "relative_path": None,
        "file_type": "local",
        "lock_mode": "none",
        "lock_session_id": None,
        "file_id": None,
        "modified": True,
        "saved": False,
        "readonly": False,
        "formatter": formatter.formatter_name,
        "buf_file_path": str(buf_path),
        "project_id": "",
        "filename": display_name or "untitled",
        "redo_stack": [],
    }
    add_buffer_to_settings(session_dir, buf_dict)
    return {
        "buffer_id": buffer_id,
        "view": formatter.render_skeleton(),
        "diagnostics": diagnostics,
    }
