"""SessionManager — delegates all domain operations to G-005 session layer."""
from __future__ import annotations

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
    ) -> None:
        self.base_dir = base_dir
        self.ca_client = ca_client
        self.formatter_registry = formatter_registry
        self.repo_map: dict[str, git.Repo] = {}
        self._search = Search(self._get_buffer_context)

    def _repo(self, buffer_id: str) -> git.Repo | None:
        return self.repo_map.get(buffer_id)

    def _get_buffer_context(self, session_key: str, buffer_id: str) -> dict[str, Any] | None:
        from ai_editor.sessions import buffer_api

        state = buffer_api.get_buffer_state(
            self.base_dir, session_key, buffer_id, self.ca_client, self.formatter_registry
        )
        if not getattr(state, "success", True):
            return None
        return {
            "formatter": state.formatter,
            "tree": state.tree,
            "buffer_id": buffer_id,
            "formatter_name": state.formatter_name,
        }

    def connect(self, readonly: bool = False) -> Any:
        from ai_editor.sessions import session_api

        return session_api.connect(self.base_dir, readonly=readonly)

    def reconnect(self, session_key: str) -> Any:
        from ai_editor.sessions import session_api

        return session_api.reconnect(self.base_dir, session_key)

    def close_session(self, session_key: str, force: bool = False) -> Any:
        from ai_editor.sessions import session_api

        return session_api.close_session(self.base_dir, session_key, force=force)

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
            self.base_dir, session_key, buffer_id, force=force, repo_map=self.repo_map
        )

    def save_buffer(self, session_key: str, buffer_id: str) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.save_buffer(
            self.base_dir,
            session_key,
            buffer_id,
            self.ca_client,
            repo=self._repo(buffer_id),
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
            repo=self._repo(buffer_id),
        )

    def reload_buffer(self, session_key: str, buffer_id: str) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.reload_buffer(
            self.base_dir,
            session_key,
            buffer_id,
            self.ca_client,
            self.formatter_registry,
            repo=self._repo(buffer_id),
        )

    def get_buffer_state(self, session_key: str, buffer_id: str) -> Any:
        from ai_editor.sessions import buffer_api

        return buffer_api.get_buffer_state(
            self.base_dir, session_key, buffer_id, self.ca_client, self.formatter_registry
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
        try:
            new_document = formatter.mutate_batch(document, operations)
        except Exception as exc:  # noqa: BLE001
            return OperationResult(success=False, message=str(exc))
        from ai_editor.sessions.mutation_api import execute_mutation

        return execute_mutation(
            self.base_dir,
            session_key,
            buffer_id,
            new_document,
            command_name="mutate_batch",
            params_summary=f"{len(operations)} ops",
            repo=self._repo(buffer_id),
        )

    def undo(self, session_key: str, buffer_id: str, steps: int = 1) -> Any:
        from ai_editor.sessions import history_api

        return history_api.undo(
            self.base_dir, session_key, buffer_id, self._repo(buffer_id), steps=steps
        )

    def redo(self, session_key: str, buffer_id: str, steps: int = 1) -> Any:
        from ai_editor.sessions import history_api

        return history_api.redo(
            self.base_dir, session_key, buffer_id, self._repo(buffer_id), steps=steps
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
            repo=self._repo(buffer_id),
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
            repo=self._repo(buffer_id),
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
            fmt = self.formatter_registry.get(formatter)
        elif buffer_id:
            raise ValueError("formatter required when buffer_id omitted in this stub")
        else:
            fmt = self.formatter_registry.get("text")
        return {"commands": fmt.list_commands()}
