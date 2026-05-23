"""Extended metadata for session_close_invalid command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    build_metadata,
    dry_run_param,
    error_block,
    example_session_key,
    force_param,
    session_key_param,
)


def get_session_close_invalid_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for session_close_invalid."""
    sk = example_session_key()
    return build_metadata(
        cls,
        detailed_description=(
            "Close one editor session that exists locally but is no longer registered "
            "on the Code Analysis server (dead or missing ca_session_id). session_key "
            "is required and must refer to an existing local session directory. Unlike "
            "session_close, this command does not require a live CA session and is "
            "intended for recovery after external session_delete on CA or CA restarts.\n\n"
            "Invalid session definition: local session directory with ses_settings.json "
            "exists, and ca_session_id is empty or absent from CA client_sessions.\n\n"
            "mode=release_ca: best-effort unlock of recorded file locks and "
            "session_delete(force=true) on CA using the stored ca_session_id, then "
            "remove the local session directory.\n\n"
            "mode=local_only: remove the local session directory only; no CA RPC calls."
        ),
        parameters={
            "session_key": {
                **session_key_param(required=True),
                "notes": (
                    "Required. Must be an existing local session_key from session_connect. "
                    "The command fails when the session is still registered on CA "
                    "(use session_close instead)."
                ),
            },
            "mode": {
                "type": "string",
                "description": (
                    "release_ca sends stored ca_session_id to CA before local cleanup; "
                    "local_only closes locally only."
                ),
                "required": False,
                "default": "local_only",
                "enum": ["release_ca", "local_only"],
                "examples": ["release_ca"],
            },
            "force": force_param(
                description=(
                    "When true, discard unsaved or unsent buffers while closing "
                    "invalid sessions."
                ),
            ),
            "dry_run": dry_run_param(),
        },
        return_value={
            "success": {
                "description": "True when every targeted session closed or was skipped cleanly.",
                "data": {
                    "success": "Overall success flag.",
                    "message": "Summary text.",
                    "closed_count": "Number of sessions removed.",
                    "skipped_count": "Number of sessions skipped (still valid on CA or missing locally).",
                    "results": (
                        "Per-session list with session_key, ca_session_id, closed, skipped, "
                        "skip_reason, ca_notified, message."
                    ),
                },
                "example": {
                    "success": True,
                    "message": "closed 1 invalid session(s)",
                    "closed_count": 1,
                    "skipped_count": 0,
                    "results": [
                        {
                            "session_key": sk,
                            "ca_session_id": "3b82630d-55b2-4fd2-867f-6b4b2d580fbf",
                            "closed": True,
                            "skipped": False,
                            "skip_reason": "",
                            "ca_notified": True,
                            "message": "session closed",
                        }
                    ],
                },
            },
            "error": {
                "description": "One or more sessions failed to close (unsaved buffers without force).",
                "code": "ErrorCode enum value as string when applicable.",
                "message": "Human-readable failure reason.",
            },
        },
        usage_examples=[
            {
                "description": "Preview close of one invalid session",
                "command": {"session_key": sk, "dry_run": True},
                "explanation": "Checks that the session is invalid on CA without deleting it.",
            },
            {
                "description": "Close one invalid session locally only",
                "command": {"session_key": sk, "mode": "local_only", "force": True},
                "explanation": "Removes the editor directory without CA RPC.",
            },
            {
                "description": "Notify CA then close invalid session",
                "command": {"session_key": sk, "mode": "release_ca", "force": True},
                "explanation": (
                    "Sends stored ca_session_id to CA for lock release and session_delete, "
                    "then deletes the local session directory."
                ),
            },
        ],
        error_cases={
            "SESSION_NOT_FOUND": error_block(
                "SESSION_NOT_FOUND",
                "Session not found: {session_key}",
                "Verify session_key from session_connect or session_status.",
                description="The local session directory is missing or corrupt.",
            ),
            "SESSION_HAS_UNSAVED_BUFFERS": error_block(
                "SESSION_HAS_UNSAVED_BUFFERS",
                "Session has unsaved buffers",
                "Pass force=true or save/send buffers before closing.",
                description="A buffer has modified=true and force=false.",
            ),
            "SESSION_HAS_UNSENT_FILES": error_block(
                "SESSION_HAS_UNSENT_FILES",
                "Session has unsent files",
                "Pass force=true when abandoning unsent remote buffers.",
                description="A remote buffer has unsent changes and force=false.",
            ),
            "CA_SESSION_ALIVE": error_block(
                "CA_SESSION_ALIVE",
                "session is still registered on CA; use session_close instead",
                "Use session_close when the CA session is still live.",
                description="The session is not invalid — ca_session_id still exists on CA.",
            ),
        },
        best_practices=[
            "Always pass session_key from session_connect or session_status.",
            "Run with dry_run=true first to confirm the session is invalid on CA.",
            "Prefer mode=release_ca when CA may still hold orphaned file locks.",
            "Use mode=local_only when CA is unreachable or ca_session_id is already gone.",
            "Do not use this command for healthy sessions; use session_close instead.",
        ],
    )
