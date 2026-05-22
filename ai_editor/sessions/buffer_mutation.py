"""Mandatory write_buf + sidecar + git commit after every mutation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
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


def execute_mutation(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    document: Any,
    new_document: Any,
    command_name: str,
    params_summary: str,
    repo: Any,
    readonly_session: bool = False,
    readonly_buffer: bool = False,
) -> dict[str, Any]:
    """Apply mutation: write buf, session sidecar, ses_settings, git commit."""
    if readonly_session or readonly_buffer:
        return {
            "success": False,
            "error_code": ErrorCode.BUFFER_READONLY,
            "message": "readonly",
        }
    if document is new_document:
        return {"success": True, "message": "unchanged", "diagnostics": []}
    settings = read_session_settings(session_dir)
    buf_meta = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf_meta:
        return {
            "success": False,
            "error_code": ErrorCode.BUFFER_NOT_FOUND,
            "message": buffer_id,
        }
    buf_path = Path(buf_meta["buf_file_path"])
    source = _source_text(formatter, new_document)
    Writer().write_buf(source, buf_path)
    sidecar = session_sidecar_path(session_dir, buffer_id)
    save_sidecar(sidecar, formatter.formatter_name, source, new_document)
    update_buffer_in_settings(
        session_dir,
        buffer_id,
        {"modified": True, "redo_stack": []},
    )
    diagnostics: list[Diagnostic] = []
    try:
        commit_buffer(
            repo,
            buffer_id,
            buf_path,
            f"{command_name}: {params_summary}",
        )
    except Exception as exc:
        diagnostics.append(history_diagnostic(exc))
    return {"success": True, "diagnostics": diagnostics}
