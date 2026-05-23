"""CodeAnalysisClient — sync gateway for project file I/O via code-analysis-client.

All file access goes through the CA server JSON-RPC API and transfer protocol
(mcp-proxy-adapter JsonRpcClient), not direct disk or REST /commands/* stubs.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code_analysis_client import CodeAnalysisAsyncClient
from code_analysis_client.responses import unwrap_command_result


class _AsyncRunner:
    """Run coroutines on a dedicated background event loop."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="ca-client-loop", daemon=True
        )
        self._thread.start()

    def run(self, coro: Any) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def close(self) -> None:
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5.0)
        self._loop.close()


@dataclass
class CAClientConfig:
    """Connection configuration retained for compatibility."""

    host: str
    port: int
    protocol: str
    ssl_context: Any = None
    auth_token: str | None = None

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}"


class CodeAnalysisClient:
    """Sync façade over :class:`CodeAnalysisAsyncClient` and transfer helpers."""

    def __init__(
        self,
        async_client: CodeAnalysisAsyncClient,
        *,
        config: CAClientConfig | None = None,
    ) -> None:
        self._async = async_client
        self._fs = async_client.file_sessions
        self._runner = _AsyncRunner()
        self._config = config

    @classmethod
    def from_config(cls, ca_config: Any) -> CodeAnalysisClient:
        """Build a client from CodeAnalysisServerConfig or compatible mapping."""
        from ai_editor.config.config_section import CodeAnalysisServerConfig

        if not isinstance(ca_config, CodeAnalysisServerConfig):
            ca_config = CodeAnalysisServerConfig.from_dict(dict(ca_config))

        auth_token: str | None = None
        if ca_config.auth.use_token and ca_config.auth.token_env:
            auth_token = os.environ.get(ca_config.auth.token_env)

        async_client = CodeAnalysisAsyncClient.from_server_config(
            ca_config.to_server_config_dict(),
            check_hostname=ca_config.check_hostname,
            token=auth_token,
        )
        cfg = CAClientConfig(
            host=ca_config.host,
            port=ca_config.port,
            protocol=ca_config.protocol,
            auth_token=auth_token,
        )
        return cls(async_client, config=cfg)

    def _run(self, coro: Any) -> Any:
        return self._runner.run(coro)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        comment: str = "ai_editor",
        *,
        role_ids: list[str] | None = None,
    ) -> str:
        """Register a CA client session and return its session_id."""
        return self._run(self._fs.create_session(comment, role_ids=role_ids))

    def delete_session(self, session_id: str, *, force: bool = False) -> dict[str, Any]:
        """Delete a CA client session."""
        return self._run(self._fs.delete_session(session_id, force=force))

    def assert_session_exists(self, ca_session_id: str) -> None:
        """Verify the CA session is registered on the analysis server."""
        self._run(self._fs.assert_session_exists(ca_session_id))

    def create_subordinate_session(
        self,
        parent_session_id: str,
        comment: str,
        *,
        server_uuid: str | None = None,
    ) -> dict[str, Any]:
        """Register parent session on a subordinate server (subordinate_session_create)."""
        return self._run(
            self._fs.create_subordinate_session(
                parent_session_id,
                comment,
                server_uuid=server_uuid,
            )
        )

    def delete_subordinate_session(
        self,
        parent_session_id: str,
        server_uuid: str,
    ) -> dict[str, Any]:
        """Remove subordinate server link (subordinate_session_delete)."""
        return self._run(
            self._fs.delete_subordinate_session(
                parent_session_id,
                server_uuid,
            )
        )

    # ------------------------------------------------------------------
    # File content I/O
    # ------------------------------------------------------------------

    def resolve_file_id(self, project_id: str, relative_path: str) -> str:
        """Resolve indexed ``files.id`` from project_id and project-relative path."""
        norm = str(relative_path or "").strip().replace("\\", "/")
        if not norm:
            raise ValueError("relative_path is required")
        for row in self.list_project_files(project_id):
            rel = str(row.get("relative_path") or row.get("path") or "").replace(
                "\\", "/"
            )
            if rel == norm:
                fid = row.get("file_id") or row.get("id")
                if fid:
                    return str(fid)
        raise ValueError(f"file not indexed: {relative_path}")

    def download_content(
        self,
        project_id: str,
        file_path: str,
        readonly: bool = False,
        *,
        ca_session_id: str,
    ) -> tuple[bytes, str]:
        """Download file content via transfer protocol.

        When ``readonly`` is False, an advisory lock is acquired during download.
        The caller must not call :meth:`lock_file` again for the same open flow.

        Args:
            project_id: UUID of the project.
            file_path: Project-relative path to the file.
            readonly: If True, download without acquiring a lock.
            ca_session_id: Registered CA session id holding locks/transfers.

        Returns:
            Tuple of (content_bytes, file_id).
        """
        if not ca_session_id:
            raise ValueError("ca_session_id is required for download_content")

        file_id = self.resolve_file_id(project_id, file_path)

        async def _download() -> tuple[bytes, str]:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                dest = tmp.name
            try:
                begin, _receipt = await self._fs.download(
                    ca_session_id,
                    dest,
                    file_id,
                    lock=not readonly,
                )
                content = Path(dest).read_bytes()
                return content, str(begin["file_id"])
            finally:
                Path(dest).unlink(missing_ok=True)

        return self._run(_download())

    def upload_content(
        self,
        project_id: str,
        file_id: str | None,
        content: bytes,
        *,
        ca_session_id: str,
        file_path: str | None = None,
        unlock: bool = False,
    ) -> str:
        """Upload file content; optionally release the file lock on CA.

        Uses ``upload_new`` for new paths (``file_id`` is None) and ``upload`` for
        existing indexed files.

        Args:
            project_id: UUID of the project.
            file_id: UUID of the file on the CA server, or None for new files.
            content: Raw bytes to write.
            ca_session_id: Registered CA session id holding the lock.
            file_path: Project-relative path; required when file_id is None.
            unlock: When True, pass unlock_after_write=True to CA (release lock).

        Returns:
            CA ``files.id`` from the save payload.
        """
        from ai_editor.sessions.project_paths import normalize_project_relative_path

        if not ca_session_id:
            raise ValueError("ca_session_id is required for upload_content")

        fid = str(file_id or "").strip() or None
        norm_path: str | None = None
        if file_path:
            norm_path = normalize_project_relative_path(file_path)
        if fid is None and not norm_path:
            raise ValueError("file_path is required when file_id is None")

        filename = Path(norm_path).name if norm_path else "payload.bin"

        async def _upload() -> str:
            if fid is None:
                assert norm_path is not None
                return await self._fs.upload_new(
                    ca_session_id,
                    content,
                    project_id,
                    norm_path,
                    filename=filename,
                    unlock=unlock,
                )
            saved = await self._fs.upload(
                ca_session_id,
                content,
                fid,
                project_id=project_id or None,
                filename=filename,
                unlock=unlock,
            )
            return str(saved["file_id"])

        return self._run(_upload())

    # ------------------------------------------------------------------
    # Lock management
    # ------------------------------------------------------------------

    def lock_file(
        self,
        ca_session_id: str,
        project_id: str,
        file_id: str,
    ) -> None:
        """Acquire a cooperative file lock via session_open_file."""
        self._run(
            self._fs.lock_file(ca_session_id, project_id, file_id)
        )

    def unlock_file(
        self,
        ca_session_id: str,
        project_id: str,
        file_id: str,
    ) -> None:
        """Release a cooperative file lock via session_close_file."""
        self._run(
            self._fs.unlock_file(ca_session_id, project_id, file_id)
        )

    def list_file_locks(
        self,
        ca_session_id: str,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all file locks held under the given CA session."""
        _ = project_id
        payload = self._run(self._fs.list_file_locks(ca_session_id))
        locks = payload.get("locks", payload.get("file_locks", []))
        return locks if isinstance(locks, list) else []

    # ------------------------------------------------------------------
    # Project file listing
    # ------------------------------------------------------------------

    def list_project_files(self, project_id: str) -> list[dict[str, Any]]:
        """List all files in the project."""
        payload = self._run(
            self._async.call_validated(
                "list_project_files", {"project_id": project_id}
            )
        )
        data = unwrap_command_result(payload)
        files = data.get("files", [])
        return files if isinstance(files, list) else []

    # ------------------------------------------------------------------
    # Backup management
    # ------------------------------------------------------------------

    def list_backup_versions(
        self,
        project_id: str,
        file_path: str,
    ) -> list[dict[str, Any]]:
        """List available backup versions for a file."""
        payload = self._run(
            self._async.call_validated(
                "list_backup_versions",
                {"project_id": project_id, "file_path": file_path},
            )
        )
        data = unwrap_command_result(payload)
        versions = data.get("versions", [])
        return versions if isinstance(versions, list) else []

    def restore_backup_file(
        self,
        project_id: str,
        file_path: str,
        backup_uuid: str,
    ) -> None:
        """Restore a file from a backup version."""
        payload = self._run(
            self._async.call_validated(
                "restore_backup_file",
                {
                    "project_id": project_id,
                    "file_path": file_path,
                    "backup_uuid": backup_uuid,
                },
            )
        )
        unwrap_command_result(payload)

    def close(self) -> None:
        """Close the underlying async client and background loop."""
        try:
            self._run(self._async.close())
        finally:
            self._runner.close()

    def __enter__(self) -> CodeAnalysisClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
