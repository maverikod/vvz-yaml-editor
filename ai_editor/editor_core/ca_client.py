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
from code_analysis_client.config import adapter_settings_from_server_config
from code_analysis_client.exceptions import ClientValidationError


def _unwrap(data: dict[str, Any]) -> dict[str, Any]:
    """Extract inner payload from a CA command response."""
    if data.get("success"):
        inner = data.get("data")
        if isinstance(inner, dict):
            if inner.get("success") is True and isinstance(inner.get("data"), dict):
                return inner["data"]
            return inner
        return data
    code_raw = data.get("code")
    message = data.get("message")
    err = data.get("error")
    if code_raw is None and isinstance(err, dict):
        code_raw = err.get("code")
        if message is None:
            message = err.get("message")
    elif code_raw is None and isinstance(err, str):
        code_raw = err
    raise ClientValidationError(
        str(message or data),
        field="command",
        details=data,
    )


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

        server_cfg: dict[str, Any] = {
            "server": {
                "host": ca_config.host,
                "port": ca_config.port,
                "protocol": ca_config.protocol,
            }
        }
        if ca_config.ssl:
            server_cfg["client"] = {"ssl": ca_config.ssl}

        adapter_settings = adapter_settings_from_server_config(server_cfg)
        async_client = CodeAnalysisAsyncClient.from_adapter_settings(
            adapter_settings,
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

    # ------------------------------------------------------------------
    # File content I/O
    # ------------------------------------------------------------------

    def download_content(
        self,
        project_id: str,
        file_path: str,
        readonly: bool = False,
        *,
        ca_session_id: str,
    ) -> tuple[bytes, str | None]:
        """Download file content via transfer protocol.

        When ``readonly`` is False, an advisory lock is acquired during download
        (``lock_mode=full``). The caller must not call :meth:`lock_file` again
        for the same open flow.

        Args:
            project_id: UUID of the project.
            file_path: Project-relative path to the file.
            readonly: If True, download without acquiring a lock.
            ca_session_id: Registered CA session id (from :meth:`create_session`).

        Returns:
            Tuple of (content_bytes, file_id). file_id may be None if the server
            omits it; resolve via :meth:`list_project_files` when needed.
        """
        if not ca_session_id:
            raise ValueError("ca_session_id is required for download_content")

        async def _download() -> tuple[bytes, str | None]:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                dest = tmp.name
            try:
                begin, _receipt = await self._fs.download_file_locked(
                    ca_session_id,
                    dest,
                    project_id=project_id,
                    file_path=file_path,
                    lock_mode="none" if readonly else "full",
                )
                content = Path(dest).read_bytes()
                file_id = begin.get("file_id")
                if file_id is not None:
                    file_id = str(file_id)
                return content, file_id
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
    ) -> None:
        """Upload file content without releasing the file lock.

        Args:
            project_id: UUID of the project.
            file_id: UUID of the file on the CA server, or None when unknown.
            content: Raw bytes to write.
            ca_session_id: Registered CA session id holding the lock.
            file_path: Project-relative path; required when file_id is None.
        """
        if not ca_session_id:
            raise ValueError("ca_session_id is required for upload_content")
        if file_id is None and not file_path:
            raise ValueError("file_path is required when file_id is None")

        filename = Path(file_path).name if file_path else "payload.bin"

        async def _upload() -> None:
            receipt = await self._fs.upload_bytes(
                content, filename=filename, compression="identity"
            )
            if not getattr(receipt, "completed", False):
                raise ClientValidationError(
                    "upload did not complete",
                    field="transfer_id",
                    details={"receipt": repr(receipt)},
                )
            await self._fs.save_upload_and_unlock(
                ca_session_id,
                str(receipt.transfer_id),
                project_id=project_id,
                file_id=file_id if file_id is not None else None,
                file_path=file_path if file_id is None else None,
                unlock_after_write=False,
            )

        self._run(_upload())

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
            self._async.call("list_project_files", {"project_id": project_id})
        )
        data = _unwrap(payload)
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
            self._async.call(
                "list_backup_versions",
                {"project_id": project_id, "file_path": file_path},
            )
        )
        data = _unwrap(payload)
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
            self._async.call(
                "restore_backup_file",
                {
                    "project_id": project_id,
                    "file_path": file_path,
                    "backup_uuid": backup_uuid,
                },
            )
        )
        _unwrap(payload)

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
