"""Embedded target Python for G-005 atomic step prompts. Imported by _gen_g005_as.py."""
from __future__ import annotations

import textwrap

SESSIONS_INIT_MINIMAL = textwrap.dedent('''
"""Session layer — buffer lifecycle, clipboard, recovery, public API."""
''').strip()

SESSION_DIR_PY = textwrap.dedent('''
"""Session directory layout and ses_settings.json management."""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SETTINGS_NAME = "ses_settings.json"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically via tempfile + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        os.close(fd)
        raise
    os.replace(tmp, path)


def create_session_dir(
    base_dir: str | Path,
    session_key: str | None,
    readonly: bool = False,
) -> Path:
    """Create session directory and initial ses_settings.json.

    Args:
        base_dir: Parent directory for all sessions.
        session_key: Existing key or None to allocate UUID4.
        readonly: Session-level readonly flag.

    Returns:
        Path to the new session directory.
    """
    base = Path(base_dir)
    key = session_key or str(uuid.uuid4())
    session_dir = base / key
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "git").mkdir(exist_ok=True)
    settings: dict[str, Any] = {
        "session_key": key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "readonly": readonly,
        "open_buffers": [],
    }
    _atomic_write_json(session_dir / SETTINGS_NAME, settings)
    return session_dir


def read_session_settings(session_dir: Path) -> dict[str, Any]:
    """Load ses_settings.json from session_dir."""
    path = session_dir / SETTINGS_NAME
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_session_settings(session_dir: Path, settings: dict[str, Any]) -> None:
    """Persist ses_settings.json atomically."""
    _atomic_write_json(session_dir / SETTINGS_NAME, settings)


def _find_buffer_index(buffers: list[dict[str, Any]], buffer_id: str) -> int:
    for i, buf in enumerate(buffers):
        if buf.get("buffer_id") == buffer_id:
            return i
    return -1


def add_buffer_to_settings(session_dir: Path, buf_dict: dict[str, Any]) -> None:
    """Append or replace open_buffers entry by buffer_id."""
    settings = read_session_settings(session_dir)
    buffers = settings.setdefault("open_buffers", [])
    idx = _find_buffer_index(buffers, buf_dict["buffer_id"])
    if idx >= 0:
        buffers[idx] = buf_dict
    else:
        buffers.append(buf_dict)
    write_session_settings(session_dir, settings)


def remove_buffer_from_settings(session_dir: Path, buffer_id: str) -> None:
    """Remove buffer from open_buffers."""
    settings = read_session_settings(session_dir)
    buffers = settings.get("open_buffers", [])
    settings["open_buffers"] = [b for b in buffers if b.get("buffer_id") != buffer_id]
    write_session_settings(session_dir, settings)


def update_buffer_in_settings(
    session_dir: Path,
    buffer_id: str,
    updates: dict[str, Any],
) -> None:
    """Merge updates into one open_buffers entry."""
    settings = read_session_settings(session_dir)
    buffers = settings.get("open_buffers", [])
    idx = _find_buffer_index(buffers, buffer_id)
    if idx < 0:
        raise KeyError(f"buffer not found: {buffer_id}")
    buffers[idx] = {**buffers[idx], **updates}
    write_session_settings(session_dir, settings)
''').strip()

SESSION_GIT_PY = textwrap.dedent('''
"""Session-scoped git repository for per-buffer undo history."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import git
from git import Repo

from ai_editor.contracts import Diagnostic, ErrorCode

logger = logging.getLogger(__name__)


def init_session_git(session_dir: Path) -> Repo:
    """Initialize non-bare git repo under session_dir/git with empty initial commit."""
    git_dir = session_dir / "git"
    git_dir.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(git_dir, bare=False)
    if not repo.head.is_valid():
        repo.index.commit("session: init", allow_empty=True)
    return repo


def get_repo(session_dir: Path) -> Repo:
    """Return existing session git repository."""
    return Repo(session_dir / "git")


def _branch_name(buffer_id: str) -> str:
    return f"buf/{buffer_id}"


def branch_name(buffer_id: str) -> str:
    """Public alias for buffer branch naming."""
    return _branch_name(buffer_id)


def create_buffer_branch(repo: Repo, buffer_id: str, buf_file_path: Path) -> None:
    """Create branch buf/<buffer_id> tracking buf file (no commit yet)."""
    name = _branch_name(buffer_id)
    if name in [h.name for h in repo.heads]:
        repo.git.checkout(name)
        return
    repo.git.checkout("-b", name)


def commit_buffer(
    repo: Repo,
    buffer_id: str,
    buf_file_path: Path,
    message: str,
) -> None:
    """Stage buf file and commit on buf/<buffer_id>; fault-tolerant."""
    try:
        name = _branch_name(buffer_id)
        repo.git.checkout(name)
        repo.index.add([str(buf_file_path)])
        commit = repo.index.commit(message)
        repo.heads[name].set_commit(commit)
    except Exception as exc:
        logger.warning("git commit failed: %s", exc)


def delete_buffer_branch(repo: Repo, buffer_id: str) -> None:
    """Delete buf/<buffer_id> branch if present."""
    name = _branch_name(buffer_id)
    if name not in [h.name for h in repo.heads]:
        return
    repo.git.checkout("master")
    repo.git.branch("-D", name)


def history_diagnostic(exc: Exception) -> Diagnostic:
    """Build HISTORY_UNAVAILABLE diagnostic (code string, not ErrorCode enum)."""
    return Diagnostic(code="HISTORY_UNAVAILABLE", message=str(exc))
''').strip()

HELPER_SOURCE_BYTES = textwrap.dedent('''
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
''').strip()

BUFFER_OPEN_PY = (
    textwrap.dedent('''
"""Open remote buffer: CA fetch, lock, tree build, buf write, git commit."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.registry import FormatterRegistry
from ai_editor.editor_core.writer import Writer
from ai_editor.formatters.sidecar import save_sidecar, session_sidecar_path
from ai_editor.sessions.session_dir import add_buffer_to_settings, read_session_settings
from ai_editor.sessions.session_git import commit_buffer, create_buffer_branch, get_repo

''')
    + HELPER_SOURCE_BYTES
    + textwrap.dedent('''


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
            project_id, file_path, readonly=readonly
        )
    except Exception as exc:
        return {
            "success": False,
            "error_code": ErrorCode.PATH_NOT_FOUND,
            "message": str(exc),
        }
    content = content_bytes.decode("utf-8")
    if not readonly and file_id:
        try:
            ca_client.lock_file(ca_session_id, project_id, file_id)
        except Exception:
            return {
                "success": False,
                "error_code": ErrorCode.BUFFER_LOCKED,
                "message": "file lock held by another session",
            }
    buffer_id = str(uuid.uuid4())
    suffix = Path(file_path).suffix or ".txt"
    buf_path = session_dir / f"{buffer_id}{suffix}"
    tree = formatter_inst.open_tree(content)
    sidecar_path = session_sidecar_path(session_dir, buffer_id)
    save_sidecar(sidecar_path, formatter_inst.formatter_name, content, tree)
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
''')
).strip()

BUFFER_NEW_PY = (
    textwrap.dedent('''
"""Create unsaved local buffer from initial content."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
from ai_editor.editor_core.registry import FormatterRegistry
from ai_editor.editor_core.writer import Writer
from ai_editor.sessions.session_dir import add_buffer_to_settings
from ai_editor.sessions.session_git import commit_buffer, create_buffer_branch, history_diagnostic

''')
    + HELPER_SOURCE_BYTES
    + textwrap.dedent('''


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
        tree = formatter.parse(initial_content)
    except Exception as exc:
        return {
            "success": False,
            "error_code": ErrorCode.FORMAT_INVALID_ON_OPEN,
            "message": str(exc),
        }
    buffer_id = str(uuid.uuid4())
    buf_path = session_dir / f"{buffer_id}.txt"
    source = _source_text(formatter, tree)
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
''')
).strip()

BUFFER_MUTATION_PY = (
    textwrap.dedent('''
"""Mandatory write_buf + sidecar + git commit after every mutation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode
from ai_editor.editor_core.writer import Writer
from ai_editor.formatters.sidecar import save_sidecar, session_sidecar_path
from ai_editor.sessions.session_dir import read_session_settings, update_buffer_in_settings
from ai_editor.sessions.session_git import commit_buffer, history_diagnostic

''')
    + HELPER_SOURCE_BYTES
    + textwrap.dedent('''


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
''')
).strip()

BUFFER_SAVE_PY = textwrap.dedent('''
"""Explicit save via save pipeline and CA upload."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import ErrorCode, OperationResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.save_pipeline import run_save_as_pipeline, run_save_pipeline
from ai_editor.sessions.session_dir import read_session_settings, remove_buffer_from_settings, update_buffer_in_settings
from ai_editor.sessions.session_git import commit_buffer, delete_buffer_branch


def save_buffer(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    document: Any,
    ca_client: CodeAnalysisClient,
    repo: Any,
    *,
    close: bool = False,
) -> OperationResult:
    """Save buffer to CA; optional unlock+close when close=True."""
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_NOT_FOUND,
            message=buffer_id,
        )
    rel = buf.get("relative_path")
    if not rel:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_INVALID,
            message="unsaved local buffer",
        )
    result = run_save_pipeline(
        formatter,
        document,
        rel,
        ca_client,
        buf["project_id"],
        buf.get("file_id"),
        commit_message=f"ai_editor: save {rel}",
    )
    if not result.success:
        return result
    update_buffer_in_settings(
        session_dir, buffer_id, {"modified": False, "saved": True}
    )
    if close and buf.get("lock_session_id") and buf.get("file_id"):
        ca_client.unlock_file(
            buf["lock_session_id"], buf["project_id"], buf["file_id"]
        )
        delete_buffer_branch(repo, buffer_id)
        remove_buffer_from_settings(session_dir, buffer_id)
    return result


def save_as_buffer(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    document: Any,
    ca_client: CodeAnalysisClient,
    new_relative_path: str,
    overwrite: bool = False,
    repo: Any | None = None,
) -> OperationResult:
    """Save buffer content to a new project path."""
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_NOT_FOUND,
            message=buffer_id,
        )
    result = run_save_as_pipeline(
        formatter,
        document,
        new_relative_path,
        ca_client,
        buf["project_id"],
        overwrite,
    )
    if result.success:
        update_buffer_in_settings(
            session_dir,
            buffer_id,
            {
                "relative_path": new_relative_path,
                "modified": False,
                "saved": True,
                "file_type": "remote",
            },
        )
    return result
''').strip()

BUFFER_RELOAD_PY = (
    textwrap.dedent('''
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

''')
    + HELPER_SOURCE_BYTES
    + textwrap.dedent('''


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
''')
).strip()

BUFFER_CLOSE_PY = textwrap.dedent('''
"""Close single buffer or entire session."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from ai_editor.contracts import ErrorCode, OperationResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.session_dir import read_session_settings, remove_buffer_from_settings
from ai_editor.sessions.session_git import delete_buffer_branch

logger = logging.getLogger(__name__)


def _release_locks(ca_client: CodeAnalysisClient, buffers: list[dict[str, Any]]) -> None:
    """Best-effort unlock_file for session close."""
    for buf in buffers:
        lock_id = buf.get("lock_session_id")
        file_id = buf.get("file_id")
        project_id = buf.get("project_id")
        if not lock_id or not file_id or not project_id:
            continue
        try:
            ca_client.unlock_file(lock_id, project_id, file_id)
        except Exception as exc:
            logger.warning("unlock failed: %s", exc)


def _cleanup_buffer_files(session_dir: Path, buf_meta: dict[str, Any]) -> None:
    """Remove buf file and generic/cst sidecar artifacts."""
    buf_path = Path(buf_meta["buf_file_path"])
    if buf_path.exists():
        buf_path.unlink()
    buffer_id = buf_meta["buffer_id"]
    for pattern in (f"{buffer_id}.tree", f"{buffer_id}.cst"):
        side = session_dir / pattern
        if side.exists():
            side.unlink()


def close_buffer(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    ca_client: CodeAnalysisClient,
    repo: Any,
    force: bool = False,
) -> OperationResult:
    """Close one buffer; unlock advisory lock when required."""
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_NOT_FOUND,
            message=buffer_id,
        )
    if (
        buf.get("file_type") == "remote"
        and not buf.get("saved")
        and buf.get("modified")
        and not force
        and not buf.get("readonly")
    ):
        return OperationResult(
            success=False,
            error_code=ErrorCode.FILE_HAS_UNSENT_CHANGES,
            message="unsent changes",
        )
    _cleanup_buffer_files(session_dir, buf)
    delete_buffer_branch(repo, buffer_id)
    if (
        buf.get("lock_session_id")
        and buf.get("file_id")
        and not buf.get("saved")
    ):
        try:
            ca_client.unlock_file(
                buf["lock_session_id"], buf["project_id"], buf["file_id"]
            )
        except Exception as exc:
            logger.warning("unlock failed: %s", exc)
    remove_buffer_from_settings(session_dir, buffer_id)
    return OperationResult(success=True, message="closed")


def close_session(
    session_dir: str | Path,
    session_key: str,
    ca_client: CodeAnalysisClient,
    force: bool = False,
) -> OperationResult:
    """Close session directory after checks and lock release."""
    path = Path(session_dir)
    settings = read_session_settings(path)
    if not force:
        for buf in settings.get("open_buffers", []):
            if buf.get("readonly"):
                continue
            if buf.get("modified"):
                return OperationResult(
                    success=False,
                    error_code=ErrorCode.SESSION_HAS_UNSAVED_BUFFERS,
                    message="modified buffers remain",
                )
            if buf.get("file_type") == "remote" and not buf.get("saved"):
                return OperationResult(
                    success=False,
                    error_code=ErrorCode.SESSION_HAS_UNSENT_FILES,
                    message="unsent remote files",
                )
    _release_locks(ca_client, settings.get("open_buffers", []))
    shutil.rmtree(path, ignore_errors=True)
    return OperationResult(success=True, message="session closed")
''').strip()

UNDO_REDO_PY = (
    textwrap.dedent('''
"""Undo/redo via session git and persisted redo_stack."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import git
from git import Commit

from ai_editor.contracts import Diagnostic, ErrorCode, OperationResult
from ai_editor.editor_core.writer import Writer
from ai_editor.sessions.session_dir import read_session_settings, update_buffer_in_settings
from ai_editor.sessions.session_git import branch_name, history_diagnostic

''')
    + HELPER_SOURCE_BYTES
    + textwrap.dedent('''


def _resolve_commit(repo: Any, sha: str) -> Commit | None:
    try:
        return repo.commit(sha)
    except (git.exc.BadName, git.exc.GitError, ValueError):
        return None


def _branch(repo: Any, buffer_id: str) -> Any:
    return repo.heads[branch_name(buffer_id)]


def undo(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    repo: Any,
    steps: int = 1,
) -> OperationResult:
    """Undo steps on buffer branch; push prior SHA to redo_stack."""
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_NOT_FOUND,
            message=buffer_id,
        )
    branch = _branch(repo, buffer_id)
    target = branch.commit
    for _ in range(steps):
        if not target.parents:
            return OperationResult(
                success=False,
                error_code=ErrorCode.UNDO_AT_BEGINNING,
                message="at first commit",
            )
        target = target.parents[0]
    prior_hexsha = branch.commit.hexsha
    buf_path = Path(buf["buf_file_path"])
    content = target.tree[str(buf_path.name)].data_stream.read().decode("utf-8")
    Writer().write_buf(content, buf_path)
    branch.set_commit(target)
    redo = list(buf.get("redo_stack", []))
    redo.append(prior_hexsha)
    update_buffer_in_settings(session_dir, buffer_id, {"redo_stack": redo})
    return OperationResult(success=True, message="undo")


def redo(
    session_dir: Path,
    buffer_id: str,
    formatter: Any,
    repo: Any,
    steps: int = 1,
) -> OperationResult:
    """Redo from redo_stack LIFO."""
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return OperationResult(
            success=False,
            error_code=ErrorCode.BUFFER_NOT_FOUND,
            message=buffer_id,
        )
    redo_stack = list(buf.get("redo_stack", []))
    if not redo_stack:
        return OperationResult(
            success=False,
            error_code=ErrorCode.REDO_AT_END,
            message="redo stack empty",
        )
    diagnostics: list[Diagnostic] = []
    branch = _branch(repo, buffer_id)
    for _ in range(steps):
        if not redo_stack:
            return OperationResult(
                success=False,
                error_code=ErrorCode.REDO_AT_END,
                message="redo stack empty",
            )
        sha = redo_stack.pop()
        commit = _resolve_commit(repo, sha)
        if commit is None:
            update_buffer_in_settings(session_dir, buffer_id, {"redo_stack": []})
            return OperationResult(
                success=False,
                error_code=None,
                message="redo commit lost",
                diagnostics=[
                    Diagnostic(
                        code="HISTORY_UNAVAILABLE",
                        message="commit no longer resolvable",
                    )
                ],
            )
        buf_path = Path(buf["buf_file_path"])
        content = commit.tree[str(buf_path.name)].data_stream.read().decode("utf-8")
        Writer().write_buf(content, buf_path)
        branch.set_commit(commit)
    update_buffer_in_settings(session_dir, buffer_id, {"redo_stack": redo_stack})
    return OperationResult(success=True, message="redo", diagnostics=diagnostics)


def buf_history(
    session_dir: Path,
    buffer_id: str,
    repo: Any,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent commits on buffer branch."""
    branch = _branch(repo, buffer_id)
    out: list[dict[str, Any]] = []
    for commit in repo.iter_commits(branch, max_count=limit):
        out.append(
            {
                "sha": commit.hexsha,
                "message": commit.message.strip(),
                "authored_date": commit.authored_datetime.isoformat(),
            }
        )
    return out


def buf_checkout(
    session_dir: Path,
    buffer_id: str,
    sha: str,
    formatter: Any,
    repo: Any,
) -> OperationResult:
    """Checkout arbitrary reachable commit; redo_stack unchanged."""
    commit = _resolve_commit(repo, sha)
    if commit is None:
        return OperationResult(
            success=False,
            message="unknown commit",
            diagnostics=[
                Diagnostic(code="HISTORY_UNAVAILABLE", message="sha not found")
            ],
        )
    branch = _branch(repo, buffer_id)
    reachable = {c.hexsha for c in repo.iter_commits(branch, max_count=200)}
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return OperationResult(
            success=False, error_code=ErrorCode.BUFFER_NOT_FOUND, message=buffer_id
        )
    for rsha in buf.get("redo_stack", []):
        reachable.add(rsha)
    if sha not in reachable:
        return OperationResult(
            success=False,
            message="commit not reachable",
            diagnostics=[
                Diagnostic(code="HISTORY_UNAVAILABLE", message="not reachable")
            ],
        )
    buf_path = Path(buf["buf_file_path"])
    content = commit.tree[str(buf_path.name)].data_stream.read().decode("utf-8")
    Writer().write_buf(content, buf_path)
    branch.set_commit(commit)
    return OperationResult(success=True, message="checkout")


def buf_diff(
    session_dir: Path,
    buffer_id: str,
    sha1: str,
    sha2: str,
    repo: Any,
) -> str:
    """Return git diff text between two SHAs."""
    if _resolve_commit(repo, sha1) is None or _resolve_commit(repo, sha2) is None:
        return ""
    return repo.git.diff(sha1, sha2)
''')
).strip()

CLIPBOARD_PY = (
    textwrap.dedent('''
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

''')
    + HELPER_SOURCE_BYTES
    + textwrap.dedent('''

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
    new_document, fragment = formatter.cut_fragment(document, source_address)
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
    if clip["formatter"] != formatter.formatter_name:
        raise ValueError(ErrorCode.CLIPBOARD_FORMAT_MISMATCH.value)
    if clip.get("paste_policy") == "reject_if_source_revision_changed":
        head = repo.heads[f"buf/{buffer_id}"].commit.hexsha
        if head != clip.get("source_revision"):
            raise ValueError(ErrorCode.CLIPBOARD_SOURCE_STALE.value)
    fragment = formatter.from_string(clip["body"])
    new_document = formatter.paste_fragment(
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
''')
).strip()

WRITE_ALL_PY = (
    textwrap.dedent('''
"""Bulk save all modified remote buffers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_editor.contracts import Diagnostic, ErrorCode, WriteAllResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.save_pipeline import run_validate
from ai_editor.sessions.session_dir import read_session_settings, update_buffer_in_settings
from ai_editor.sessions.session_git import commit_buffer, history_diagnostic

''')
    + HELPER_SOURCE_BYTES
    + textwrap.dedent('''


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
            ca_client.upload_content(buf["project_id"], buf["file_id"], content)
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
''')
).strip()

RECOVERY_PY = textwrap.dedent('''
"""Startup sweep and session reconnect helpers."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from ai_editor.contracts import ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.session_dir import SETTINGS_NAME, read_session_settings

logger = logging.getLogger(__name__)


def release_all_locks_for_session(
    ca_client: CodeAnalysisClient,
    buffers: list[dict[str, Any]],
    allow_foreign_session: bool = False,
) -> None:
    """Best-effort unlock_file per locked buffer."""
    _ = allow_foreign_session
    for buf in buffers:
        lock_id = buf.get("lock_session_id")
        file_id = buf.get("file_id")
        project_id = buf.get("project_id")
        if not lock_id or not file_id or not project_id:
            continue
        try:
            ca_client.unlock_file(lock_id, project_id, file_id)
        except Exception as exc:
            logger.warning("unlock failed: %s", exc)


def startup_sweep(base_dir: str | Path, ca_client: CodeAnalysisClient) -> None:
    """Policy B: drop orphan dirs; release stale locks on valid dirs."""
    base = Path(base_dir)
    if not base.exists():
        return
    for child in base.iterdir():
        if not child.is_dir():
            continue
        settings_path = child / SETTINGS_NAME
        try:
            if not settings_path.exists():
                shutil.rmtree(child, ignore_errors=True)
                continue
            settings = read_session_settings(child)
        except Exception:
            shutil.rmtree(child, ignore_errors=True)
            continue
        buffers = settings.get("open_buffers", [])
        stale = [
            b
            for b in buffers
            if b.get("lock_mode") == "full"
            and not b.get("saved")
            and not b.get("readonly")
            and b.get("lock_session_id")
        ]
        release_all_locks_for_session(ca_client, stale, allow_foreign_session=True)


def reconnect_session(base_dir: str | Path, session_key: str) -> dict[str, Any]:
    """Load ses_settings for existing session directory."""
    session_dir = Path(base_dir) / session_key
    if not session_dir.is_dir():
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)
    return read_session_settings(session_dir)
''').strip()

SESSION_API_PY = textwrap.dedent('''
"""Public session API for command layer."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ai_editor.contracts import BufferDescriptor, ErrorCode, SessionDescriptor
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.registry import FormatterRegistry
from ai_editor.sessions.buffer_close import close_session
from ai_editor.sessions.recovery import reconnect_session
from ai_editor.sessions.session_dir import (
    create_session_dir,
    read_session_settings,
    write_session_settings,
)
from ai_editor.sessions.session_git import init_session_git


def _settings_to_descriptor(settings: dict[str, Any]) -> SessionDescriptor:
    """Map ses_settings open_buffers to public BufferDescriptor list."""
    session_key = settings["session_key"]
    open_buffers: list[BufferDescriptor] = []
    for buf in settings.get("open_buffers", []):
        open_buffers.append(
            BufferDescriptor(
                buffer_id=buf["buffer_id"],
                session_key=session_key,
                filename=buf.get("filename", ""),
                relative_path=buf.get("relative_path"),
                formatter=buf.get("formatter", ""),
                project_id=buf.get("project_id", ""),
                modified=bool(buf.get("modified")),
                readonly=bool(buf.get("readonly")),
                buf_file_path=buf.get("buf_file_path", ""),
            )
        )
    return SessionDescriptor(session_key=session_key, open_buffers=open_buffers)


def connect(
    base_dir: str | Path,
    ca_client: CodeAnalysisClient,
    formatter_registry: FormatterRegistry,
    config: dict[str, Any],
    readonly: bool = False,
) -> SessionDescriptor:
    """Create new session dir + git repo; store ca_session_id in settings."""
    _ = formatter_registry
    session_key = str(uuid.uuid4())
    session_dir = create_session_dir(base_dir, session_key, readonly=readonly)
    init_session_git(session_dir)
    settings = read_session_settings(session_dir)
    settings["ca_session_id"] = config["ca_session_id"]
    write_session_settings(session_dir, settings)
    return _settings_to_descriptor(settings)


def reconnect(
    base_dir: str | Path,
    session_key: str,
    ca_client: CodeAnalysisClient,
) -> SessionDescriptor:
    """Reconnect to existing session directory."""
    _ = ca_client
    settings = reconnect_session(base_dir, session_key)
    return _settings_to_descriptor(settings)


def close_session_api(
    base_dir: str | Path,
    session_key: str,
    ca_client: CodeAnalysisClient,
    force: bool = False,
) -> SessionDescriptor:
    """Close session via buffer_close.close_session."""
    session_dir = Path(base_dir) / session_key
    close_session(session_dir, session_key, ca_client, force=force)
    return SessionDescriptor(session_key=session_key)


def session_status(base_dir: str | Path, session_key: str) -> SessionDescriptor:
    """Read-only session descriptor."""
    session_dir = Path(base_dir) / session_key
    if not session_dir.is_dir():
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)
    return _settings_to_descriptor(read_session_settings(session_dir))
''').strip()

SESSIONS_INIT_EXPORTS = textwrap.dedent('''
"""Session layer — buffer lifecycle, clipboard, recovery, public API."""
from ai_editor.sessions.session_api import (
    close_session_api,
    connect,
    reconnect,
    session_status,
)

__all__ = [
    "connect",
    "reconnect",
    "close_session_api",
    "session_status",
]
''').strip()
