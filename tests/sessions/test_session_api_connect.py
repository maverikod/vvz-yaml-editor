"""Tests for session_api.connect."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ai_editor.contracts import ErrorCode
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.session_api import connect

EDITOR_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _ca_client() -> MagicMock:
    client = MagicMock(spec=CodeAnalysisClient)
    client.create_subordinate_session.return_value = {"server_uuid": EDITOR_UUID}
    return client


def _connect_config(ca_session_id: str) -> dict[str, str]:
    return {"ca_session_id": ca_session_id, "editor_server_uuid": EDITOR_UUID}


def test_connect_uses_ca_session_id_as_session_key(tmp_path) -> None:
    ca_client = _ca_client()
    ca_session_id = "parent-ca-id"

    descriptor = connect(
        tmp_path,
        ca_client,
        MagicMock(),
        _connect_config(ca_session_id),
        readonly=False,
    )

    assert descriptor.session_key == ca_session_id
    settings_path = tmp_path / ca_session_id / "ses_settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["session_key"] == ca_session_id
    assert settings["ca_session_id"] == ca_session_id
    assert settings["subordinate_server_uuid"] == EDITOR_UUID
    ca_client.create_subordinate_session.assert_called_once_with(
        ca_session_id,
        "ai_editor",
        server_uuid=EDITOR_UUID,
    )
    ca_client.create_session.assert_not_called()


def test_connect_reopens_existing_local_session(tmp_path) -> None:
    ca_client = _ca_client()
    ca_session_id = "parent-ca-id"
    cfg = _connect_config(ca_session_id)

    first = connect(tmp_path, ca_client, MagicMock(), cfg, readonly=False)
    ca_client.create_subordinate_session.reset_mock()
    second = connect(tmp_path, ca_client, MagicMock(), cfg, readonly=False)

    assert first.session_key == ca_session_id
    assert second.session_key == ca_session_id
    assert len(list(tmp_path.iterdir())) == 1
    ca_client.create_subordinate_session.assert_not_called()


def test_connect_rolls_back_local_dir_when_subordinate_fails(tmp_path) -> None:
    ca_client = _ca_client()
    ca_client.create_subordinate_session.side_effect = RuntimeError("link failed")
    ca_session_id = "parent-ca-id"

    with pytest.raises(ValueError, match=ErrorCode.SESSION_REGISTRATION_FAILED.value):
        connect(
            tmp_path,
            ca_client,
            MagicMock(),
            _connect_config(ca_session_id),
            readonly=False,
        )

    assert list(tmp_path.iterdir()) == []
