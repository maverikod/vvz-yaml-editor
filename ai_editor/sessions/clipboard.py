"""Session clipboard copy/cut/paste."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
from ai_editor.editor_core.writer import Writer
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


CLIPBOARD_NAME = "clipboard.json"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    finally:
        pass
    os.replace(tmp, path)


def _read_clipboard(session_dir: Path) -> dict[str, Any] | None:
    path = session_dir / CLIPBOARD_NAME
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def copy_to_clipboard(
    session_dir: Path,
    buffer_id: str,
    source_address: Any,
    formatter: Any,
    document: Any,
    repo: Any,
) -> None:
    """Copy fragment to clipboard.json; no buf write or git commit."""
    fragment = formatter.copy_fragment(document, source_address)
    body = formatter.to_string(fragment)
    branch = repo.heads[f"buf/{buffer_id}"]
    source_revision = branch.commit.hexsha
    data = {
        "formatter": formatter.formatter_name,
        "body": body,
        "source_revision": source_revision,
        "paste_policy": "snapshot",
    }
    _atomic_write_json(session_dir / CLIPBOARD_NAME, data)


def cut_to_clipboard(
    session_dir: Path,
    buffer_id: str,
    source_address: Any,
    formatter: Any,
    document: Any,
    repo: Any,
) -> tuple[Any, Any]:
    """Cut: clipboard then write_buf then settings then commit."""
    new_document, fragment, _changed = formatter.cut_fragment(document, source_address)
    body = formatter.to_string(fragment)
    branch = repo.heads[f"buf/{buffer_id}"]
    source_revision = branch.commit.hexsha
    _atomic_write_json(
        session_dir / CLIPBOARD_NAME,
        {
            "formatter": formatter.formatter_name,
            "body": body,
            "source_revision": source_revision,
            "paste_policy": "snapshot",
        },
    )
    settings = read_session_settings(session_dir)
    buf = next(
        b for b in settings["open_buffers"] if b["buffer_id"] == buffer_id
    )
    buf_path = Path(buf["buf_file_path"])
    Writer().write_buf(_source_text(formatter, new_document), buf_path)
    update_buffer_in_settings(
        session_dir, buffer_id, {"modified": True, "redo_stack": []}
    )
    try:
        commit_buffer(
            repo, buffer_id, buf_path, f"clipboard: cut {source_address}"
        )
    except Exception as exc:
        pass
    return new_document, fragment


def paste_from_clipboard(
    session_dir: Path,
    buffer_id: str,
    target_address: Any,
    mode: str,
    formatter: Any,
    document: Any,
    repo: Any,
) -> tuple[Any, list[Diagnostic]]:
    """Paste clipboard body at target; write_buf + commit."""
    diagnostics: list[Diagnostic] = []
    clip = _read_clipboard(session_dir)
    if not clip:
        raise ValueError(ErrorCode.CLIPBOARD_EMPTY.value)
    src_fmt = clip["formatter"]
    tgt_fmt = formatter.formatter_name
    if src_fmt != tgt_fmt:
        from ai_editor.formatters.conversion.registry import conversion_registry
        if not conversion_registry.can_convert(src_fmt, tgt_fmt):
            raise ValueError(ErrorCode.CLIPBOARD_FORMAT_MISMATCH.value)
        try:
            raw_fragment = clip["body"]
            converted = conversion_registry.convert(raw_fragment, src_fmt, tgt_fmt, None, formatter)
            clip = dict(clip)
            clip["body"] = converted if isinstance(converted, str) else str(converted)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(ErrorCode.CLIPBOARD_FORMAT_MISMATCH.value) from exc
    if clip.get("paste_policy") == "reject_if_source_revision_changed":
        head = repo.heads[f"buf/{buffer_id}"].commit.hexsha
        if head != clip.get("source_revision"):
            raise ValueError(ErrorCode.CLIPBOARD_SOURCE_STALE.value)
    fragment = formatter.from_string(clip["body"])
    new_document, _changed = formatter.paste_fragment(
        document, target_address, mode, fragment
    )
    settings = read_session_settings(session_dir)
    buf = next(
        b for b in settings["open_buffers"] if b["buffer_id"] == buffer_id
    )
    buf_path = Path(buf["buf_file_path"])
    Writer().write_buf(_source_text(formatter, new_document), buf_path)
    update_buffer_in_settings(
        session_dir, buffer_id, {"modified": True, "redo_stack": []}
    )
    try:
        commit_buffer(
            repo,
            buffer_id,
            buf_path,
            f"clipboard: paste {mode} {target_address}",
        )
    except Exception as exc:
        diagnostics.append(history_diagnostic(exc))
    return new_document, diagnostics
