"""AiEditorConfigValidator validates ai_editor and code_analysis_server."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp_proxy_adapter.core.config.simple_config import SimpleConfigModel
from mcp_proxy_adapter.core.config.simple_config_validator import SimpleConfigValidator
from mcp_proxy_adapter.core.config.validators.base_validator import (
    BaseValidator,
    ValidationError,
)
from mcp_proxy_adapter.core.config.validators.ssl_validator import SSLValidator

from ai_editor.config.config_section import AiEditorConfig, CodeAnalysisServerConfig


def parse_threshold(value: str | int) -> int:
    """Parse ai_editor formatter threshold into bytes.

    Accepts bare integers and k/m suffixes (optionally with trailing `b`).
    """
    if isinstance(value, int):
        if value < 0:
            raise ValueError("threshold must be non-negative")
        return value
    if not isinstance(value, str):
        raise ValueError("threshold must be a string or integer")

    text = value.strip().lower()
    if not text:
        raise ValueError("threshold must not be empty")

    multiplier = 1
    if text.endswith("kb"):
        text = text[:-2]
        multiplier = 1_000
    elif text.endswith("mb"):
        text = text[:-2]
        multiplier = 1_000_000
    elif text.endswith("k"):
        text = text[:-1]
        multiplier = 1_000
    elif text.endswith("m"):
        text = text[:-1]
        multiplier = 1_000_000

    if not text.isdigit():
        raise ValueError("threshold must be an integer optionally suffixed with k/m")
    return int(text) * multiplier


class AiEditorConfigValidator(BaseValidator):
    """Validate ai_editor-specific sections while composing adapter validators."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(config_path=config_path)
        self._simple_validator = SimpleConfigValidator(config_path)
        self._ssl_validator = SSLValidator(config_path)

    def validate(self, model: dict[str, Any] | SimpleConfigModel) -> list[ValidationError]:
        """Validate config model/raw dict; never raise, always return errors."""
        errors: list[ValidationError] = []

        raw: dict[str, Any]
        if isinstance(model, SimpleConfigModel):
            try:
                errors.extend(self._simple_validator.validate(model))
            except Exception as exc:
                errors.append(ValidationError(f"adapter validation failed: {exc}"))
            raw = asdict(model)
        else:
            raw = model

        errors.extend(self._validate_ai_editor(raw))
        errors.extend(self._validate_code_analysis_server(raw))
        return errors

    def _validate_ai_editor(self, raw: dict[str, Any]) -> list[ValidationError]:
        section = raw.get("ai_editor")
        if section is None:
            return []

        errors: list[ValidationError] = []
        try:
            cfg = AiEditorConfig.from_config_json(raw)
            parse_threshold(cfg.formatter.small_file_threshold)
            if cfg.formatter.small_file_formatter not in {"text", "yaml", "cst"}:
                errors.append(
                    ValidationError(
                        "ai_editor.formatter.small_file_formatter must be one of: text, yaml, cst"
                    )
                )
        except Exception as exc:
            errors.append(ValidationError(f"Invalid ai_editor config: {exc}"))
        return errors

    def _validate_code_analysis_server(self, raw: dict[str, Any]) -> list[ValidationError]:
        section = raw.get("code_analysis_server")
        if section is None:
            return []

        errors: list[ValidationError] = []
        try:
            cfg = CodeAnalysisServerConfig.from_config_json(raw)
        except Exception as exc:
            return [ValidationError(f"Invalid code_analysis_server config: {exc}")]

        if cfg.protocol not in {"https", "mtls"}:
            errors.append(
                ValidationError(
                    "code_analysis_server.protocol must be one of: https, mtls"
                )
            )
        if cfg.port < 1 or cfg.port > 65535:
            errors.append(ValidationError("code_analysis_server.port must be 1..65535"))
        if cfg.protocol == "mtls" and not cfg.ssl:
            errors.append(
                ValidationError("code_analysis_server.ssl is required when protocol=mtls")
            )
        if cfg.auth.use_token and not cfg.auth.token_env:
            errors.append(
                ValidationError(
                    "code_analysis_server.auth.token_env is required when use_token=true"
                )
            )

        if cfg.ssl:
            ssl_obj = cfg.ssl
            errors.extend(
                self._ssl_validator.validate_ssl_files(
                    ssl_obj, "code_analysis_server", enabled=True
                )
            )
        return errors
