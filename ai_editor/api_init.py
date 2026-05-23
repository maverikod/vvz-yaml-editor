"""Singleton initialisation for ai_editor api facade."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_editor.config.config_section import AiEditorConfig, CodeAnalysisServerConfig
from ai_editor.editor_core.ca_client import CodeAnalysisClient
from ai_editor.editor_core.formatter_registry import FormatterRegistry

if TYPE_CHECKING:
    from ai_editor.session_manager import SessionManager

_ca_client: CodeAnalysisClient | None = None
_session_manager: "SessionManager | None" = None


def init_api(
    config: AiEditorConfig,
    ca_config: CodeAnalysisServerConfig,
    formatter_registry: FormatterRegistry,
    *,
    editor_server_uuid: str = "",
) -> None:
    """Build CA client and SessionManager; run startup_sweep once."""
    global _ca_client, _session_manager
    from ai_editor.session_manager import SessionManager

    _ca_client = CodeAnalysisClient.from_config(ca_config)
    base_dir = config.sessions.base_dir
    _session_manager = SessionManager(
        base_dir,
        _ca_client,
        formatter_registry,
        editor_server_uuid=editor_server_uuid,
    )
    try:
        from ai_editor.sessions.recovery import startup_sweep
    except Exception:  # noqa: BLE001
        startup_sweep = None

    if startup_sweep is not None:
        startup_sweep(base_dir, _ca_client)


def get_ca_client() -> CodeAnalysisClient:
    if _ca_client is None:
        raise RuntimeError("init_api() must be called before using api")
    return _ca_client


def get_session_manager() -> "SessionManager":
    if _session_manager is None:
        raise RuntimeError("init_api() must be called before using api")
    return _session_manager
