"""Thin synchronous facade over SessionManager — sole import for commands and CLI."""
from __future__ import annotations

from typing import Any

def _get_session_manager() -> Any:
    from ai_editor.api_init import get_session_manager

    return get_session_manager()


def connect(*, ca_session_id: str, readonly: bool = False) -> Any:
    return _get_session_manager().connect(readonly=readonly, ca_session_id=ca_session_id)

def reconnect(session_key: str) -> Any:
    return _get_session_manager().reconnect(session_key)

def close_session(session_key: str, force: bool = False) -> Any:
    return _get_session_manager().close_session(session_key, force=force)

def close_invalid_sessions(
    session_key: str,
    *,
    mode: str = "local_only",
    force: bool = False,
    dry_run: bool = False,
) -> Any:
    return _get_session_manager().close_invalid_sessions(
        session_key,
        mode=mode,
        force=force,
        dry_run=dry_run,
    )

def session_status(session_key: str) -> Any:
    return _get_session_manager().session_status(session_key)

def open_buffer(
    session_key: str,
    project_id: str,
    file_path: str,
    formatter: str = "auto",
    open_as_text: bool = False,
    readonly: bool = False,
) -> Any:
    return _get_session_manager().open_buffer(
        session_key, project_id, file_path, formatter, open_as_text, readonly
    )

def new_buffer(
    session_key: str,
    formatter_name: str = "auto",
    initial_content: str = "",
    display_name: str | None = None,
) -> Any:
    return _get_session_manager().new_buffer(
        session_key, formatter_name, initial_content, display_name
    )

def close_buffer(
    session_key: str, buffer_id: str, force: bool = False, dry_run: bool = False
) -> Any:
    if dry_run:
        return {"success": True, "dry_run": True}
    return _get_session_manager().close_buffer(session_key, buffer_id, force=force)

def get_buffer_state(session_key: str, buffer_id: str) -> Any:
    return _get_session_manager().get_buffer_state(session_key, buffer_id)

def get_buffer_file(session_key: str, buffer_id: str, *, lock: bool = True) -> Any:
    return _get_session_manager().get_buffer_file(session_key, buffer_id, lock=lock)

def save_buffer(
    session_key: str,
    buffer_id: str,
    dry_run: bool = False,
    *,
    project_id: str | None = None,
    file_path: str | None = None,
    release_lock: bool = False,
) -> Any:
    if dry_run:
        return {"success": True, "dry_run": True}
    return _get_session_manager().save_buffer(
        session_key,
        buffer_id,
        project_id=project_id,
        file_path=file_path,
        release_lock=release_lock,
    )

def save_as_buffer(
    session_key: str,
    buffer_id: str,
    new_relative_path: str,
    overwrite: bool = False,
    dry_run: bool = False,
) -> Any:
    if dry_run:
        return {"success": True, "dry_run": True}
    return _get_session_manager().save_as_buffer(
        session_key, buffer_id, new_relative_path, overwrite=overwrite
    )

def reload_buffer(session_key: str, buffer_id: str) -> Any:
    return _get_session_manager().reload_buffer(session_key, buffer_id)

def write_all(session_key: str, force: bool = False, dry_run: bool = False) -> Any:
    if dry_run:
        return {"success": True, "dry_run": True}
    return _get_session_manager().write_all(session_key, force=force)

def validate_buffer(session_key: str, buffer_id: str) -> Any:
    return _get_session_manager().validate_buffer(session_key, buffer_id)

def validate_file(
    session_key: str,
    file_path: str | None = None,
    buffer_id: str | None = None,
    project_id: str | None = None,
    formatter: str = "auto",
    schema: dict[str, Any] | None = None,
) -> Any:
    return _get_session_manager().validate_file(
        session_key, file_path, buffer_id, project_id, formatter, schema
    )

def mutate_batch(
    session_key: str, buffer_id: str, operations: list[dict[str, Any]], dry_run: bool = False
) -> Any:
    if dry_run:
        return {"success": True, "dry_run": True, "operations": len(operations)}
    return _get_session_manager().mutate_batch(session_key, buffer_id, operations)

def undo(session_key: str, buffer_id: str, steps: int = 1) -> Any:
    return _get_session_manager().undo(session_key, buffer_id, steps=steps)

def redo(session_key: str, buffer_id: str, steps: int = 1) -> Any:
    return _get_session_manager().redo(session_key, buffer_id, steps=steps)

def copy(session_key: str, source: dict[str, Any]) -> Any:
    return _get_session_manager().copy_fragment(
        session_key, source["buffer_id"], source["address"]
    )

def cut(session_key: str, source: dict[str, Any], dry_run: bool = False) -> Any:
    if dry_run:
        return {"success": True, "dry_run": True}
    return _get_session_manager().cut_fragment(
        session_key, source["buffer_id"], source["address"]
    )

def paste(
    session_key: str, target: dict[str, Any], mode: str, dry_run: bool = False
) -> Any:
    if dry_run:
        return {"success": True, "dry_run": True}
    return _get_session_manager().paste_fragment(
        session_key, target["buffer_id"], target["address"], mode
    )

def find(
    session_key: str,
    buffer_id: str,
    query: dict[str, Any],
    scope: str | None = None,
) -> Any:
    return _get_session_manager().find(session_key, buffer_id, query, scope)

def find_one(
    session_key: str,
    buffer_id: str,
    query: dict[str, Any],
    scope: str | None = None,
) -> Any:
    return _get_session_manager().find_one(session_key, buffer_id, query, scope)

def list_units(session_key: str, buffer_id: str, scope: str | None = None) -> Any:
    return _get_session_manager().list_units(session_key, buffer_id, scope)

def formatter_commands(buffer_id: str | None = None, formatter: str | None = None) -> Any:
    return _get_session_manager().formatter_commands(buffer_id, formatter)
