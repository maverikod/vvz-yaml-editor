"""Mandatory write_buf + sidecar + git commit after every mutation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
from ai_editor.editor_core.writer import Writer
from ai_editor.formatters.sidecar import persist_tree_sidecar, session_sidecar_path
from ai_editor.sessions.session_dir import (
    read_session_settings,
    resolve_buffer_file_path,
    update_buffer_in_settings,
)
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
    *,
    source_before: str | None = None,
) -> dict[str, Any]:
    """Apply mutation: write buf, session sidecar, ses_settings, git commit."""
    if readonly_session:
        return {
            "success": False,
            "error_code": ErrorCode.BUFFER_READONLY,
            "message": "readonly",
        }
    old_source = source_before if source_before is not None else _source_text(formatter, document)
    new_source = _source_text(formatter, new_document)
    if old_source == new_source:
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
    buf_path = resolve_buffer_file_path(session_dir, buf_meta)
    source = _source_text(formatter, new_document)
    Writer().write_buf(source, buf_path)
    sidecar = session_sidecar_path(session_dir, buffer_id)
    if hasattr(new_document, "root"):
        persist_tree_sidecar(sidecar, formatter.formatter_name, source, new_document.root)
    else:
        from ai_editor.formatters.cst.sidecar import save_sidecar as save_cst_sidecar

        save_cst_sidecar(session_dir / f"{buffer_id}.cst", new_document)
    update_buffer_in_settings(
        session_dir,
        buffer_id,
        {
            "modified": True,
            "redo_stack": [],
            **(
                {"saved": False}
                if buf_meta.get("file_type") == "remote"
                else {}
            ),
        },
    )
    diagnostics: list[Diagnostic] = []
    try:
        commit_buffer(
            repo,
            buffer_id,
            buf_path,
            f"{command_name}: {params_summary}",
            session_dir=session_dir,
        )
    except Exception as exc:
        diagnostics.append(history_diagnostic(exc))
    return {"success": True, "diagnostics": diagnostics}
