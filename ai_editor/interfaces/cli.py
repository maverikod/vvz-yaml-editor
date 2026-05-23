"""CLI diagnostic wrapper over ai_editor.api — JSON stdout, errors stderr."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from ai_editor.api_init import init_api
from ai_editor.config.config_section import AiEditorConfig, CodeAnalysisServerConfig
from ai_editor.config.config_validator import AiEditorConfigValidator
from ai_editor.editor_core.formatter_registry import FormatterRegistry
from ai_editor import api


def _load_config(config_path: str) -> None:
    from mcp_proxy_adapter.core.config.simple_config import SimpleConfig

    model = SimpleConfig(config_path).load()
    errors = AiEditorConfigValidator().validate(model.raw)
    if errors:
        print(json.dumps({"errors": errors}), file=sys.stderr)
        sys.exit(1)
    ai_cfg = AiEditorConfig.from_config_json(model.raw)
    ca_cfg = CodeAnalysisServerConfig.from_config_json(model.raw)
    init_api(ai_cfg, ca_cfg, FormatterRegistry.get_instance())


def _out(data: Any) -> None:
    print(json.dumps(data, default=str))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ai-editor")
    parser.add_argument(
        "--config",
        default=os.environ.get("AI_EDITOR_CONFIG", "config.json"),
        help="Path to config.json (or AI_EDITOR_CONFIG env var).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("connect")
    p.add_argument("--ca-session-id", required=True)
    p.add_argument("--readonly", action="store_true")

    p = sub.add_parser("disconnect")
    p.add_argument("--session-key", required=True)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("open")
    p.add_argument("--session-key", required=True)
    p.add_argument("--project-id", required=True)
    p.add_argument("--file-path", required=True)
    p.add_argument("--formatter", default="auto")

    p = sub.add_parser("find")
    p.add_argument("--session-key", required=True)
    p.add_argument("--buffer-id", required=True)
    p.add_argument("--query", required=True, help="JSON query object")

    p = sub.add_parser("copy")
    p.add_argument("--session-key", required=True)
    p.add_argument("--buffer-id", required=True)
    p.add_argument("--address", required=True)

    p = sub.add_parser("paste")
    p.add_argument("--session-key", required=True)
    p.add_argument("--buffer-id", required=True)
    p.add_argument("--address", required=True)
    p.add_argument("--mode", default="replace")

    p = sub.add_parser("save")
    p.add_argument("--session-key", required=True)
    p.add_argument("--buffer-id", required=True)

    p = sub.add_parser("undo")
    p.add_argument("--session-key", required=True)
    p.add_argument("--buffer-id", required=True)
    p.add_argument("--steps", type=int, default=1)

    p = sub.add_parser("redo")
    p.add_argument("--session-key", required=True)
    p.add_argument("--buffer-id", required=True)
    p.add_argument("--steps", type=int, default=1)

    p = sub.add_parser("validate-file")
    p.add_argument("--session-key", required=True)
    p.add_argument("--file-path", required=True)
    p.add_argument("--project-id", required=True)

    args = parser.parse_args(argv)
    _load_config(args.config)

    try:
        if args.command == "connect":
            _out(api.connect(ca_session_id=args.ca_session_id, readonly=args.readonly))
        elif args.command == "disconnect":
            _out(api.close_session(args.session_key, force=args.force))
        elif args.command == "open":
            _out(
                api.open_buffer(
                    args.session_key,
                    args.project_id,
                    args.file_path,
                    formatter=args.formatter,
                )
            )
        elif args.command == "find":
            _out(
                api.find(
                    args.session_key,
                    args.buffer_id,
                    json.loads(args.query),
                )
            )
        elif args.command == "copy":
            _out(
                api.copy(
                    args.session_key,
                    {"buffer_id": args.buffer_id, "address": args.address},
                )
            )
        elif args.command == "paste":
            _out(
                api.paste(
                    args.session_key,
                    {"buffer_id": args.buffer_id, "address": args.address},
                    args.mode,
                )
            )
        elif args.command == "save":
            _out(api.save_buffer(args.session_key, args.buffer_id))
        elif args.command == "undo":
            _out(api.undo(args.session_key, args.buffer_id, steps=args.steps))
        elif args.command == "redo":
            _out(api.redo(args.session_key, args.buffer_id, steps=args.steps))
        elif args.command == "validate-file":
            _out(
                api.validate_file(
                    args.session_key,
                    file_path=args.file_path,
                    project_id=args.project_id,
                )
            )
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
