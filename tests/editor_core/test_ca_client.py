"""Tests for CodeAnalysisClient wrappers over code-analysis-client 1.0.6."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_editor.editor_core.ca_client import CodeAnalysisClient


@pytest.fixture
def ca_client() -> CodeAnalysisClient:
    async_client = MagicMock()
    fs = MagicMock()
    async_client.file_sessions = fs
    client = CodeAnalysisClient(async_client)
    client._run = lambda coro: asyncio.run(coro)  # noqa: SLF001
    return client


def test_resolve_file_id_matches_relative_path(ca_client: CodeAnalysisClient) -> None:
    ca_client.list_project_files = MagicMock(
        return_value=[
            {
                "relative_path": "src/main.py",
                "file_id": "fid-1",
            }
        ]
    )
    assert ca_client.resolve_file_id("proj", "src/main.py") == "fid-1"


def test_upload_content_uses_upload_new_for_new_files(
    ca_client: CodeAnalysisClient,
) -> None:
    fs = ca_client._fs  # noqa: SLF001
    fs.upload_new = AsyncMock(return_value="new-fid")

    file_id = ca_client.upload_content(
        "proj",
        None,
        b"hello",
        ca_session_id="sess",
        file_path="tmp/new.txt",
    )

    assert file_id == "new-fid"
    fs.upload_new.assert_awaited_once()
    fs.upload.assert_not_called()


def test_upload_content_uses_upload_for_existing_files(
    ca_client: CodeAnalysisClient,
) -> None:
    fs = ca_client._fs  # noqa: SLF001
    fs.upload = AsyncMock(return_value={"file_id": "existing-fid"})

    file_id = ca_client.upload_content(
        "proj",
        "existing-fid",
        b"hello",
        ca_session_id="sess",
        file_path="tmp/existing.txt",
    )

    assert file_id == "existing-fid"
    fs.upload.assert_awaited_once()
    fs.upload_new.assert_not_called()


def test_upload_content_uses_upload_when_file_id_without_path(
    ca_client: CodeAnalysisClient,
) -> None:
    fs = ca_client._fs  # noqa: SLF001
    fs.upload = AsyncMock(return_value={"file_id": "existing-fid"})

    file_id = ca_client.upload_content(
        "proj",
        "existing-fid",
        b"hello",
        ca_session_id="sess",
    )

    assert file_id == "existing-fid"
    fs.upload.assert_awaited_once()
    fs.upload_bytes.assert_not_called()


def test_download_content_uses_download_by_file_id(
    ca_client: CodeAnalysisClient,
    tmp_path,
) -> None:
    ca_client.resolve_file_id = MagicMock(return_value="fid-1")
    fs = ca_client._fs  # noqa: SLF001

    async def _download(session_id, destination, file_id, *, lock=True):
        Path = __import__("pathlib").Path
        Path(destination).write_bytes(b"payload")
        return {"file_id": "fid-1"}, object()

    fs.download = _download

    content, file_id = ca_client.download_content(
        "proj",
        "src/main.py",
        readonly=False,
        ca_session_id="sess",
    )

    assert content == b"payload"
    assert file_id == "fid-1"
