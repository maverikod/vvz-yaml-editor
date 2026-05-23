"""SessionManager — delegates all domain operations to G-005 session layer."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import git

from ai_editor.contracts import OperationResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.formatter_registry import FormatterRegistry
from ai_editor.search import Search

# G-005 inline signatures (delegation targets):
# session_api.connect(base_dir, readonly=False) -> SessionDescriptor
# session_api.reconnect(base_dir, session_key) -> SessionDescriptor
# session_api.close_session(base_dir, session_key, force=False) -> OperationResult
# session_api.session_status(base_dir, session_key) -> SessionDescriptor
# buffer_api.open_buffer(...) -> BufferDescriptor
# buffer_api.new_buffer(...) -> BufferDescriptor
# buffer_api.close_buffer(...) -> OperationResult
# buffer_api.save_buffer(...) -> OperationResult
# buffer_api.save_as_buffer(...) -> OperationResult
# buffer_api.reload_buffer(...) -> OperationResult
# buffer_api.get_buffer_state(...) -> BufferState
# buffer_api.write_all(...) -> WriteAllResult
# history_api.undo(session_key, buffer_id, repo, steps=1) -> OperationResult
# history_api.redo(session_key, buffer_id, repo, steps=1) -> OperationResult
# clipboard.copy_to_clipboard(...) / cut_to_clipboard(...) / paste_from_clipboard(...)
# mutation_api.execute_mutation(...) after formatter.mutate_batch(...)


class SessionManager:
    """Holds session state wiring; no module-level singleton."""

    def __init__(
        self,
        base_dir: str,
        ca_client: CodeAnalysisClient,
        formatter_registry: FormatterRegistry,
        *,
        editor_server_uuid: str = "",
    ) -> None:
        self.base_dir = base_dir
        self.ca_client = ca_client
        self.formatter_registry = formatter_registry
        self.editor_server_uuid = str(editor_server_uuid or "").strip()
        self.repo_map: dict[str, git.Repo] = {}
        self._buffer_cache: dict[str, tuple[Any, Any]] = {}
        self._search = Search(self._get_buffer_context)

    def _repo(self, buffer_id: str) -> git.Repo | None:
        return self.repo_map.get(buffer_id)

    def _ensure_repo(self, session_key: str, buffer_id: str) -> git.Repo:
        """Return git repo for buffer, loading from session dir when not cached."""
        cached = self.repo_map.get(buffer_id)
        if cached is not None:
            return cached
        from ai_editor.sessions.buffer_api import _repo_for_buffer

        session_dir = Path(self.base_dir) / session_key
        if not session_dir.is_dir():
            raise ValueError("session not found")
        return _repo_for_buffer(session_dir, buffer_id, self.repo_map)

    def _get_buffer_context(self, session_key: str, buffer_id: str) -> dict[str, Any] | None:
        cache_key = f"{session_key}:{buffer_id}"
        if cache_key in self._buffer_cache:
            formatter, tree = self._buffer_cache[cache_key]
            return {
                "formatter": formatter,
                "tree": tree,
                "buffer_id": buffer_id,
                "formatter_name": getattr(formatter, "formatter_name", ""),
            }
        from ai_editor.sessions import buffer_api

        state = buffer_api.get_buffer_state(
            self.base_dir, session_key, buffer_id, self.ca_client, self.formatter_registry
        )
        if not getattr(state, "success", True):
            return None
        self._buffer_cache[cache_key] = (state.formatter_instance, state.tree)
        return {
            "formatter": state.formatter_instance,
            "tree": state.tree,
            "buffer_id": buffer_id,
            "formatter_name": state.formatter_name,
        }

    def _invalidate_buffer_cache(self, session_key: str, buffer_id: str) -> None:
        self._buffer_cache.pop(f"{session_key}:{buffer_id}", None)

    def connect(self, readonly: bool = False, ca_session_id: str = "") -> Any:
        from code_analysis_client import SessionNotFoundError

        from ai_editor.contracts import ErrorCode
        from ai_editor.sessions import session_api
        from ai_editor.sessions.ca_session import verify_parent_ca_session

        ca_session_id = str(ca_session_id or "").strip()
        if not ca_session_id:
            raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)
        try:
            verify_parent_ca_session(self.ca_client, ca_session_id)
        except ValueError:
            raise
        except SessionNotFoundError as exc:
            raise ValueError(ErrorCode.SESSION_NOT_FOUND.value) from exc

        config = {
            "ca_session_id": ca_session_id,
            "editor_server_uuid": self.editor_server_uuid,
        }
        return session_api.connect(
            self.base_dir,
            self.ca_client,
            self.formatter_registry,
            config,
            readonly=readonly,
        )

    def reconnect(self, session_key: str) -> Any:
        from ai_editor.sessions import session_api

        return session_api.reconnect(self.base_dir, session_key, self.ca_client)

    def _evict_session_state(self, session_key: str) -> None:
        """Drop cached formatter state and git handles for a closed session."""
        prefix = f"{session_key}:"
        for key in list(self._buffer_cache):
            if key.startswith(prefix):
                self._buffer_cache.pop(key, None)
        session_git = (Path(self.base_dir) / session_key / "git").resolve()
        for key, repo in list(self.repo_map.items()):
            try:
                if Path(repo.git_dir).resolve() == session_git:
                    self.repo_map.pop(key, None)
            except Exception:
                continue

    def close_session(self, session_key: str, force: bool = False) -> Any:
        from ai_editor.sessions import session_api

        result = session_api.close_session_api(
            self.base_dir, session_key, self.ca_client, force=force
        )
        session_gone = not (Path(self.base_dir) / session_key).exists()
        if session_gone:
            self._evict_session_state(session_key)
        return result

    def close_invalid_sessions(
        self,
        session_key: str,
        *,
        mode: str = "local_only",
        force: bool = False,
        dry_run: bool = False,
    ) -> Any:
        from ai_editor.sessions.invalid_session import close_invalid_sessions

        return close_invalid_sessions(
            self.base_dir,
            self.ca_client,
            session_key=session_key,
            mode=mode,  # type: ignore[arg-type]
            force=force,
            dry_run=dry_run,
        )

    def session_status(self, session_key: str) -> Any:
        from ai_editor.sessions import session_api

        return session_api.session_status(self.base_dir, session_key)

    def open_buffer(
        self,
        session_key: str,
        project_id: str,
        file_path: str,
        formatter: str = "auto",
        open_as_text: bool = False,
        readonly: bool = False,
    ) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.open_buffer(
            self.base_dir,
            session_key,
            project_id,
            file_path,
            self.ca_client,
            self.formatter_registry,
            formatter_name=formatter,
            open_as_text=open_as_text,
            readonly=readonly,
            repo_map=self.repo_map,
        )

    def new_buffer(
        self,
        session_key: str,
        formatter_name: str = "auto",
        initial_content: str = "",
        display_name: str | None = None,
    ) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.new_buffer(
            self.base_dir,
            session_key,
            self.formatter_registry,
            formatter_name=formatter_name,
            initial_content=initial_content,
            display_name=display_name,
            repo_map=self.repo_map,
        )

    def close_buffer(self, session_key: str, buffer_id: str, force: bool = False) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.close_buffer(
            self.base_dir,
            session_key,
            buffer_id,
            self.ca_client,
            force=force,
            repo_map=self.repo_map,
        )

    def save_buffer(
        self,
        session_key: str,
        buffer_id: str,
        *,
        project_id: str | None = None,
        file_path: str | None = None,
        release_lock: bool = False,
    ) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.save_buffer(
            self.base_dir,
            session_key,
            buffer_id,
            self.ca_client,
            repo=self._ensure_repo(session_key, buffer_id),
            project_id=project_id,
            file_path=file_path,
            release_lock=release_lock,
        )

    def save_as_buffer(
        self,
        session_key: str,
        buffer_id: str,
        new_relative_path: str,
        overwrite: bool = False,
    ) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.save_as_buffer(
            self.base_dir,
            session_key,
            buffer_id,
            self.ca_client,
            new_relative_path,
            overwrite=overwrite,
            repo=self._ensure_repo(session_key, buffer_id),
        )

    def reload_buffer(self, session_key: str, buffer_id: str) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.reload_buffer(
            self.base_dir,
            session_key,
            buffer_id,
            self.ca_client,
            self.formatter_registry,
            repo=self._ensure_repo(session_key, buffer_id),
        )

    def get_buffer_state(self, session_key: str, buffer_id: str) -> Any:
        ctx = self._get_buffer_context(session_key, buffer_id)
        if ctx is None:
            from ai_editor.editor_core.buffer import BufferState

            return BufferState(
                buffer_id=buffer_id,
                formatter="",
                preview="",
                modified=False,
                readonly=False,
            )
        formatter = ctx["formatter"]
        from ai_editor.sessions import buffer_api
        from ai_editor.sessions.session_dir import read_session_settings

        session_dir = Path(self.base_dir) / session_key
        settings = read_session_settings(session_dir)
        buf = next(
            (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
            None,
        )
        preview = formatter.render_skeleton()
        return buffer_api.LoadedBufferState(
            buffer_id=buffer_id,
            formatter=buf.get("formatter", "") if buf else "",
            preview=preview,
            modified=bool(buf.get("modified")) if buf else False,
            readonly=bool(buf.get("readonly")) if buf else False,
            file_path=buf.get("relative_path") if buf else None,
            relative_path=buf.get("relative_path") if buf else None,
            formatter_instance=formatter,
            tree=ctx["tree"],
            formatter_name=ctx["formatter_name"],
            success=True,
        )

    def get_buffer_file(
        self,
        session_key: str,
        buffer_id: str,
        *,
        lock: bool = True,
    ) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.get_buffer_file_content(
            self.base_dir,
            session_key,
            buffer_id,
            lock=lock,
        )

    def write_all(self, session_key: str, force: bool = False) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.write_all(
            self.base_dir,
            session_key,
            self.ca_client,
            force=force,
            repo_map=self.repo_map,
        )

    def validate_buffer(self, session_key: str, buffer_id: str) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.validate_buffer(
            self.base_dir,
            session_key,
            buffer_id,
            self.formatter_registry,
        )

    def validate_file(
        self,
        session_key: str,
        file_path: str | None = None,
        buffer_id: str | None = None,
        project_id: str | None = None,
        formatter: str = "auto",
        schema: dict[str, Any] | None = None,
    ) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.validate_file(
            self.base_dir,
            session_key,
            self.ca_client,
            self.formatter_registry,
            file_path=file_path,
            buffer_id=buffer_id,
            project_id=project_id,
            formatter_name=formatter,
            schema=schema,
        )

    def mutate_batch(
        self, session_key: str, buffer_id: str, operations: list[dict[str, Any]]
    ) -> OperationResult:
        ctx = self._get_buffer_context(session_key, buffer_id)
        if ctx is None:
            return OperationResult(success=False, message="buffer not found")
        formatter = ctx["formatter"]
        document = ctx["tree"]
        from ai_editor.sessions.buffer_mutation import _source_text, execute_mutation

        source_before = _source_text(formatter, document)
        try:
            new_document = formatter.mutate_batch(document, operations)
        except Exception as exc:  # noqa: BLE001
            return OperationResult(success=False, message=str(exc))
        from ai_editor.sessions.session_dir import read_session_settings

        session_dir = Path(self.base_dir) / session_key
        settings = read_session_settings(session_dir)
        readonly_session = bool(settings.get("readonly"))
        buf = next(
            (b for b in settings.get("open_buffers", []) if b["buffer_id"] == buffer_id),
            None,
        )
        readonly_buffer = bool(buf.get("readonly")) if buf else False
        result = execute_mutation(
            session_dir,
            buffer_id,
            formatter,
            document,
            new_document,
            "mutate_batch",
            f"{len(operations)} ops",
            self._ensure_repo(session_key, buffer_id),
            readonly_session=readonly_session,
            readonly_buffer=readonly_buffer,
            source_before=source_before,
        )
        if not result.get("success", True):
            return OperationResult(success=False, message=result.get("message", "mutation failed"))
        self._invalidate_buffer_cache(session_key, buffer_id)
        self._buffer_cache[f"{session_key}:{buffer_id}"] = (formatter, new_document)
        return OperationResult(success=True, message="mutated")

    def undo(self, session_key: str, buffer_id: str, steps: int = 1) -> Any:
        from ai_editor.sessions import undo_redo

        ctx = self._get_buffer_context(session_key, buffer_id)
        if ctx is None:
            return OperationResult(success=False, message="buffer not found")
        return undo_redo.undo(
            Path(self.base_dir) / session_key,
            buffer_id,
            ctx["formatter"],
            self._ensure_repo(session_key, buffer_id),
            steps=steps,
        )

    def redo(self, session_key: str, buffer_id: str, steps: int = 1) -> Any:
        from ai_editor.sessions import undo_redo

        ctx = self._get_buffer_context(session_key, buffer_id)
        if ctx is None:
            return OperationResult(success=False, message="buffer not found")
        return undo_redo.redo(
            Path(self.base_dir) / session_key,
            buffer_id,
            ctx["formatter"],
            self._ensure_repo(session_key, buffer_id),
            steps=steps,
        )

    def copy_fragment(self, session_key: str, buffer_id: str, address: Any) -> Any:
        from ai_editor.sessions import clipboard

        return clipboard.copy_to_clipboard(
            self.base_dir, session_key, buffer_id, address, self.formatter_registry
        )

    def cut_fragment(self, session_key: str, buffer_id: str, address: Any) -> Any:
        from ai_editor.sessions import clipboard

        return clipboard.cut_to_clipboard(
            self.base_dir,
            session_key,
            buffer_id,
            address,
            self.formatter_registry,
            repo=self._ensure_repo(session_key, buffer_id),
        )

    def paste_fragment(
        self, session_key: str, buffer_id: str, address: Any, mode: str
    ) -> Any:
        from ai_editor.sessions import clipboard

        return clipboard.paste_from_clipboard(
            self.base_dir,
            session_key,
            buffer_id,
            address,
            mode,
            self.formatter_registry,
            repo=self._ensure_repo(session_key, buffer_id),
        )

    def find(
        self,
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> Any:
        return self._search.find(session_key, buffer_id, query, scope=scope)

    def find_one(
        self,
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> Any:
        return self._search.find_one(session_key, buffer_id, query, scope=scope)

    def list_units(
        self, session_key: str, buffer_id: str, scope: str | None = None
    ) -> Any:
        return self._search.list_units(session_key, buffer_id, scope=scope)

    def formatter_commands(
        self, buffer_id: str | None = None, formatter: str | None = None
    ) -> Any:
        if formatter:
            cls = self.formatter_registry.get_by_name(formatter)
            if cls is None:
                from ai_editor.contracts import ErrorCode, OperationResult

                return OperationResult(
                    success=False,
                    error_code=ErrorCode.FORMATTER_NOT_FOUND,
                    message=formatter,
                )
            fmt = cls()
        elif buffer_id:
            raise ValueError("formatter required when buffer_id omitted in this stub")
        else:
            cls = self.formatter_registry.get_by_name("text")
            fmt = cls() if cls is not None else None
        if fmt is None:
            from ai_editor.contracts import ErrorCode, OperationResult

            return OperationResult(
                success=False,
                error_code=ErrorCode.FORMATTER_NOT_FOUND,
                message="text",
            )
        catalog = fmt.list_commands()
        from dataclasses import asdict

        return {"success": True, "commands": asdict(catalog)}
