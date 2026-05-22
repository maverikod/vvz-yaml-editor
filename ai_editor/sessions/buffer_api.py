"""Public buffer API — session-scoped facade over G-005 buffer modules."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_editor.contracts import ErrorCode, OperationResult, ValidationResult, WriteAllResult
from ai_editor.editor_core.buffer import BufferState
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.formatter_registry import FormatterRegistry
from ai_editor.editor_core.save_pipeline import run_validate
from ai_editor.formatters.sidecar import load_sidecar, session_sidecar_path
from ai_editor.sessions.buffer_close import close_buffer as _close_buffer
from ai_editor.sessions.buffer_new import create_new_buffer
from ai_editor.sessions.buffer_open import open_buffer as _open_buffer
from ai_editor.sessions.buffer_reload import reload_buffer as _reload_buffer
from ai_editor.sessions.buffer_save import save_as_buffer as _save_as_buffer
from ai_editor.sessions.buffer_save import save_buffer as _save_buffer
from ai_editor.sessions.session_dir import read_session_settings
from ai_editor.sessions.session_git import get_repo
from ai_editor.sessions.write_all import write_all as _write_all


@dataclass
class LoadedBufferState(BufferState):
    """BufferState plus live formatter instance and document tree for mutations."""

    formatter_instance: Any = None
    tree: Any = None
    formatter_name: str = ""
    success: bool = True


def _session_dir(base_dir: str | Path, session_key: str) -> Path:
    path = Path(base_dir) / session_key
    if not path.is_dir():
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)
    return path


def _repo_for_session(session_dir: Path, repo_map: dict[str, Any]) -> Any:
    repo = get_repo(session_dir)
    repo_map.setdefault("_session", repo)
    return repo


def _repo_for_buffer(
    session_dir: Path, buffer_id: str, repo_map: dict[str, Any]
) -> Any:
    if buffer_id not in repo_map:
        repo_map[buffer_id] = get_repo(session_dir)
    return repo_map[buffer_id]


def _load_document(
    formatter_registry: FormatterRegistry,
    buf: dict[str, Any],
    session_dir: Path,
) -> tuple[Any, Any]:
    fmt_name = buf.get("formatter", "text")
    cls = formatter_registry.get_by_name(fmt_name)
    if cls is None:
        raise ValueError(ErrorCode.FORMATTER_NOT_FOUND.value)
    formatter = cls()
    buf_path = Path(buf["buf_file_path"])
    source = buf_path.read_text(encoding="utf-8")
    sidecar_path = session_sidecar_path(session_dir, buf["buffer_id"])
    sidecar = load_sidecar(sidecar_path, source)
    if sidecar is not None and hasattr(formatter, "open_tree"):
        document = formatter.open_tree(source)
    elif fmt_name == "cst":
        from ai_editor.formatters.cst.tree_builder import create_tree_from_code

        document = create_tree_from_code(source)
        formatter._tree = document  # noqa: SLF001
    else:
        document = formatter.open_tree(source)
    return formatter, document


def open_buffer(
    base_dir: str | Path,
    session_key: str,
    project_id: str,
    file_path: str,
    ca_client: CodeAnalysisClient,
    formatter_registry: FormatterRegistry,
    *,
    formatter_name: str = "auto",
    open_as_text: bool = False,
    readonly: bool = False,
    repo_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_dir = _session_dir(base_dir, session_key)
    repo_map = repo_map if repo_map is not None else {}
    repo = _repo_for_session(session_dir, repo_map)
    settings = read_session_settings(session_dir)
    config = {"ca_session_id": settings.get("ca_session_id", "")}
    result = _open_buffer(
        session_dir,
        session_key,
        project_id,
        file_path,
        ca_client,
        formatter_registry,
        repo,
        config,
        formatter=formatter_name,
        open_as_text=open_as_text,
        readonly=readonly,
    )
    if result.get("success") and result.get("buffer_id"):
        _repo_for_buffer(session_dir, result["buffer_id"], repo_map)
    return result


def new_buffer(
    base_dir: str | Path,
    session_key: str,
    formatter_registry: FormatterRegistry,
    *,
    formatter_name: str = "auto",
    initial_content: str = "",
    display_name: str | None = None,
    repo_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_dir = _session_dir(base_dir, session_key)
    repo_map = repo_map if repo_map is not None else {}
    repo = _repo_for_session(session_dir, repo_map)
    name = formatter_name
    if name == "auto":
        name = "text"
    result = create_new_buffer(
        session_dir,
        session_key,
        name,
        initial_content,
        display_name or "",
        formatter_registry,
        repo,
    )
    if result.get("buffer_id"):
        _repo_for_buffer(session_dir, result["buffer_id"], repo_map)
    return result


def close_buffer(
    base_dir: str | Path,
    session_key: str,
    buffer_id: str,
    ca_client: CodeAnalysisClient,
    *,
    force: bool = False,
    repo_map: dict[str, Any] | None = None,
) -> OperationResult:
    session_dir = _session_dir(base_dir, session_key)
    repo_map = repo_map if repo_map is not None else {}
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
    formatter, document = _load_document(
        FormatterRegistry.get_instance(), buf, session_dir
    )
    _ = document
    repo = _repo_for_buffer(session_dir, buffer_id, repo_map)
    return _close_buffer(session_dir, buffer_id, formatter, ca_client, repo, force=force)


def save_buffer(
    base_dir: str | Path,
    session_key: str,
    buffer_id: str,
    ca_client: CodeAnalysisClient,
    *,
    repo: Any | None = None,
    repo_map: dict[str, Any] | None = None,
) -> OperationResult:
    session_dir = _session_dir(base_dir, session_key)
    repo_map = repo_map if repo_map is not None else {}
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
    formatter, document = _load_document(
        FormatterRegistry.get_instance(), buf, session_dir
    )
    if repo is None:
        repo = _repo_for_buffer(session_dir, buffer_id, repo_map)
    return _save_buffer(
        session_dir, buffer_id, formatter, document, ca_client, repo
    )


def save_as_buffer(
    base_dir: str | Path,
    session_key: str,
    buffer_id: str,
    ca_client: CodeAnalysisClient,
    new_relative_path: str,
    *,
    overwrite: bool = False,
    repo: Any | None = None,
    repo_map: dict[str, Any] | None = None,
) -> OperationResult:
    session_dir = _session_dir(base_dir, session_key)
    repo_map = repo_map if repo_map is not None else {}
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
    formatter, document = _load_document(
        FormatterRegistry.get_instance(), buf, session_dir
    )
    if repo is None:
        repo = _repo_for_buffer(session_dir, buffer_id, repo_map)
    return _save_as_buffer(
        session_dir,
        buffer_id,
        formatter,
        document,
        ca_client,
        new_relative_path,
        overwrite=overwrite,
        repo=repo,
    )


def reload_buffer(
    base_dir: str | Path,
    session_key: str,
    buffer_id: str,
    ca_client: CodeAnalysisClient,
    formatter_registry: FormatterRegistry,
    *,
    repo: Any | None = None,
    repo_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_dir = _session_dir(base_dir, session_key)
    repo_map = repo_map if repo_map is not None else {}
    if repo is None:
        repo = _repo_for_buffer(session_dir, buffer_id, repo_map)
    return _reload_buffer(
        session_dir, session_key, buffer_id, ca_client, formatter_registry, repo
    )


def get_buffer_state(
    base_dir: str | Path,
    session_key: str,
    buffer_id: str,
    ca_client: CodeAnalysisClient,  # noqa: ARG001
    formatter_registry: FormatterRegistry,
) -> LoadedBufferState:
    session_dir = _session_dir(base_dir, session_key)
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return LoadedBufferState(
            buffer_id=buffer_id,
            formatter="",
            preview="",
            modified=False,
            readonly=False,
            success=False,
        )
    formatter, document = _load_document(formatter_registry, buf, session_dir)
    preview = formatter.render_skeleton()
    return LoadedBufferState(
        buffer_id=buffer_id,
        formatter=buf.get("formatter", ""),
        preview=preview,
        modified=bool(buf.get("modified")),
        readonly=bool(buf.get("readonly")),
        file_path=buf.get("relative_path"),
        relative_path=buf.get("relative_path"),
        formatter_instance=formatter,
        tree=document,
        formatter_name=buf.get("formatter", ""),
        success=True,
    )


def write_all(
    base_dir: str | Path,
    session_key: str,
    ca_client: CodeAnalysisClient,
    *,
    force: bool = False,
    repo_map: dict[str, Any] | None = None,
) -> WriteAllResult:
    session_dir = _session_dir(base_dir, session_key)
    repo_map = repo_map if repo_map is not None else {}
    settings = read_session_settings(session_dir)
    formatter_map: dict[str, tuple[Any, Any, Any]] = {}
    registry = FormatterRegistry.get_instance()
    for buf in settings.get("open_buffers", []):
        bid = buf["buffer_id"]
        try:
            formatter, document = _load_document(registry, buf, session_dir)
        except ValueError:
            continue
        repo = _repo_for_buffer(session_dir, bid, repo_map)
        formatter_map[bid] = (formatter, document, repo)
    return _write_all(session_dir, ca_client, formatter_map, force=force)


def validate_buffer(
    base_dir: str | Path,
    session_key: str,
    buffer_id: str,
    formatter_registry: FormatterRegistry,
) -> ValidationResult:
    session_dir = _session_dir(base_dir, session_key)
    settings = read_session_settings(session_dir)
    buf = next(
        (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
        None,
    )
    if not buf:
        return ValidationResult(
            success=False,
            diagnostics=[],
        )
    formatter, document = _load_document(formatter_registry, buf, session_dir)
    return run_validate(formatter, document)


def validate_file(
    base_dir: str | Path,
    session_key: str,
    ca_client: CodeAnalysisClient,  # noqa: ARG001
    formatter_registry: FormatterRegistry,
    *,
    file_path: str | None = None,
    buffer_id: str | None = None,
    project_id: str | None = None,  # noqa: ARG001
    formatter_name: str = "auto",
    schema: dict[str, Any] | None = None,  # noqa: ARG001
) -> ValidationResult:
    if buffer_id:
        return validate_buffer(base_dir, session_key, buffer_id, formatter_registry)
    if not file_path:
        return ValidationResult(success=False, diagnostics=[])
    cls = formatter_registry.get_by_extension(Path(file_path).suffix.lower())
    if cls is None:
        return ValidationResult(success=False, diagnostics=[])
    formatter = cls()
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        tree = formatter.open_tree(content)
    except Exception as exc:
        return ValidationResult(
            success=False,
            diagnostics=[],
        )
    return run_validate(formatter, tree)
