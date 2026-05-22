"""Bulk save all modified remote buffers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode, WriteAllResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.save_pipeline import run_validate
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


def write_all(
    session_dir: Path,
    ca_client: CodeAnalysisClient,
    formatter_map: dict[str, tuple[Any, Any, Any]],
    force: bool = False,
) -> WriteAllResult:
    """Save eligible buffers; unlock_after_write=False (locks kept)."""
    settings = read_session_settings(session_dir)
    written: list[str] = []
    failed: list[dict[str, Any]] = []
    skipped: list[str] = []
    diagnostics: list[Diagnostic] = []
    for buf in settings.get("open_buffers", []):
        buffer_id = buf["buffer_id"]
        if buf.get("readonly"):
            skipped.append(buffer_id)
            continue
        if not force and not buf.get("modified"):
            skipped.append(buffer_id)
            continue
        if buf.get("relative_path") is None:
            skipped.append(buffer_id)
            continue
        if buffer_id not in formatter_map:
            skipped.append(buffer_id)
            continue
        formatter, document, repo = formatter_map[buffer_id]
        vr = run_validate(formatter, document)
        if not vr.success:
            failed.append(
                {"buffer_id": buffer_id, "error": ErrorCode.VALIDATION_FAILED.value}
            )
            continue
        content = _source_text(formatter, document).encode("utf-8")
        rel = buf["relative_path"]
        try:
            ca_client.upload_content(
                buf["project_id"],
                buf.get("file_id"),
                content,
                ca_session_id=settings.get("ca_session_id", ""),
                file_path=rel,
            )
        except Exception as exc:
            failed.append({"buffer_id": buffer_id, "message": str(exc)})
            continue
        buf_path = Path(buf["buf_file_path"])
        try:
            commit_buffer(
                repo, buffer_id, buf_path, f"write_all: {buf.get('filename', rel)}"
            )
        except Exception as exc:
            diagnostics.append(history_diagnostic(exc))
        update_buffer_in_settings(session_dir, buffer_id, {"modified": False})
        written.append(buffer_id)
    return WriteAllResult(
        success=len(failed) == 0,
        written_buffers=written,
        failed_buffers=failed,
        skipped_buffers=skipped,
        diagnostics=diagnostics,
    )
