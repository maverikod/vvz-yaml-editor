"""Typed dataclass models for ai_editor and code_analysis_server config sections."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from mcp_proxy_adapter.core.config.simple_config import SSLConfig
except ImportError:
    SSLConfig = None  # type: ignore[assignment,misc]


@dataclass
class AiEditorFormatterConfig:
    """Formatter selection thresholds for ai_editor.

    Attributes:
        small_file_threshold: File size threshold string (e.g. '50kb') below which
            the small_file_formatter is preferred.
        small_file_formatter: Formatter name to use for small files.
    """

    small_file_threshold: str = "50kb"
    small_file_formatter: str = "text"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AiEditorFormatterConfig:
        """Build from a dict; missing keys use defaults."""
        return cls(
            small_file_threshold=d.get("small_file_threshold", "50kb"),
            small_file_formatter=d.get("small_file_formatter", "text"),
        )


@dataclass
class AiEditorSessionsConfig:
    """Session storage configuration.

    Attributes:
        base_dir: Absolute path to the directory where session directories are stored.
    """

    base_dir: str = "/tmp/ai_editor_sessions"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AiEditorSessionsConfig:
        """Build from a dict; missing keys use defaults."""
        return cls(base_dir=d.get("base_dir", "/tmp/ai_editor_sessions"))


@dataclass
class AiEditorConfig:
    """Top-level 'ai_editor' section of config.json.

    Attributes:
        formatter: Formatter selection thresholds.
        sessions: Session storage configuration.
    """

    formatter: AiEditorFormatterConfig = field(
        default_factory=AiEditorFormatterConfig
    )
    sessions: AiEditorSessionsConfig = field(
        default_factory=AiEditorSessionsConfig
    )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AiEditorConfig:
        """Build from the 'ai_editor' subsection dict; missing keys use defaults."""
        return cls(
            formatter=AiEditorFormatterConfig.from_dict(
                d.get("formatter", {})
            ),
            sessions=AiEditorSessionsConfig.from_dict(
                d.get("sessions", {})
            ),
        )

    @classmethod
    def from_config_json(cls, config: dict[str, Any]) -> AiEditorConfig:
        """Build from a full config.json dict (reads 'ai_editor' key)."""
        return cls.from_dict(config.get("ai_editor", {}))


@dataclass
class CodeAnalysisServerAuthConfig:
    """Authentication subsection of CodeAnalysisServerConfig.

    Attributes:
        use_token: If True, use HTTPS bearer token auth.
        token_env: Environment variable name holding the bearer token.
    """

    use_token: bool = False
    token_env: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CodeAnalysisServerAuthConfig:
        """Build from a dict; missing keys use defaults."""
        return cls(
            use_token=d.get("use_token", False),
            token_env=d.get("token_env"),
        )


@dataclass
class CodeAnalysisServerConfig:
    """Top-level 'code_analysis_server' section of config.json.

    Attributes:
        host: CA server hostname.
        port: CA server port.
        protocol: 'https' or 'mtls'.
        servername: TLS SNI servername override; None uses host.
        check_hostname: Whether to verify hostname in TLS handshake.
        ssl: SSLConfig for mTLS; None for plain HTTPS.
        auth: Authentication configuration.
    """

    host: str = "localhost"
    port: int = 15000
    protocol: str = "https"
    servername: str | None = None
    check_hostname: bool = True
    ssl: Any = None  # SSLConfig | None
    auth: CodeAnalysisServerAuthConfig = field(
        default_factory=CodeAnalysisServerAuthConfig
    )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CodeAnalysisServerConfig:
        """Build from a dict; missing keys use defaults."""
        return cls(
            host=d.get("host", "localhost"),
            port=int(d.get("port", 15000)),
            protocol=d.get("protocol", "https"),
            servername=d.get("servername"),
            check_hostname=bool(d.get("check_hostname", True)),
            ssl=d.get("ssl"),
            auth=CodeAnalysisServerAuthConfig.from_dict(d.get("auth", {})),
        )

    @classmethod
    def from_config_json(
        cls, config: dict[str, Any]
    ) -> CodeAnalysisServerConfig:
        """Build from a full config.json dict (reads 'code_analysis_server' key)."""
        return cls.from_dict(config.get("code_analysis_server", {}))
