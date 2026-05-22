"""ai_editor MCP server entry - six-step startup sequence."""
from __future__ import annotations

import logging
import os
import sys

from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook
from mcp_proxy_adapter.core.app_factory import create_application
from mcp_proxy_adapter.core.app_factory.server_runner import run_server
from mcp_proxy_adapter.core.config.simple_config import SimpleConfig

from ai_editor.config.config_section import AiEditorConfig, CodeAnalysisServerConfig
from ai_editor.config.config_validator import AiEditorConfigValidator

logger = logging.getLogger(__name__)


def main(config_path: str | None = None) -> None:
    """Run six-step startup: load, validate, init_api, create_app, register commands, serve."""
    from ai_editor.api_init import init_api
    from ai_editor.hooks_register import formatter_registry, register_ai_editor_commands

    config_path = config_path or os.environ.get("AI_EDITOR_CONFIG", "config.json")

    # (1) Load config via adapter SimpleConfig
    model = SimpleConfig(config_path).load()

    # (2) Validate before any ai_editor objects are built
    errors = AiEditorConfigValidator().validate(model.raw)
    if errors:
        for err in errors:
            logger.error("config validation: %s", err)
        sys.exit(1)

    # (3) Build ai_editor singletons and run startup_sweep
    ai_cfg = AiEditorConfig.from_config_json(model.raw)
    ca_cfg = CodeAnalysisServerConfig.from_config_json(model.raw)
    init_api(ai_cfg, ca_cfg, formatter_registry)

    # (4) Adapter creates ASGI app (proxy registration per config auto_on_startup)
    app = create_application(model.raw)

    # (5) Register EditorCommand subclasses
    register_custom_commands_hook(register_ai_editor_commands)

    # (6) Start server (proxy unreachable still allows server start per config)
    run_server(app, model.raw.get("server", {}))


if __name__ == "__main__":
    main()
