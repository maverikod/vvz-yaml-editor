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
