"""CodeAnalysisClient — single gateway for all project file I/O via CA server API.

ai_editor never reads or writes project files directly from disk.
All file access goes through this client.
"""
from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass
class CAClientConfig:
    """Connection configuration for the CA server.

    Attributes:
        host: CA server hostname.
        port: CA server port.
        protocol: 'https' or 'mtls'.
        ssl_context: SSL context for mTLS; None for plain HTTPS+token.
        auth_token: Bearer token for HTTPS+token auth; None for mTLS.
    """

    host: str
    port: int
    protocol: str  # 'https' | 'mtls'
    ssl_context: ssl.SSLContext | None = None
    auth_token: str | None = None

    @property
    def base_url(self) -> str:
        """Return the base URL for the CA server."""
        return f"https://{self.host}:{self.port}"


class CodeAnalysisClient:
    """Single gateway for all project file I/O via the CA server API.

    ai_editor never reads or writes project files directly from disk.
    All file access goes through this client.

    Invariant: upload_content writes content only and never releases
    the file lock. Lock release is always a separate explicit unlock_file call.
    """

    def __init__(self, config: CAClientConfig) -> None:
        """Initialise the client with the given connection configuration.

        Args:
            config: CA server connection configuration.
        """
        self._config = config
        self._client = httpx.Client(
            base_url=config.base_url,
            verify=config.ssl_context or True,
            headers=(
                {"Authorization": f"Bearer {config.auth_token}"}
                if config.auth_token
                else {}
            ),
            timeout=60.0,
        )

    # ------------------------------------------------------------------
    # File content I/O
    # ------------------------------------------------------------------

    def download_content(
        self,
        project_id: str,
        file_path: str,
        readonly: bool = False,
    ) -> tuple[bytes, str | None]:
        """Download file content from the CA server.

        Transfer download with no lock side-effect. The caller is responsible
        for acquiring the lock separately via lock_file if a write is intended.

        Args:
            project_id: UUID of the project.
            file_path: Project-relative path to the file.
            readonly: True if the buffer will be opened read-only (advisory).

        Returns:
            Tuple of (content_bytes, file_id). file_id is None if the server
            does not return it.
        """
        resp = self._client.get(
            "/commands/download_file",
            params={"project_id": project_id, "file_path": file_path},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"].encode("utf-8"), data.get("file_id")

    def upload_content(
        self,
        project_id: str,
        file_id: str,
        content: bytes,
    ) -> None:
        """Upload file content to the CA server.

        Writes file content only. Never releases the file lock.
        Lock release requires a separate explicit unlock_file call.

        Args:
            project_id: UUID of the project.
            file_id: UUID of the file on the CA server.
            content: Raw bytes to write.
        """
        resp = self._client.post(
            "/commands/upload_file",
            json={
                "project_id": project_id,
                "file_id": file_id,
                "content": content.decode("utf-8"),
            },
        )
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Lock management
    # ------------------------------------------------------------------

    def lock_file(
        self,
        ca_session_id: str,
        project_id: str,
        file_id: str,
    ) -> None:
        """Acquire a cooperative file lock via session_open_file.

        Raises BUFFER_LOCKED error if the file is already held by another
        CA session. Idempotent if the same session already holds the lock.

        Args:
            ca_session_id: External CA session UUID.
            project_id: UUID of the project.
            file_id: UUID of the file.
        """
        resp = self._client.post(
            "/commands/session_open_file",
            json={
                "session_id": ca_session_id,
                "project_id": project_id,
                "file_id": file_id,
            },
        )
        resp.raise_for_status()

    def unlock_file(
        self,
        ca_session_id: str,
        project_id: str,
        file_id: str,
    ) -> None:
        """Release a cooperative file lock via session_close_file.

        Args:
            ca_session_id: External CA session UUID.
            project_id: UUID of the project.
            file_id: UUID of the file.
        """
        resp = self._client.post(
            "/commands/session_close_file",
            json={
                "session_id": ca_session_id,
                "project_id": project_id,
                "file_id": file_id,
            },
        )
        resp.raise_for_status()

    def list_file_locks(
        self,
        ca_session_id: str,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """List all file locks held under the given CA session.

        Used as a pre-check before acquiring a new lock to detect conflicts.

        Args:
            ca_session_id: External CA session UUID.
            project_id: UUID of the project.

        Returns:
            List of lock descriptor dicts from session_list_file_locks.
        """
        resp = self._client.get(
            "/commands/session_list_file_locks",
            params={"session_id": ca_session_id, "project_id": project_id},
        )
        resp.raise_for_status()
        return resp.json().get("locks", [])

    # ------------------------------------------------------------------
    # Project file listing
    # ------------------------------------------------------------------

    def list_project_files(self, project_id: str) -> list[dict[str, Any]]:
        """List all files in the project.

        Args:
            project_id: UUID of the project.

        Returns:
            List of file descriptor dicts.
        """
        resp = self._client.get(
            "/commands/list_project_files",
            params={"project_id": project_id},
        )
        resp.raise_for_status()
        return resp.json().get("files", [])

    # ------------------------------------------------------------------
    # Backup management
    # ------------------------------------------------------------------

    def list_backup_versions(
        self,
        project_id: str,
        file_path: str,
    ) -> list[dict[str, Any]]:
        """List available backup versions for a file.

        Args:
            project_id: UUID of the project.
            file_path: Project-relative path to the file.

        Returns:
            List of backup version dicts (backup_uuid, created_at, etc.).
        """
        resp = self._client.get(
            "/commands/list_backup_versions",
            params={"project_id": project_id, "file_path": file_path},
        )
        resp.raise_for_status()
        return resp.json().get("versions", [])

    def restore_backup_file(
        self,
        project_id: str,
        file_path: str,
        backup_uuid: str,
    ) -> None:
        """Restore a file from a backup version.

        Args:
            project_id: UUID of the project.
            file_path: Project-relative path to the file.
            backup_uuid: UUID of the backup version to restore.
        """

        resp = self._client.post(
            "/commands/restore_backup_file",
            json={
                "project_id": project_id,
                "file_path": file_path,
                "backup_uuid": backup_uuid,
            },
        )
        resp.raise_for_status()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> CodeAnalysisClient:
        """Return self for use as a context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close the client on context manager exit."""
        self.close()
