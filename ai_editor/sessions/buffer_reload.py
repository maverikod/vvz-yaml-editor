"""Reload remote buffer from CA server."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.registry import FormatterRegistry
from ai_editor.editor_core.writer import Writer
from ai_editor.formatters.sidecar import save_sidecar, session_sidecar_path
from ai_editor.sessions.session_dir import read_session_settings, update_buffer_in_settings
from ai_editor.sessions.session_git import commit_buffer, history_diagnostic


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


def reload_buffer(
    session_dir: Path,
    session_key: str,
    buffer_id: str,
    ca_client: CodeAnalysisClient,
    formatter_registry: FormatterRegistry,
    repo: Any,
) -> dict[str, Any]:
    """Re-download remote buffer; rebuild tree+sidecar; modified=False."""
    diagnostics: list[Diagnostic] = []
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return {
            "success": False,
            "error_code": ErrorCode.BUFFER_NOT_FOUND,
            "message": buffer_id,
        }
    if buf.get("file_type") != "remote":
        return {
            "success": False,
            "error_code": ErrorCode.BUFFER_INVALID,
            "message": "local buffer cannot reload",
        }
    rel = buf["relative_path"]
    project_id = buf["project_id"]
    try:
        content_bytes, _fid = ca_client.download_content(
            project_id, rel, readonly=True
        )
    except Exception as exc:
        return {
            "success": False,
            "error_code": ErrorCode.PATH_NOT_FOUND,
            "message": str(exc),
        }
    content = content_bytes.decode("utf-8")
    cls = formatter_registry.get_by_name(buf["formatter"])
    if cls is None:
        return {
            "success": False,
            "error_code": ErrorCode.FORMATTER_NOT_FOUND,
            "message": buf["formatter"],
        }
    formatter = cls()
    try:
        tree = formatter.open_tree(content)
    except Exception as exc:
        return {
            "success": False,
            "error_code": ErrorCode.FORMAT_INVALID_ON_OPEN,
            "message": str(exc),
        }
    buf_path = Path(buf["buf_file_path"])
    Writer().write_buf(content, buf_path)
    save_sidecar(
        session_sidecar_path(session_dir, buffer_id),
        formatter.formatter_name,
        content,
        tree,
    )
    try:
        commit_buffer(repo, buffer_id, buf_path, f"reload: {rel}")
    except Exception as exc:
        diagnostics.append(history_diagnostic(exc))
    update_buffer_in_settings(
        session_dir, buffer_id, {"modified": False, "redo_stack": []}
    )
    return {
        "success": True,
        "view": formatter.render_skeleton(),
        "diagnostics": diagnostics,
    }
