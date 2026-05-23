"""Tests for session_connect execute error handling."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from ai_editor.commands.session_connect_command import SessionConnectCommand
from ai_editor.contracts import ErrorCode


def test_session_connect_execute_returns_error_on_registration_failure() -> None:
    cmd = SessionConnectCommand()
    manager = MagicMock()
    manager.connect.side_effect = ValueError(ErrorCode.SESSION_REGISTRATION_FAILED.value)

    with patch("ai_editor.api.connect", side_effect=manager.connect):
        result = asyncio.run(
            cmd.execute(
                ca_session_id="parent-ca-id",
                readonly=False,
            )
        )

    assert result.success is False
    assert result.data["error_code"] == ErrorCode.SESSION_REGISTRATION_FAILED.value
    assert result.error == ErrorCode.SESSION_REGISTRATION_FAILED.value
