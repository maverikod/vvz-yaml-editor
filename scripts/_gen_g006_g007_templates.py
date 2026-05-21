"""Code templates for _gen_g006_g007_as.py — not imported at runtime except by generator."""
from __future__ import annotations

import textwrap

SESSION_MANAGER_PY = textwrap.dedent(
    '''\
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
    from ai_editor.sessions import buffer_api, clipboard, history_api, session_api


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
            return session_api.connect(self.base_dir, readonly=readonly)

        def reconnect(self, session_key: str) -> Any:
            return session_api.reconnect(self.base_dir, session_key)

        def close_session(self, session_key: str, force: bool = False) -> Any:
            return session_api.close_session(self.base_dir, session_key, force=force)

        def session_status(self, session_key: str) -> Any:
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
            return buffer_api.close_buffer(
                self.base_dir, session_key, buffer_id, force=force, repo_map=self.repo_map
            )

        def save_buffer(self, session_key: str, buffer_id: str) -> Any:
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
            return buffer_api.reload_buffer(
                self.base_dir,
                session_key,
                buffer_id,
                self.ca_client,
                self.formatter_registry,
                repo=self._repo(buffer_id),
            )

        def get_buffer_state(self, session_key: str, buffer_id: str) -> Any:
            return buffer_api.get_buffer_state(
                self.base_dir, session_key, buffer_id, self.ca_client, self.formatter_registry
            )

        def write_all(self, session_key: str, force: bool = False) -> Any:
            return buffer_api.write_all(
                self.base_dir,
                session_key,
                self.ca_client,
                force=force,
                repo_map=self.repo_map,
            )

        def validate_buffer(self, session_key: str, buffer_id: str) -> Any:
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
            return history_api.undo(
                self.base_dir, session_key, buffer_id, self._repo(buffer_id), steps=steps
            )

        def redo(self, session_key: str, buffer_id: str, steps: int = 1) -> Any:
            return history_api.redo(
                self.base_dir, session_key, buffer_id, self._repo(buffer_id), steps=steps
            )

        def copy_fragment(self, session_key: str, buffer_id: str, address: Any) -> Any:
            return clipboard.copy_to_clipboard(
                self.base_dir, session_key, buffer_id, address, self.formatter_registry
            )

        def cut_fragment(self, session_key: str, buffer_id: str, address: Any) -> Any:
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
    '''
).strip()

API_INIT_PY = textwrap.dedent(
    '''\
    """Singleton initialisation for ai_editor api facade."""
    from __future__ import annotations

    from ai_editor.config.config_section import AiEditorConfig, CodeAnalysisServerConfig
    from ai_editor.editor_core.ca_client import CodeAnalysisClient
    from ai_editor.editor_core.formatter_registry import FormatterRegistry
    from ai_editor.session_manager import SessionManager
    from ai_editor.sessions.startup_sweep import startup_sweep

    _ca_client: CodeAnalysisClient | None = None
    _session_manager: SessionManager | None = None


    def init_api(
        config: AiEditorConfig,
        ca_config: CodeAnalysisServerConfig,
        formatter_registry: FormatterRegistry,
    ) -> None:
        """Build CA client and SessionManager; run startup_sweep once."""
        global _ca_client, _session_manager
        _ca_client = CodeAnalysisClient.from_config(ca_config)
        base_dir = config.sessions.base_dir
        _session_manager = SessionManager(base_dir, _ca_client, formatter_registry)
        startup_sweep(base_dir, _ca_client)


    def get_ca_client() -> CodeAnalysisClient:
        if _ca_client is None:
            raise RuntimeError("init_api() must be called before using api")
        return _ca_client


    def get_session_manager() -> SessionManager:
        if _session_manager is None:
            raise RuntimeError("init_api() must be called before using api")
        return _session_manager
    '''
).strip()

API_PY = textwrap.dedent(
    '''\
    """Thin synchronous facade over SessionManager — sole import for commands and CLI."""
    from __future__ import annotations

    from typing import Any

    from ai_editor.api_init import get_session_manager


    def connect(readonly: bool = False) -> Any:
        return get_session_manager().connect(readonly=readonly)

    def reconnect(session_key: str) -> Any:
        return get_session_manager().reconnect(session_key)

    def close_session(session_key: str, force: bool = False) -> Any:
        return get_session_manager().close_session(session_key, force=force)

    def session_status(session_key: str) -> Any:
        return get_session_manager().session_status(session_key)

    def open_buffer(
        session_key: str,
        project_id: str,
        file_path: str,
        formatter: str = "auto",
        open_as_text: bool = False,
        readonly: bool = False,
    ) -> Any:
        return get_session_manager().open_buffer(
            session_key, project_id, file_path, formatter, open_as_text, readonly
        )

    def new_buffer(
        session_key: str,
        formatter_name: str = "auto",
        initial_content: str = "",
        display_name: str | None = None,
    ) -> Any:
        return get_session_manager().new_buffer(
            session_key, formatter_name, initial_content, display_name
        )

    def close_buffer(
        session_key: str, buffer_id: str, force: bool = False, dry_run: bool = False
    ) -> Any:
        if dry_run:
            return {"success": True, "dry_run": True}
        return get_session_manager().close_buffer(session_key, buffer_id, force=force)

    def get_buffer_state(session_key: str, buffer_id: str) -> Any:
        return get_session_manager().get_buffer_state(session_key, buffer_id)

    def save_buffer(session_key: str, buffer_id: str, dry_run: bool = False) -> Any:
        if dry_run:
            return {"success": True, "dry_run": True}
        return get_session_manager().save_buffer(session_key, buffer_id)

    def save_as_buffer(
        session_key: str,
        buffer_id: str,
        new_relative_path: str,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> Any:
        if dry_run:
            return {"success": True, "dry_run": True}
        return get_session_manager().save_as_buffer(
            session_key, buffer_id, new_relative_path, overwrite=overwrite
        )

    def reload_buffer(session_key: str, buffer_id: str) -> Any:
        return get_session_manager().reload_buffer(session_key, buffer_id)

    def write_all(session_key: str, force: bool = False, dry_run: bool = False) -> Any:
        if dry_run:
            return {"success": True, "dry_run": True}
        return get_session_manager().write_all(session_key, force=force)

    def validate_buffer(session_key: str, buffer_id: str) -> Any:
        return get_session_manager().validate_buffer(session_key, buffer_id)

    def validate_file(
        session_key: str,
        file_path: str | None = None,
        buffer_id: str | None = None,
        project_id: str | None = None,
        formatter: str = "auto",
        schema: dict[str, Any] | None = None,
    ) -> Any:
        return get_session_manager().validate_file(
            session_key, file_path, buffer_id, project_id, formatter, schema
        )

    def mutate_batch(
        session_key: str, buffer_id: str, operations: list[dict[str, Any]], dry_run: bool = False
    ) -> Any:
        if dry_run:
            return {"success": True, "dry_run": True, "operations": len(operations)}
        return get_session_manager().mutate_batch(session_key, buffer_id, operations)

    def undo(session_key: str, buffer_id: str, steps: int = 1) -> Any:
        return get_session_manager().undo(session_key, buffer_id, steps=steps)

    def redo(session_key: str, buffer_id: str, steps: int = 1) -> Any:
        return get_session_manager().redo(session_key, buffer_id, steps=steps)

    def copy(session_key: str, source: dict[str, Any]) -> Any:
        return get_session_manager().copy_fragment(
            session_key, source["buffer_id"], source["address"]
        )

    def cut(session_key: str, source: dict[str, Any], dry_run: bool = False) -> Any:
        if dry_run:
            return {"success": True, "dry_run": True}
        return get_session_manager().cut_fragment(
            session_key, source["buffer_id"], source["address"]
        )

    def paste(
        session_key: str, target: dict[str, Any], mode: str, dry_run: bool = False
    ) -> Any:
        if dry_run:
            return {"success": True, "dry_run": True}
        return get_session_manager().paste_fragment(
            session_key, target["buffer_id"], target["address"], mode
        )

    def find(
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> Any:
        return get_session_manager().find(session_key, buffer_id, query, scope)

    def find_one(
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> Any:
        return get_session_manager().find_one(session_key, buffer_id, query, scope)

    def list_units(session_key: str, buffer_id: str, scope: str | None = None) -> Any:
        return get_session_manager().list_units(session_key, buffer_id, scope)

    def formatter_commands(buffer_id: str | None = None, formatter: str | None = None) -> Any:
        return get_session_manager().formatter_commands(buffer_id, formatter)
    '''
).strip()

CLI_PY = textwrap.dedent(
    '''\
    """CLI diagnostic wrapper over ai_editor.api — JSON stdout, errors stderr."""
    from __future__ import annotations

    import argparse
    import json
    import os
    import sys
    from typing import Any

    from ai_editor.api_init import init_api
    from ai_editor.config.config_section import AiEditorConfig, CodeAnalysisServerConfig
    from ai_editor.config.config_validator import AiEditorConfigValidator
    from ai_editor.editor_core.formatter_registry import FormatterRegistry
    from ai_editor import api


    def _load_config(config_path: str) -> None:
        from mcp_proxy_adapter.core.config.simple_config import SimpleConfig

        model = SimpleConfig(config_path).load()
        errors = AiEditorConfigValidator().validate(model.raw)
        if errors:
            print(json.dumps({"errors": errors}), file=sys.stderr)
            sys.exit(1)
        ai_cfg = AiEditorConfig.from_config_json(model.raw)
        ca_cfg = CodeAnalysisServerConfig.from_config_json(model.raw)
        init_api(ai_cfg, ca_cfg, FormatterRegistry.get_instance())


    def _out(data: Any) -> None:
        print(json.dumps(data, default=str))


    def main(argv: list[str] | None = None) -> None:
        parser = argparse.ArgumentParser(prog="ai-editor")
        parser.add_argument(
            "--config",
            default=os.environ.get("AI_EDITOR_CONFIG", "config.json"),
            help="Path to config.json (or AI_EDITOR_CONFIG env var).",
        )
        sub = parser.add_subparsers(dest="command", required=True)

        p = sub.add_parser("connect")
        p.add_argument("--readonly", action="store_true")

        p = sub.add_parser("disconnect")
        p.add_argument("--session-key", required=True)
        p.add_argument("--force", action="store_true")

        p = sub.add_parser("open")
        p.add_argument("--session-key", required=True)
        p.add_argument("--project-id", required=True)
        p.add_argument("--file-path", required=True)
        p.add_argument("--formatter", default="auto")

        p = sub.add_parser("find")
        p.add_argument("--session-key", required=True)
        p.add_argument("--buffer-id", required=True)
        p.add_argument("--query", required=True, help="JSON query object")

        p = sub.add_parser("copy")
        p.add_argument("--session-key", required=True)
        p.add_argument("--buffer-id", required=True)
        p.add_argument("--address", required=True)

        p = sub.add_parser("paste")
        p.add_argument("--session-key", required=True)
        p.add_argument("--buffer-id", required=True)
        p.add_argument("--address", required=True)
        p.add_argument("--mode", default="replace")

        p = sub.add_parser("save")
        p.add_argument("--session-key", required=True)
        p.add_argument("--buffer-id", required=True)

        p = sub.add_parser("undo")
        p.add_argument("--session-key", required=True)
        p.add_argument("--buffer-id", required=True)
        p.add_argument("--steps", type=int, default=1)

        p = sub.add_parser("redo")
        p.add_argument("--session-key", required=True)
        p.add_argument("--buffer-id", required=True)
        p.add_argument("--steps", type=int, default=1)

        p = sub.add_parser("validate-file")
        p.add_argument("--session-key", required=True)
        p.add_argument("--file-path", required=True)
        p.add_argument("--project-id", required=True)

        args = parser.parse_args(argv)
        _load_config(args.config)

        try:
            if args.command == "connect":
                _out(api.connect(readonly=args.readonly))
            elif args.command == "disconnect":
                _out(api.close_session(args.session_key, force=args.force))
            elif args.command == "open":
                _out(
                    api.open_buffer(
                        args.session_key,
                        args.project_id,
                        args.file_path,
                        formatter=args.formatter,
                    )
                )
            elif args.command == "find":
                _out(
                    api.find(
                        args.session_key,
                        args.buffer_id,
                        json.loads(args.query),
                    )
                )
            elif args.command == "copy":
                _out(
                    api.copy(
                        args.session_key,
                        {"buffer_id": args.buffer_id, "address": args.address},
                    )
                )
            elif args.command == "paste":
                _out(
                    api.paste(
                        args.session_key,
                        {"buffer_id": args.buffer_id, "address": args.address},
                        args.mode,
                    )
                )
            elif args.command == "save":
                _out(api.save_buffer(args.session_key, args.buffer_id))
            elif args.command == "undo":
                _out(api.undo(args.session_key, args.buffer_id, steps=args.steps))
            elif args.command == "redo":
                _out(api.redo(args.session_key, args.buffer_id, steps=args.steps))
            elif args.command == "validate-file":
                _out(
                    api.validate_file(
                        args.session_key,
                        file_path=args.file_path,
                        project_id=args.project_id,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            print(str(exc), file=sys.stderr)
            sys.exit(1)


    if __name__ == "__main__":
        main()
    '''
).strip()

MAIN_PY = textwrap.dedent(
    '''\
    """ai_editor MCP server entry — six-step startup sequence."""
    from __future__ import annotations

    import logging
    import os
    import sys

    from mcp_proxy_adapter.core.config.simple_config import SimpleConfig
    from mcp_proxy_adapter.core.server_runner import UnifiedServerRunner
    from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook
    from mcp_proxy_adapter.web.create_app import create_app

    from ai_editor.api_init import init_api
    from ai_editor.config.config_section import AiEditorConfig, CodeAnalysisServerConfig
    from ai_editor.config.config_validator import AiEditorConfigValidator
    from ai_editor.hooks_register import formatter_registry, register_ai_editor_commands

    logger = logging.getLogger(__name__)


    def main(config_path: str | None = None) -> None:
        """Run six-step startup: load, validate, init_api, create_app, register commands, serve."""
        config_path = config_path or os.environ.get("AI_EDITOR_CONFIG", "config.json")

        # (1) Load config via adapter SimpleConfig
        model = SimpleConfig(config_path).load()

        # (2) Validate before any ai_editor objects are built
        errors = AiEditorConfigValidator().validate(model.raw)
        if errors:
            for err in errors:
                logger.error("config validation: %s", err)
            sys.exit(1)

        # (3) Build ai_editor singletons and run startup_sweep
        ai_cfg = AiEditorConfig.from_config_json(model.raw)
        ca_cfg = CodeAnalysisServerConfig.from_config_json(model.raw)
        init_api(ai_cfg, ca_cfg, formatter_registry)

        # (4) Adapter creates ASGI app (proxy registration per config auto_on_startup)
        app = create_app(app_config=model.raw, config_path=config_path)

        # (5) Register EditorCommand subclasses
        register_custom_commands_hook(register_ai_editor_commands)

        # (6) Start server (proxy unreachable still allows server start per config)
        runner = UnifiedServerRunner()
        runner.run_server(app, model.raw.get("server", {}))


    if __name__ == "__main__":
        main()
    '''
).strip()

AIEDMGR_PY = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    """Service manager for ai_editor — start/stop/status/restart/generate-config."""
    from __future__ import annotations

    import argparse
    import os
    import signal
    import subprocess
    import sys
    import time
    from pathlib import Path

    from mcp_proxy_adapter.core.config.simple_config import SimpleConfig

    from ai_editor.config.config_generator import AiEditorConfigGenerator, ConfigGenerationError
    from ai_editor.config.config_validator import AiEditorConfigValidator

    DEFAULT_PID = "ai_editor.pid"
    DEFAULT_LOG = "logs/ai_editor.log"


    def _config_path(args: argparse.Namespace) -> str:
        return args.config or os.environ.get("AI_EDITOR_CONFIG", "config.json")


    def _read_pid(pid_file: Path) -> int | None:
        if not pid_file.exists():
            return None
        try:
            return int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            return None


    def cmd_start(args: argparse.Namespace) -> None:
        config_path = _config_path(args)
        model = SimpleConfig(config_path).load()
        errors = AiEditorConfigValidator().validate(model.raw)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            sys.exit(1)
        pid_file = Path(args.pid_file)
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(log_path, "a", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-m", "ai_editor.main", "--config", config_path],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        time.sleep(2)
        if proc.poll() is not None:
            print("ai_editor failed to start; see log", file=sys.stderr)
            sys.exit(1)
        print(f"started pid={proc.pid}")


    def cmd_stop(args: argparse.Namespace) -> None:
        pid_file = Path(args.pid_file)
        pid = _read_pid(pid_file)
        if pid is None:
            print("not running")
            return
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            try:
                os.kill(pid, 0)
            except OSError:
                pid_file.unlink(missing_ok=True)
                print("stopped")
                return
            time.sleep(1)
        os.kill(pid, signal.SIGKILL)
        pid_file.unlink(missing_ok=True)
        print("killed")


    def cmd_status(args: argparse.Namespace) -> None:
        pid = _read_pid(Path(args.pid_file))
        if pid is None:
            print("stopped")
            sys.exit(1)
        try:
            os.kill(pid, 0)
        except OSError:
            print("stopped (stale pid file)")
            sys.exit(1)
        print(f"running pid={pid}")


    def cmd_restart(args: argparse.Namespace) -> None:
        cmd_stop(args)
        cmd_start(args)


    def cmd_generate_config(args: argparse.Namespace) -> None:
        gen = AiEditorConfigGenerator()
        try:
            gen.generate(args.protocol, args.out_path)
        except ConfigGenerationError as exc:
            for e in exc.errors:
                print(e, file=sys.stderr)
            sys.exit(1)
        print(f"wrote {args.out_path}")


    def main() -> None:
        parser = argparse.ArgumentParser(prog="aiedmgr")
        parser.add_argument("--config", default=None)
        parser.add_argument("--pid-file", default=DEFAULT_PID)
        parser.add_argument("--log-file", default=DEFAULT_LOG)
        sub = parser.add_subparsers(dest="command", required=True)
        sub.add_parser("start")
        sub.add_parser("stop")
        sub.add_parser("status")
        sub.add_parser("restart")
        p = sub.add_parser("generate-config")
        p.add_argument("protocol", choices=["https", "mtls"])
        p.add_argument("out_path")
        args = parser.parse_args()
        {
            "start": cmd_start,
            "stop": cmd_stop,
            "status": cmd_status,
            "restart": cmd_restart,
            "generate-config": cmd_generate_config,
        }[args.command](args)


    if __name__ == "__main__":
        main()
    '''
).strip()

TEST_CONFIG_INTEGRATION_PY = textwrap.dedent(
    '''\
    """G-007/T-002 — AiEditorConfig integration with main.py startup."""
    from __future__ import annotations

    import inspect

    import pytest

    from ai_editor.config.config_section import AiEditorConfig
    from ai_editor.config.config_validator import AiEditorConfigValidator


    def test_ai_editor_config_importable() -> None:
        cfg = AiEditorConfig.from_dict({})
        assert cfg.formatter.small_file_threshold == "50kb"
        assert cfg.formatter.small_file_formatter == "text"
        assert cfg.sessions.base_dir == "/tmp/ai_editor_sessions"


    def test_from_config_json_reads_ai_editor_section() -> None:
        raw = {"ai_editor": {"formatter": {"small_file_threshold": "2kb"}}}
        cfg = AiEditorConfig.from_config_json(raw)
        assert cfg.formatter.small_file_threshold == "2kb"


    def test_validator_returns_list() -> None:
        errors = AiEditorConfigValidator().validate({})
        assert isinstance(errors, list)


    def test_main_validates_before_from_config_json(monkeypatch: pytest.MonkeyPatch) -> None:
        import ai_editor.main as main_mod

        src = inspect.getsource(main_mod.main)
        v_idx = src.index("AiEditorConfigValidator")
        f_idx = src.index("AiEditorConfig.from_config_json")
        assert v_idx < f_idx, "validator must run before from_config_json in main.py"
    '''
).strip()

TEST_GENERATOR_INTEGRATION_PY = textwrap.dedent(
    '''\
    """G-007/T-003 — AiEditorConfigGenerator round-trip integration."""
    from __future__ import annotations

    import json
    from pathlib import Path

    import pytest

    from ai_editor.config.config_generator import AiEditorConfigGenerator, ConfigGenerationError
    from ai_editor.config.config_section import AiEditorConfig
    from ai_editor.config.config_validator import AiEditorConfigValidator


    def test_generate_and_validate(tmp_path: Path) -> None:
        out = tmp_path / "config.json"
        gen = AiEditorConfigGenerator()
        gen.generate("https", str(out))
        assert not (tmp_path / "config.json.tmp").exists()
        raw = json.loads(out.read_text(encoding="utf-8"))
        errors = AiEditorConfigValidator().validate(raw)
        assert errors == [] or all("ai_editor" not in e for e in errors)
        cfg = AiEditorConfig.from_config_json(raw)
        assert cfg.formatter.small_file_formatter


    def test_invalid_kwargs_raises_and_no_tmp(tmp_path: Path) -> None:
        gen = AiEditorConfigGenerator()
        out = tmp_path / "bad.json"
        with pytest.raises(ConfigGenerationError):
            gen.generate("https", str(out), small_file_threshold="1g")
        assert not (tmp_path / "bad.json.tmp").exists()
    '''
).strip()
