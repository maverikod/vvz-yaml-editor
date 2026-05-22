"""ai_editor MCP server entry - six-step startup sequence."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from mcp_proxy_adapter.api.app import create_app
from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook
from mcp_proxy_adapter.core.server_adapter import UnifiedServerRunner

from ai_editor.config.config_section import AiEditorConfig, CodeAnalysisServerConfig
from ai_editor.config.config_validator import AiEditorConfigValidator

logger = logging.getLogger(__name__)


def _load_raw_config(config_path: str) -> dict:
    return json.loads(Path(config_path).read_text(encoding="utf-8"))


def main(config_path: str | None = None) -> None:
    """Run six-step startup: load, validate, init_api, create_app, register commands, serve."""
    from ai_editor.api_init import init_api
    from ai_editor.hooks_register import formatter_registry, register_ai_editor_commands

    config_path = config_path or os.environ.get("AI_EDITOR_CONFIG", "config.json")
    raw = _load_raw_config(config_path)

    # (2) Validate before any ai_editor objects are built
    errors = AiEditorConfigValidator(config_path=config_path).validate(raw)
    if errors:
        for err in errors:
            logger.error("config validation: %s", getattr(err, "message", err))
        sys.exit(1)

    # (3) Build ai_editor singletons and run startup_sweep
    ai_cfg = AiEditorConfig.from_config_json(raw)
    ca_cfg = CodeAnalysisServerConfig.from_config_json(raw)
    init_api(ai_cfg, ca_cfg, formatter_registry)

    # (4) Adapter creates ASGI app; lifespan handles proxy auto-registration
    app = create_app(
        title="AI Editor",
        description=raw.get("registration", {})
        .get("metadata", {})
        .get("description", "Universal document editor for AI models and MCP"),
        version=raw.get("registration", {}).get("metadata", {}).get("version", "1.0.0"),
        app_config=raw,
        config_path=config_path,
    )

    # (5) Register EditorCommand subclasses
    register_custom_commands_hook(register_ai_editor_commands)

    # (6) Start server (registration runs in app lifespan when auto_on_startup=true)
    UnifiedServerRunner().run_server(app, raw.get("server", {}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="ai-editor-server")
    parser.add_argument(
        "--config",
        default=os.environ.get("AI_EDITOR_CONFIG", "config.json"),
        help="Path to config.json",
    )
    args = parser.parse_args()
    main(args.config)
