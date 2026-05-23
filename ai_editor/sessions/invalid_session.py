"""Close editor sessions whose CA registration is missing or expired."""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from code_analysis_client import SessionNotFoundError

from ai_editor.contracts import ErrorCode, OperationResult
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.sessions.buffer_close import close_session
from ai_editor.sessions.session_git import destroy_session_git
from ai_editor.sessions.ca_session import work_ca_session_id
from ai_editor.sessions.recovery import release_all_locks_for_session
from ai_editor.sessions.session_dir import SETTINGS_NAME, read_session_settings

logger = logging.getLogger(__name__)

CloseInvalidMode = Literal["release_ca", "local_only"]


@dataclass
class CloseInvalidSessionEntry:
    """Outcome for one session processed by close_invalid_sessions."""

    session_key: str
    ca_session_id: str
    closed: bool
    skipped: bool = False
    skip_reason: str = ""
    ca_notified: bool = False
    message: str = ""


@dataclass
class CloseInvalidSessionsResult:
    """Aggregate result for close_invalid_sessions."""

    success: bool
    closed_count: int = 0
    skipped_count: int = 0
    results: list[CloseInvalidSessionEntry] = field(default_factory=list)
    message: str = ""


def is_ca_session_dead(ca_client: CodeAnalysisClient, ca_session_id: str) -> bool:
    """Return True when ca_session_id is absent or not registered on CA."""
    if not str(ca_session_id or "").strip():
        return True
    try:
        ca_client.assert_session_exists(ca_session_id)
    except SessionNotFoundError:
        return True
    except Exception as exc:
        logger.warning("CA session probe failed for %s: %s", ca_session_id, exc)
        return True
    return False


def _load_session_settings(base_dir: Path, session_key: str) -> dict[str, Any] | None:
    session_dir = base_dir / session_key
    settings_path = session_dir / SETTINGS_NAME
    if not session_dir.is_dir() or not settings_path.is_file():
        return None
    try:
        return read_session_settings(session_dir)
    except Exception:
        return None


def list_invalid_session_keys(
    base_dir: str | Path,
    ca_client: CodeAnalysisClient,
) -> list[str]:
    """Return session_key values for local dirs whose CA session is dead."""
    base = Path(base_dir)
    if not base.is_dir():
        return []
    invalid: list[str] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        session_key = child.name
        settings = _load_session_settings(base, session_key)
        if settings is None:
            continue
        ca_session_id = str(settings.get("ca_session_id") or "").strip()
        if is_ca_session_dead(ca_client, ca_session_id):
            invalid.append(session_key)
    return invalid


def _notify_ca_before_local_close(
    ca_client: CodeAnalysisClient,
    settings: dict[str, Any],
    buffers: list[dict[str, Any]],
) -> bool:
    """Best-effort lock release before local removal; subordinate cleanup is in close_session."""
    work_id = work_ca_session_id(settings)
    if not work_id:
        return False
    release_all_locks_for_session(
        ca_client,
        buffers,
        allow_foreign_session=True,
    )
    return True


def close_invalid_session(
    base_dir: str | Path,
    ca_client: CodeAnalysisClient,
    session_key: str,
    *,
    mode: CloseInvalidMode = "local_only",
    force: bool = False,
    dry_run: bool = False,
) -> CloseInvalidSessionEntry:
    """Close one local session when its CA registration is dead."""
    base = Path(base_dir)
    settings = _load_session_settings(base, session_key)
    if settings is None:
        return CloseInvalidSessionEntry(
            session_key=session_key,
            ca_session_id="",
            closed=False,
            skipped=True,
            skip_reason=ErrorCode.SESSION_NOT_FOUND.value,
            message="local session directory missing or corrupt",
        )

    ca_session_id = str(settings.get("ca_session_id") or "").strip()
    if not is_ca_session_dead(ca_client, ca_session_id):
        return CloseInvalidSessionEntry(
            session_key=session_key,
            ca_session_id=ca_session_id,
            closed=False,
            skipped=False,
            skip_reason="CA_SESSION_ALIVE",
            message="session is still registered on CA; use session_close instead",
        )

    if dry_run:
        return CloseInvalidSessionEntry(
            session_key=session_key,
            ca_session_id=ca_session_id,
            closed=False,
            skipped=False,
            message="dry_run: would close invalid session",
        )

    session_dir = base / session_key
    buffers = settings.get("open_buffers", [])

    if mode == "release_ca":
        ca_notified = _notify_ca_before_local_close(ca_client, settings, buffers)
        result = close_session(session_dir, session_key, ca_client, force=force)
    else:
        ca_notified = False
        if not force:
            for buf in buffers:
                if buf.get("readonly"):
                    continue
                if buf.get("modified"):
                    return CloseInvalidSessionEntry(
                        session_key=session_key,
                        ca_session_id=ca_session_id,
                        closed=False,
                        message=ErrorCode.SESSION_HAS_UNSAVED_BUFFERS.value,
                    )
                if buf.get("file_type") == "remote" and not buf.get("saved"):
                    return CloseInvalidSessionEntry(
                        session_key=session_key,
                        ca_session_id=ca_session_id,
                        closed=False,
                        message=ErrorCode.SESSION_HAS_UNSENT_FILES.value,
                    )
        destroy_session_git(session_dir)
        shutil.rmtree(session_dir, ignore_errors=True)
        result = OperationResult(success=True, message="session closed")

    if not result.success:
        return CloseInvalidSessionEntry(
            session_key=session_key,
            ca_session_id=ca_session_id,
            closed=False,
            ca_notified=ca_notified,
            message=str(result.message or result.error_code or "close failed"),
        )

    return CloseInvalidSessionEntry(
        session_key=session_key,
        ca_session_id=ca_session_id,
        closed=True,
        ca_notified=ca_notified,
        message=str(result.message or "invalid session closed"),
    )


def close_invalid_sessions(
    base_dir: str | Path,
    ca_client: CodeAnalysisClient,
    *,
    session_key: str,
    mode: CloseInvalidMode = "local_only",
    force: bool = False,
    dry_run: bool = False,
) -> CloseInvalidSessionsResult:
    """Close one invalid local session identified by session_key."""
    if not str(session_key or "").strip():
        raise ValueError(ErrorCode.SESSION_NOT_FOUND.value)

    results: list[CloseInvalidSessionEntry] = [
        close_invalid_session(
            base_dir,
            ca_client,
            session_key,
            mode=mode,
            force=force,
            dry_run=dry_run,
        )
    ]

    closed_count = sum(1 for item in results if item.closed)
    skipped_count = sum(1 for item in results if item.skipped)
    failed = [item for item in results if not item.closed and not item.skipped and not dry_run]
    success = not failed

    if dry_run:
        message = f"dry_run: {len(results)} invalid session(s) matched"
    elif closed_count:
        message = f"closed {closed_count} invalid session(s)"
    elif skipped_count and not failed:
        message = "no invalid sessions to close"
    else:
        message = "close invalid sessions finished with errors"

    return CloseInvalidSessionsResult(
        success=success,
        closed_count=closed_count,
        skipped_count=skipped_count,
        results=results,
        message=message,
    )
