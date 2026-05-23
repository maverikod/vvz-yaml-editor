"""Tests for CA session identity and subordinate link helpers."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from code_analysis_client import SessionNotFoundError

from ai_editor.contracts import ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.ca_session import (
    EDITOR_SUBORDINATE_COMMENT,
    register_editor_subordinate,
    release_editor_subordinate,
    verify_ca_session,
    work_ca_session_id,
)

EDITOR_UUID = "550e8400-e29b-41d4-a716-446655440000"


def test_work_ca_session_id_equals_ca_session_id() -> None:
    settings = {"session_key": "abc-id", "ca_session_id": "abc-id"}
    assert work_ca_session_id(settings) == "abc-id"


def _ca_client() -> MagicMock:
    return MagicMock(spec=CodeAnalysisClient)


def test_verify_ca_session_rejects_unknown() -> None:
    ca_client = _ca_client()
    ca_client.assert_session_exists.side_effect = SessionNotFoundError(
        "SESSION_NOT_FOUND", field="session_id", details={}
    )
    with pytest.raises(ValueError, match=ErrorCode.SESSION_NOT_FOUND.value):
        verify_ca_session(ca_client, "parent-id")


def test_register_editor_subordinate_calls_ca_api() -> None:
    ca_client = _ca_client()
    ca_client.create_subordinate_session.return_value = {"server_uuid": EDITOR_UUID}

    linked = register_editor_subordinate(
        ca_client,
        ca_session_id="parent-id",
        editor_server_uuid=EDITOR_UUID,
    )

    assert linked == EDITOR_UUID
    ca_client.create_subordinate_session.assert_called_once_with(
        "parent-id",
        EDITOR_SUBORDINATE_COMMENT,
        server_uuid=EDITOR_UUID,
    )


def test_release_editor_subordinate_deletes_link() -> None:
    ca_client = _ca_client()
    settings = {
        "ca_session_id": "parent-id",
        "subordinate_server_uuid": EDITOR_UUID,
    }

    release_editor_subordinate(ca_client, settings)

    ca_client.delete_subordinate_session.assert_called_once_with(
        "parent-id",
        EDITOR_UUID,
    )
    ca_client.delete_session.assert_not_called()


def test_release_editor_subordinate_noop_without_uuid() -> None:
    ca_client = _ca_client()
    release_editor_subordinate(ca_client, {"ca_session_id": "parent-id"})
    ca_client.delete_subordinate_session.assert_not_called()
