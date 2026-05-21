#!/usr/bin/env python3
"""Generate atomic step YAML files for G-006 and G-007. Run once, then delete."""
from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _gen_g006_g007_templates import (  # noqa: E402
    AIEDMGR_PY,
    API_INIT_PY,
    API_PY,
    CLI_PY,
    MAIN_PY,
    SESSION_MANAGER_PY,
    TEST_CONFIG_INTEGRATION_PY,
    TEST_GENERATOR_INTEGRATION_PY,
)

PLAN = ROOT / "docs/plans/ai_editor"
AUTHOR = "Vasiliy Zdanovskiy"
EMAIL = "vasilyvz@gmail.com"
CATEGORY = "editor"


def yaml_quote(s: str) -> str:
    """Escape string for YAML double-quoted scalar."""
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


def write_as(
    ts_dir: Path,
    step_id: str,
    slug: str,
    *,
    parent_ts: str,
    name: str,
    target_file: str,
    operation: str,
    priority: int,
    depends_on: list[str],
    concepts: list[str],
    prompt: str,
    vtype: str,
    vtarget: str,
    vexpected: str,
) -> Path:
    ts_dir.mkdir(parents=True, exist_ok=True)
    adir = ts_dir / "atomic_steps"
    adir.mkdir(exist_ok=True)
    path = adir / f"{step_id}-{slug}.yaml"
    dep = "" if not depends_on else "\n".join(f"  - {d}" for d in depends_on)
    dep_block = f"depends_on:\n{dep}\n" if depends_on else "depends_on: []\n"
    content = f"""step_id: {step_id}
parent_tactical_step: {parent_ts}
name: {name}
target_file: {target_file}
operation: {operation}
priority: {priority}
{dep_block}concepts:
{chr(10).join(f'  - {c}' for c in concepts)}
prompt: "{yaml_quote(prompt)}"
status: draft
verification:
  type: {vtype}
  target: {vtarget}
  expected: {vexpected}
"""
    path.write_text(content, encoding="utf-8")
    return path


def schema_py(cmd: str, props: str, required: str = "", extra_props: str = "False") -> str:
    props_block = "\n".join(
        f"            {line.rstrip(',')}," if not line.rstrip().endswith(",") else f"            {line}"
        for line in props.splitlines()
        if line.strip()
    )
    # normalize: props may already include trailing commas
    props_lines = []
    for line in props.splitlines():
        s = line.strip()
        if not s:
            continue
        if not s.endswith(","):
            s += ","
        props_lines.append(f"            {s}")
    props_block = "\n".join(props_lines)
    req_line = f'        "required": [{required}],\n' if required else ""
    return (
        f'"""JSON Schema for {cmd} command parameters."""\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n\n"
        f"def get_{cmd}_schema() -> dict[str, Any]:\n"
        f'    """Return machine-readable input schema for {cmd}."""\n'
        "    return {\n"
        '        "type": "object",\n'
        '        "properties": {\n'
        f"{props_block}\n"
        "        },\n"
        f"{req_line}"
        f'        "additionalProperties": {extra_props},\n'
        "    }\n"
    )


def metadata_py(cmd: str, descr: str, detailed: str, params_doc: str, dry_run: bool = False) -> str:
    dry = ""
    if dry_run:
        dry = (
            '        "dry_run": {\n'
            '            "description": "When True, preview the operation without mutating state.",\n'
            '            "type": "boolean",\n'
            '            "required": False,\n'
            '            "default": False,\n'
            '        },\n'
        )
    return textwrap.dedent(
        f'''\
        """Extended metadata for {cmd} command."""
        from __future__ import annotations

        from typing import Any, Type


        def get_{cmd}_metadata(cls: Type[Any]) -> dict[str, Any]:
            """Return AI/documentation metadata for {cmd}."""
            return {{
                "name": cls.name,
                "version": cls.version,
                "description": cls.descr,
                "category": cls.category,
                "author": cls.author,
                "email": cls.email,
                "detailed_description": (
                    "{detailed}"
                ),
                "parameters": {{
        {params_doc}
        {dry}    }},
                "return_value": {{
                    "success": {{
                        "description": "Operation succeeded.",
                        "data": "{{result fields from api layer}}",
                    }},
                    "error": {{
                        "description": "Operation failed.",
                        "code": "ErrorCode string",
                        "message": "Human-readable message",
                    }},
                }},
                "usage_examples": [
                    {{
                        "description": "Typical {cmd} invocation",
                        "command": {{}},
                        "explanation": "Returns success envelope with result data.",
                    }},
                ],
                "error_cases": {{
                    "OPERATION_FAILED": {{
                        "description": "Underlying api call returned success=False.",
                        "message": "{{message from OperationResult}}",
                        "solution": "Check session_key and buffer_id; verify session is open.",
                    }},
                }},
                "best_practices": [
                    "Call init_api() before executing commands (handled by main.py startup).",
                    "Use dry_run=True on destructive commands to preview changes.",
                ],
            }}
        '''
    )


def result_to_dict(body: str) -> str:
    return (
        f"        result = {body}\n"
        "        if hasattr(result, \"__dataclass_fields__\"):\n"
        "            from dataclasses import asdict\n"
        "            payload = asdict(result)\n"
        "            if payload.get(\"error_code\") is not None:\n"
        "                payload[\"error_code\"] = str(payload[\"error_code\"])\n"
        "            return {\"success\": payload.get(\"success\", True), \"data\": payload}\n"
        "        if isinstance(result, dict):\n"
        "            return {\"success\": True, \"data\": result}\n"
        "        return {\"success\": True, \"data\": result}"
    )


def command_py(
    cmd: str,
    class_name: str,
    api_fn: str,
    execute_call: str,
    validate_extra: str = "",
    imports: str = "from ai_editor import api",
) -> str:
    exec_body = result_to_dict(execute_call)
    val = validate_extra or "        return params"
    return (
        f'"""{cmd} MCP command — delegates to ai_editor.api.{api_fn}."""\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n\n"
        "from mcp_proxy_adapter.commands.base import Command\n\n"
        f"from ai_editor.commands.{cmd}_metadata import get_{cmd}_metadata\n"
        f"from ai_editor.commands.{cmd}_schema import get_{cmd}_schema\n"
        f"{imports}\n\n\n"
        f"class {class_name}(Command):\n"
        f'    """MCP command: {cmd}."""\n\n'
        f'    name = "{cmd}"\n'
        '    version = "1.0.0"\n'
        f'    descr = "{cmd.replace("_", " ").title()}"\n'
        f'    category = "{CATEGORY}"\n'
        f'    author = "{AUTHOR}"\n'
        f'    email = "{EMAIL}"\n\n'
        "    @classmethod\n"
        "    def get_schema(cls) -> dict[str, Any]:\n"
        f"        return get_{cmd}_schema()\n\n"
        "    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:\n"
        "        params = super().validate_params(params)\n"
        f"{val}\n\n"
        "    async def execute(self, **params: Any) -> dict[str, Any]:\n"
        f"{exec_body}\n\n"
        "    @classmethod\n"
        "    def metadata(cls) -> dict[str, Any]:\n"
        f"        return get_{cmd}_metadata(cls)\n"
    )


def hooks_register_create() -> str:
    return textwrap.dedent(
        '''\
        """Register ai_editor formatters and commands with mcp_proxy_adapter."""
        from __future__ import annotations

        from typing import Any

        from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook

        from ai_editor.editor_core.formatter_registry import FormatterRegistry

        formatter_registry = FormatterRegistry.get_instance()


        def _register_formatters() -> None:
            """Register G-003 formatters in mandatory order: text, yaml, json, cst."""
            from ai_editor.formatters.cst import CSTFormatter
            from ai_editor.formatters.json import JsonFormatter
            from ai_editor.formatters.text import TextFormatter
            from ai_editor.formatters.yaml import YamlFormatter

            formatter_registry.register(
                "text",
                [".txt", ".log", ".rst", ".ini", ".cfg", ".toml"],
                TextFormatter,
            )
            formatter_registry.register("yaml", [".yaml", ".yml"], YamlFormatter)
            formatter_registry.register("json", [".json"], JsonFormatter)
            formatter_registry.register("cst", [".py"], CSTFormatter)


        _register_formatters()


        def _register(registry: Any) -> None:
            """Register EditorCommand subclasses. Extended by T-002..T-011."""
            pass


        register_custom_commands_hook(_register)


        def register_ai_editor_commands(registry: Any) -> None:
            """Public hook entry called from main.py."""
            _register(registry)
        '''
    )


def cmd_class_name(cmd: str) -> str:
    return "".join(p.capitalize() for p in cmd.split("_")) + "Command"


TS_COMMANDS: dict[str, list[str]] = {
    "T-002": ["session_connect", "session_reconnect", "session_close", "session_status"],
    "T-003": ["file_open", "file_close", "file_get", "file_send", "file_create"],
    "T-004": ["buf_undo", "buf_redo"],
    "T-005": ["buf_copy", "buf_cut", "buf_paste"],
    "T-006": ["search_find", "search_find_one", "search_list_units"],
    "T-007": ["buf_validate", "validate_file", "formatter_commands"],
    "T-008": [
        "yaml_get_command",
        "yaml_update_command",
        "yaml_get_verification",
        "yaml_append_verification",
        "yaml_validate_plan_task",
    ],
    "T-011": [
        "buf_new",
        "buf_save_as",
        "buf_reload",
        "buf_get_state",
        "buf_write_all",
        "buf_mutate_batch",
    ],
}

TS_ORDER = ["T-002", "T-003", "T-004", "T-005", "T-006", "T-007", "T-008", "T-011"]


def commands_through(ts_id: str) -> list[str]:
    out: list[str] = []
    for ts in TS_ORDER:
        out.extend(TS_COMMANDS[ts])
        if ts == ts_id:
            break
    return out


def hooks_register_full(commands: list[str]) -> str:
    imports = "\n".join(
        f"    from ai_editor.commands.{c}_command import {cmd_class_name(c)}"
        for c in commands
    )
    regs = "\n".join(
        f'    registry.register({cmd_class_name(c)}, "custom")' for c in commands
    )
    new_register = (
        f'def _register(registry: Any) -> None:\n'
        f'    """Register EditorCommand subclasses."""\n{imports}\n{regs}\n'
    )
    base = hooks_register_create()
    old = (
        'def _register(registry: Any) -> None:\n'
        '    """Register EditorCommand subclasses. Extended by T-002..T-011."""\n'
        "    pass"
    )
    return base.replace(old, new_register.rstrip())


def hooks_register_modify(commands: list[str], prior_content: str | None = None) -> str:
    if prior_content is None:
        prior = commands_through(TS_ORDER[TS_ORDER.index(
            next(t for t in TS_ORDER if set(TS_COMMANDS[t]).issubset(set(commands)))
        ) - 1]) if commands else []
        # fallback: build from all commands passed
        return hooks_register_full(commands)
    prior_cmds: list[str] = []
    for line in prior_content.splitlines():
        if "from ai_editor.commands." in line and "_command import" in line:
            part = line.split("commands.")[1].split("_command")[0]
            prior_cmds.append(part)
    return hooks_register_full(prior_cmds + [c for c in commands if c not in prior_cmds])


def gen_command_triplet(
    ts_dir: Path,
    ts_id: str,
    cmd: str,
    *,
    start_priority: int,
    api_fn: str,
    schema_props: str,
    schema_required: str = "",
    metadata_params: str,
    metadata_detailed: str,
    execute_call: str,
    validate_extra: str = "",
    dry_run: bool = False,
    concepts: list[str] | None = None,
    command_imports: str = "from ai_editor import api",
    command_depends_on: list[str] | None = None,
) -> tuple[list[str], int]:
    """Generate schema, metadata, command AS files. Return (step_ids, next_priority)."""
    concepts = concepts or ["C-045", "C-047"]
    class_name = cmd_class_name(cmd)
    pri = start_priority
    ids: list[str] = []
    cmd_dep = command_depends_on or []

    schema_code = schema_py(cmd, schema_props, schema_required)
    prompt_s = (
        f"Project: ai_editor. Tactical step: {ts_id}. "
        f"File: ai_editor/commands/{cmd}_schema.py. Operation: create_file.\n\n"
        f"MRS concepts C-045 EditorCommand, C-047 ApiFacade.\n"
        f"metadatastd: get_schema() returns JSON Schema with additionalProperties=False.\n\n"
        f"Create with exact content:\n\n```python\n{schema_code}```"
    )
    sid = f"A-{pri:03d}"
    write_as(
        ts_dir, sid, f"create-{cmd.replace('_', '-')}-schema-py",
        parent_ts=ts_id,
        name=f"Create {cmd}_schema.py",
        target_file=f"ai_editor/commands/{cmd}_schema.py",
        operation="create_file", priority=pri, depends_on=[], concepts=concepts,
        prompt=prompt_s, vtype="import",
        vtarget=f"ai_editor.commands.{cmd}_schema",
        vexpected=f"get_{cmd}_schema() returns dict with type=object and additionalProperties=False.",
    )
    ids.append(sid)
    pri += 1

    meta_code = metadata_py(cmd, cmd, metadata_detailed, metadata_params, dry_run)
    prompt_m = (
        f"Project: ai_editor. Tactical step: {ts_id}. "
        f"File: ai_editor/commands/{cmd}_metadata.py. Operation: create_file.\n\n"
        f"MRS C-045: metadata() separate from get_schema(). Required fields per metadatastd.\n\n"
        f"Create with exact content:\n\n```python\n{meta_code}```"
    )
    sid = f"A-{pri:03d}"
    write_as(
        ts_dir, sid, f"create-{cmd.replace('_', '-')}-metadata-py",
        parent_ts=ts_id,
        name=f"Create {cmd}_metadata.py",
        target_file=f"ai_editor/commands/{cmd}_metadata.py",
        operation="create_file", priority=pri, depends_on=[], concepts=concepts,
        prompt=prompt_m, vtype="import",
        vtarget=f"ai_editor.commands.{cmd}_metadata",
        vexpected=f"get_{cmd}_metadata() returns dict with name, detailed_description, error_cases.",
    )
    ids.append(sid)
    pri += 1

    cmd_code = command_py(cmd, class_name, api_fn, execute_call, validate_extra, command_imports)
    api_note = (
        f"Requires ai_editor.api.{api_fn} from G-006/T-010 (api.py facade).\n"
        if ts_id == "T-004"
        else ""
    )
    prompt_c = (
        f"Project: ai_editor. Tactical step: {ts_id}. "
        f"File: ai_editor/commands/{cmd}_command.py. Operation: create_file.\n\n"
        f"MRS C-045: extends Command from mcp_proxy_adapter.commands.base.\n"
        f"validate_params calls super() first. async execute delegates to api.{api_fn} only.\n"
        f"Never import session layer directly.\n\n"
        f"{api_note}"
        f"api.{api_fn} signature (G-006/T-010 api.py):\n"
        f"  synchronous; returns OperationResult or dataclass/dict.\n\n"
        f"Create with exact content:\n\n```python\n{cmd_code}```"
    )
    sid = f"A-{pri:03d}"
    write_as(
        ts_dir, sid, f"create-{cmd.replace('_', '-')}-command-py",
        parent_ts=ts_id,
        name=f"Create {cmd}_command.py",
        target_file=f"ai_editor/commands/{cmd}_command.py",
        operation="create_file", priority=pri, depends_on=cmd_dep, concepts=concepts,
        prompt=prompt_c, vtype="import",
        vtarget=f"ai_editor.commands.{cmd}_command.{class_name}",
        vexpected=f"{class_name} imports; name=='{cmd}'; get_schema and metadata callable.",
    )
    ids.append(sid)
    return ids, pri + 1


def write_hooks_update(
    ts_dir: Path,
    ts_id: str,
    pri: int,
    all_ids: list[str],
    cumulative_ts: str,
    slug: str,
    detail: str,
) -> str:
    """Append hooks_register modify AS; return step id."""
    hr = hooks_register_full(commands_through(cumulative_ts))
    sid = f"A-{pri:03d}"
    write_as(
        ts_dir, sid, slug,
        parent_ts=ts_id,
        name=f"Register commands in hooks_register ({ts_id})",
        target_file="ai_editor/hooks_register.py",
        operation="modify_file",
        priority=pri,
        depends_on=[all_ids[-1]] if all_ids else [],
        concepts=["C-046"],
        prompt=(
            f"Project: ai_editor. Tactical step: {ts_id}. "
            "File: ai_editor/hooks_register.py. Operation: modify_file.\n\n"
            f"{detail}\n\n"
            f"Full cumulative content after {ts_id}:\n\n```python\n{hr}```"
        ),
        vtype="import",
        vtarget="ai_editor.hooks_register",
        vexpected=f"_register registers all commands through {ts_id}.",
    )
    all_ids.append(sid)
    return sid


DRY_RUN_PROP = (
    '"dry_run": {"type": "boolean", "default": False, '
    '"description": "Preview without mutating state."}'
)
QUERY_PROP = (
    '"query": {"type": "object", "properties": {"kind": {"type": "string"}, '
    '"value": {}, "options": {"type": "object"}}, '
    '"required": ["kind"], "additionalProperties": False}'
)
ADDRESS_SOURCE = (
    '"source": {"type": "object", "properties": {"buffer_id": {"type": "string"}, '
    '"address": {}}, "required": ["buffer_id", "address"], "additionalProperties": False}'
)
ADDRESS_TARGET = (
    '"target": {"type": "object", "properties": {"buffer_id": {"type": "string"}, '
    '"address": {}}, "required": ["buffer_id", "address"], "additionalProperties": False}'
)
PASTE_MODE_ENUM = (
    '"mode": {"type": "string", "enum": ["set", "replace_block", "append", '
    '"insert_before", "insert_after", "insert", "replace_range", "prepend", '
    '"replace", "delete"]}'
)
SEARCH_VALIDATE = textwrap.dedent(
    """\
            from ai_editor.search.query import validate_query
            query = params.get("query")
            if query is not None:
                errs = validate_query(query)
                if errs:
                    raise ValueError("; ".join(errs))
            return params"""
)


# --- T-001 ---
def gen_t001() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-001-command-base-hooks"
    ids = []
    write_as(
        ts, "A-001", "create-commands-init",
        parent_ts="T-001",
        name="Create ai_editor/commands/__init__.py",
        target_file="ai_editor/commands/__init__.py",
        operation="create_file", priority=1, depends_on=[], concepts=["C-046"],
        prompt=(
            "Project: ai_editor. Tactical step: T-001. "
            "File: ai_editor/commands/__init__.py. Operation: create_file.\n\n"
            "MRS C-046 HooksRegister owns command package.\n\n"
            "Create empty package init:\n\n```python\n"
            '"""ai_editor MCP command implementations."""\n\n__all__: list[str] = []\n```'
        ),
        vtype="import", vtarget="ai_editor.commands",
        vexpected="Package imports without error.",
    )
    ids.append("A-001")
    hr = hooks_register_create()
    write_as(
        ts, "A-002", "create-hooks-register",
        parent_ts="T-001",
        name="Create ai_editor/hooks_register.py",
        target_file="ai_editor/hooks_register.py",
        operation="create_file", priority=2, depends_on=["A-001"], concepts=["C-046", "C-012"],
        prompt=(
            "Project: ai_editor. Tactical step: T-001. "
            "File: ai_editor/hooks_register.py. Operation: create_file.\n\n"
            "MRS C-046 HooksRegister: registers formatters at import, skeleton _register for commands.\n"
            "C-012 FormatterRegistry singleton from ai_editor.editor_core.formatter_registry.\n\n"
            "G-003 formatters (assume exist): TextFormatter, YamlFormatter, JsonFormatter, CSTFormatter.\n"
            "Registration order MANDATORY: (1) text (2) yaml (3) json (4) cst.\n"
            "Do NOT register markdown/xml/html (G-008 future).\n\n"
            "Pattern: register_custom_commands_hook(_register) at module level.\n"
            "Export register_ai_editor_commands(registry) calling _register(registry).\n\n"
            f"Create with exact content:\n\n```python\n{hr}```"
        ),
        vtype="import", vtarget="ai_editor.hooks_register",
        vexpected="formatter_registry has text,yaml,json,cst registered; register_ai_editor_commands callable.",
    )
    ids.append("A-002")
    return ids


SESSION_KEY = '"session_key": {"type": "string", "description": "UUID4 session identifier."}'
BUFFER_ID = '"buffer_id": {"type": "string", "description": "Open buffer identifier."}'


def gen_t002() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-002-session-commands"
    all_ids: list[str] = []
    pri = 1
    specs = [
        ("session_connect", "connect", '"readonly": {"type": "boolean", "default": False, "description": "Open session read-only."}', "",
         '"readonly": {"description": "Read-only session flag.", "type": "boolean", "required": False, "default": False},',
         "Create a new editing session. Command name session_connect; api.connect(readonly=False).",
         "api.connect(readonly=params.get('readonly', False))"),
        ("session_reconnect", "reconnect",
         f'{SESSION_KEY}', '"session_key"',
         f'{SESSION_KEY.replace("session_key", "session_key")}',
         "Reconnect to existing session by session_key.",
         "api.reconnect(session_key=params['session_key'])"),
        ("session_close", "close_session",
         f'{SESSION_KEY},\n        "force": {{"type": "boolean", "default": False, "description": "Force close with unsaved buffers."}}',
         '"session_key"',
         f'{SESSION_KEY},\n        "force": {{"description": "Force close.", "type": "boolean", "required": False, "default": False}},',
         "Close session; without force checks modified=False and remote saved=True.",
         "api.close_session(session_key=params['session_key'], force=params.get('force', False))"),
        ("session_status", "session_status",
         f'{SESSION_KEY}', '"session_key"',
         f'{SESSION_KEY}',
         "Read-only session status returning SessionDescriptor.",
         "api.session_status(session_key=params['session_key'])"),
    ]
    cmds = []
    for cmd, api_fn, props, req, meta_p, detail, exec_call in specs:
        ids, pri = gen_command_triplet(
            ts, "T-002", cmd, start_priority=pri, api_fn=api_fn,
            schema_props=props, schema_required=req, metadata_params=meta_p,
            metadata_detailed=detail, execute_call=exec_call,
            concepts=["C-045", "C-047"],
        )
        all_ids.extend(ids)
        cmds.append(cmd)
    hr = hooks_register_full(cmds)
    write_as(
        ts, f"A-{pri:03d}", "update-hooks-register-session",
        parent_ts="T-002",
        name="Register session commands in hooks_register",
        target_file="ai_editor/hooks_register.py",
        operation="modify_file", priority=pri, depends_on=[all_ids[-1]], concepts=["C-046"],
        prompt=(
            "Project: ai_editor. Tactical step: T-002. "
            "File: ai_editor/hooks_register.py. Operation: modify_file.\n\n"
            "Current file content after T-001:\n\n```python\n" + hooks_register_create() + "```\n\n"
            "Replace _register body (pass) with registration of session_connect, session_reconnect, "
            "session_close, session_status. Keep formatter registration and hook call unchanged.\n\n"
            f"Full post-modification content:\n\n```python\n{hr}```"
        ),
        vtype="import", vtarget="ai_editor.hooks_register",
        vexpected="_register registers four session commands via registry.register(..., 'custom').",
    )
    all_ids.append(f"A-{pri:03d}")
    return all_ids


def gen_t003() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-003-buffer-commands"
    all_ids: list[str] = []
    pri = 1
    dry_props = '"dry_run": {"type": "boolean", "default": False, "description": "Preview without mutating."}'
    specs = [
        ("file_open", "open_buffer", False,
         f'{SESSION_KEY},\n        "project_id": {{"type": "string", "description": "Project UUID (required)."}},\n        "file_path": {{"type": "string"}},\n        "formatter": {{"type": "string", "default": "auto"}},\n        "open_as_text": {{"type": "boolean", "default": False}},\n        "readonly": {{"type": "boolean", "default": False}}',
         '"session_key", "project_id", "file_path"',
         "api.open_buffer(session_key=..., project_id=..., file_path=..., formatter=params.get('formatter','auto'), open_as_text=params.get('open_as_text',False), readonly=params.get('readonly',False))"),
        ("file_close", "close_buffer", True,
         f'{SESSION_KEY},\n        {BUFFER_ID},\n        "force": {{"type": "boolean", "default": False}},\n        {dry_props}',
         '"session_key", "buffer_id"',
         "api.close_buffer(session_key=params['session_key'], buffer_id=params['buffer_id'], force=params.get('force',False), dry_run=params.get('dry_run',False))"),
        ("file_get", "get_buffer_state", False,
         f'{SESSION_KEY},\n        {BUFFER_ID}', '"session_key", "buffer_id"',
         "api.get_buffer_state(session_key=params['session_key'], buffer_id=params['buffer_id'])"),
        ("file_send", "save_buffer", True,
         f'{SESSION_KEY},\n        {BUFFER_ID},\n        {dry_props}', '"session_key", "buffer_id"',
         "api.save_buffer(session_key=params['session_key'], buffer_id=params['buffer_id'], dry_run=params.get('dry_run',False))"),
        ("file_create", "new_buffer", False,
         f'{SESSION_KEY},\n        "formatter": {{"type": "string", "default": "auto"}},\n        "content": {{"type": "string", "default": ""}},\n        "display_name": {{"type": "string"}}',
         '"session_key"',
         "api.new_buffer(session_key=params['session_key'], formatter_name=params.get('formatter','auto'), initial_content=params.get('content',''), display_name=params.get('display_name'))"),
    ]
    cmds = []
    for cmd, api_fn, dry, props, req, exec_call in specs:
        ids, pri = gen_command_triplet(
            ts, "T-003", cmd, start_priority=pri, api_fn=api_fn,
            schema_props=props, schema_required=req,
            metadata_params=SESSION_KEY, metadata_detailed=f"File command {cmd} via api.{api_fn}.",
            execute_call=exec_call, dry_run=dry,
        )
        all_ids.extend(ids)
        cmds.append(cmd)
    hr = hooks_register_full(commands_through("T-003"))
    write_as(
        ts, f"A-{pri:03d}", "update-hooks-register-file",
        parent_ts="T-003",
        name="Register file commands in hooks_register",
        target_file="ai_editor/hooks_register.py",
        operation="modify_file", priority=pri, depends_on=[all_ids[-1]], concepts=["C-046"],
        prompt=(
            "Project: ai_editor. Tactical step: T-003. modify_file ai_editor/hooks_register.py.\n\n"
            "Post T-002 state registers session commands. Add file_open, file_close, file_get, "
            "file_send, file_create to _register without removing prior registrations.\n\n"
            f"Full content:\n\n```python\n{hr}```"
        ),
        vtype="import", vtarget="ai_editor.hooks_register",
        vexpected="Nine commands registered total (4 session + 5 file).",
    )
    all_ids.append(f"A-{pri:03d}")
    return all_ids


def gen_t004() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-004-history-commands"
    all_ids: list[str] = []
    pri = 1
    steps_prop = (
        '"steps": {"type": "integer", "default": 1, "minimum": 1, '
        '"description": "Number of history steps."}'
    )
    for cmd, api_fn in [("buf_undo", "undo"), ("buf_redo", "redo")]:
        props = f"{SESSION_KEY},\n        {BUFFER_ID},\n        {steps_prop}"
        exec_call = (
            f"api.{api_fn}(session_key=params['session_key'], "
            f"buffer_id=params['buffer_id'], steps=params.get('steps', 1))"
        )
        ids, pri = gen_command_triplet(
            ts, "T-004", cmd, start_priority=pri, api_fn=api_fn,
            schema_props=props, schema_required='"session_key", "buffer_id"',
            metadata_params=f"{SESSION_KEY},\n        {BUFFER_ID},",
            metadata_detailed=(
                f"History command {cmd}. Delegates to api.{api_fn} (G-006/T-010). "
                "UNDO_AT_BEGINNING / REDO_AT_END on boundary."
            ),
            execute_call=exec_call,
        )
        all_ids.extend(ids)
    write_hooks_update(
        ts, "T-004", pri, all_ids, "T-004", "update-hooks-register-history",
        "Register buf_undo and buf_redo; preserve all prior command registrations.",
    )
    return all_ids


def gen_t005() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-005-edit-commands"
    all_ids: list[str] = []
    pri = 1
    specs = [
        ("buf_copy", "copy", False, f"{SESSION_KEY},\n        {ADDRESS_SOURCE}",
         '"session_key", "source"',
         "api.copy(session_key=params['session_key'], source=params['source'])"),
        ("buf_cut", "cut", True,
         f"{SESSION_KEY},\n        {ADDRESS_SOURCE},\n        {DRY_RUN_PROP}",
         '"session_key", "source"',
         "api.cut(session_key=params['session_key'], source=params['source'], dry_run=params.get('dry_run', False))"),
        ("buf_paste", "paste", True,
         f"{SESSION_KEY},\n        {ADDRESS_TARGET},\n        {PASTE_MODE_ENUM},\n        {DRY_RUN_PROP}",
         '"session_key", "target", "mode"',
         "api.paste(session_key=params['session_key'], target=params['target'], mode=params['mode'], dry_run=params.get('dry_run', False))"),
    ]
    for cmd, api_fn, dry, props, req, exec_call in specs:
        ids, pri = gen_command_triplet(
            ts, "T-005", cmd, start_priority=pri, api_fn=api_fn,
            schema_props=props, schema_required=req,
            metadata_params=SESSION_KEY,
            metadata_detailed=f"Clipboard command {cmd} via api.{api_fn}.",
            execute_call=exec_call, dry_run=dry,
        )
        all_ids.extend(ids)
    write_hooks_update(
        ts, "T-005", pri, all_ids, "T-005", "update-hooks-register-edit",
        "Register buf_copy, buf_cut, buf_paste.",
    )
    return all_ids


def gen_t006() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-006-search-commands"
    all_ids: list[str] = []
    pri = 1
    scope_prop = '"scope": {"type": "string", "description": "Optional search scope."}'
    specs = [
        ("search_find", "find", True),
        ("search_find_one", "find_one", True),
        ("search_list_units", "list_units", False),
    ]
    for cmd, api_fn, with_query in specs:
        props = f"{SESSION_KEY},\n        {BUFFER_ID}"
        if with_query:
            props += f",\n        {QUERY_PROP}"
        props += f",\n        {scope_prop}"
        req = '"session_key", "buffer_id"' + (', "query"' if with_query else "")
        exec_call = (
            f"api.{api_fn}(session_key=params['session_key'], buffer_id=params['buffer_id']"
            + (", query=params['query']" if with_query else "")
            + ", scope=params.get('scope'))"
        )
        val = SEARCH_VALIDATE if with_query else ""
        ids, pri = gen_command_triplet(
            ts, "T-006", cmd, start_priority=pri, api_fn=api_fn,
            schema_props=props, schema_required=req,
            metadata_params=SESSION_KEY,
            metadata_detailed=f"Search command {cmd}; validate_query on query when present.",
            execute_call=exec_call,
            validate_extra=val,
            command_imports="from ai_editor import api\n        from ai_editor.search.query import validate_query",
        )
        all_ids.extend(ids)
    write_hooks_update(
        ts, "T-006", pri, all_ids, "T-006", "update-hooks-register-search",
        "Register search_find, search_find_one, search_list_units.",
    )
    return all_ids


def gen_t007() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-007-validation-commands"
    all_ids: list[str] = []
    pri = 1
    specs = [
        ("buf_validate", "validate_buffer", False,
         f"{SESSION_KEY},\n        {BUFFER_ID}",
         '"session_key", "buffer_id"',
         "api.validate_buffer(session_key=params['session_key'], buffer_id=params['buffer_id'])"),
        ("validate_file", "validate_file", False,
         f'{SESSION_KEY},\n        "file_path": {{"type": "string"}},\n        {BUFFER_ID},\n        "project_id": {{"type": "string"}},\n        "formatter": {{"type": "string", "default": "auto"}},\n        "schema": {{"type": "object"}}',
         '"session_key"',
         "api.validate_file(session_key=params['session_key'], file_path=params.get('file_path'), buffer_id=params.get('buffer_id'), project_id=params.get('project_id'), formatter=params.get('formatter','auto'), schema=params.get('schema'))"),
        ("formatter_commands", "formatter_commands", False,
         f'{BUFFER_ID},\n        "formatter": {{"type": "string"}}',
         "",
         "api.formatter_commands(buffer_id=params.get('buffer_id'), formatter=params.get('formatter'))"),
    ]
    for cmd, api_fn, dry, props, req, exec_call in specs:
        ids, pri = gen_command_triplet(
            ts, "T-007", cmd, start_priority=pri, api_fn=api_fn,
            schema_props=props, schema_required=req,
            metadata_params=SESSION_KEY,
            metadata_detailed=f"Validation/discovery command {cmd}.",
            execute_call=exec_call, dry_run=dry,
        )
        all_ids.extend(ids)
    write_hooks_update(
        ts, "T-007", pri, all_ids, "T-007", "update-hooks-register-validation",
        "Register buf_validate, validate_file, formatter_commands.",
    )
    return all_ids


def gen_t008() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-008-yaml-commands"
    all_ids: list[str] = []
    pri = 1
    specs = [
        ("yaml_get_command", "find_one", False,
         f"{SESSION_KEY},\n        {BUFFER_ID},\n        "
         '"command_name": {{"type": "string"}}',
         '"session_key", "buffer_id", "command_name"',
         "api.find_one(session_key=params['session_key'], buffer_id=params['buffer_id'], "
         "query={'kind': 'field_equals', 'field': 'name', 'value': params['command_name']})"),
        ("yaml_update_command", "mutate_batch", True,
         f"{SESSION_KEY},\n        {BUFFER_ID},\n        "
         '"command_name": {{"type": "string"}},\n        '
         '"patch": {{"type": "object"}},\n        {DRY_RUN_PROP}',
         '"session_key", "buffer_id", "command_name", "patch"',
         "api.mutate_batch(session_key=params['session_key'], buffer_id=params['buffer_id'], "
         "operations=[{'op': 'set', 'address': params['command_name'], 'value': v} "
         "for k, v in params['patch'].items()], dry_run=params.get('dry_run', False))"),
        ("yaml_get_verification", "find_one", False,
         f"{SESSION_KEY},\n        {BUFFER_ID}",
         '"session_key", "buffer_id"',
         "api.find_one(session_key=params['session_key'], buffer_id=params['buffer_id'], "
         "query={'kind': 'field_equals', 'field': 'verification', 'value': None})"),
        ("yaml_append_verification", "mutate_batch", True,
         f"{SESSION_KEY},\n        {BUFFER_ID},\n        "
         '"item": {},\n        "dedupe": {{"type": "boolean", "default": True}},\n        {DRY_RUN_PROP}',
         '"session_key", "buffer_id", "item"',
         "api.mutate_batch(session_key=params['session_key'], buffer_id=params['buffer_id'], "
         "operations=[{'op': 'append', 'address': 'verification', 'value': params['item']}], "
         "dry_run=params.get('dry_run', False))"),
        ("yaml_validate_plan_task", "validate_file", False,
         f'{SESSION_KEY},\n        {BUFFER_ID},\n        "file_path": {{"type": "string"}},\n        "project_id": {{"type": "string"}}',
         '"session_key"',
         "api.validate_file(session_key=params['session_key'], file_path=params.get('file_path'), "
         "buffer_id=params.get('buffer_id'), project_id=params.get('project_id'), "
         "formatter='yaml', schema={'format': 'plan_task_v1'})"),
    ]
    for cmd, api_fn, dry, props, req, exec_call in specs:
        ids, pri = gen_command_triplet(
            ts, "T-008", cmd, start_priority=pri, api_fn=api_fn,
            schema_props=props, schema_required=req,
            metadata_params=SESSION_KEY,
            metadata_detailed=f"YAML convenience command {cmd}.",
            execute_call=exec_call, dry_run=dry,
        )
        all_ids.extend(ids)
    write_hooks_update(
        ts, "T-008", pri, all_ids, "T-008", "update-hooks-register-yaml",
        "Register five yaml_* commands.",
    )
    return all_ids


def gen_t009() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-009-cli"
    write_as(
        ts, "A-001", "create-interfaces-init",
        parent_ts="T-009",
        name="Create ai_editor/interfaces/__init__.py",
        target_file="ai_editor/interfaces/__init__.py",
        operation="create_file", priority=1, depends_on=[], concepts=["C-048"],
        prompt=(
            "Project: ai_editor. Tactical step: T-009. "
            "File: ai_editor/interfaces/__init__.py. Operation: create_file.\n\n"
            "MRS C-048 CLIInterface package init.\n\n"
            "Create:\n\n```python\n"
            '"""CLI diagnostic interface."""\n\n__all__: list[str] = ["cli"]\n```'
        ),
        vtype="import", vtarget="ai_editor.interfaces",
        vexpected="Package imports without error.",
    )
    write_as(
        ts, "A-002", "create-cli-py",
        parent_ts="T-009",
        name="Create ai_editor/interfaces/cli.py",
        target_file="ai_editor/interfaces/cli.py",
        operation="create_file", priority=2, depends_on=[], concepts=["C-048", "C-047"],
        prompt=(
            "Project: ai_editor. Tactical step: T-009. "
            "File: ai_editor/interfaces/cli.py. Operation: create_file.\n\n"
            "MRS C-048: argparse CLI with ten subcommands. Imports ONLY api_init.init_api "
            "and ai_editor.api (never session layer). session_key flag is --session-key.\n"
            "Requires G-006/T-010 api.py and api_init.py.\n"
            "init_api() once before dispatch. api functions synchronous (no asyncio.run).\n"
            "JSON stdout on success; stderr + exit 1 on error. No save_always.\n\n"
            f"Create with exact content:\n\n```python\n{CLI_PY}```"
        ),
        vtype="import", vtarget="ai_editor.interfaces.cli",
        vexpected="main() defined; ten subcommands; uses --session-key not --session-id.",
    )
    return ["A-001", "A-002"]


def gen_t010() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-010-api-facade"
    write_as(
        ts, "A-001", "create-session-manager-py",
        parent_ts="T-010",
        name="Create ai_editor/session_manager.py",
        target_file="ai_editor/session_manager.py",
        operation="create_file", priority=1, depends_on=[], concepts=["C-047"],
        prompt=(
            "Project: ai_editor. Tactical step: T-010. "
            "File: ai_editor/session_manager.py. Operation: create_file.\n\n"
            "MRS C-047 ApiFacade: SessionManager holds base_dir, ca_client, formatter_registry, "
            "repo_map. All methods synchronous; delegate to G-005 session layer only.\n"
            "mutate_batch: formatter.mutate_batch then execute_mutation; atomic on raise.\n"
            "No singleton state. Under 400 lines.\n\n"
            f"Create with exact content:\n\n```python\n{SESSION_MANAGER_PY}```"
        ),
        vtype="import", vtarget="ai_editor.session_manager.SessionManager",
        vexpected="SessionManager has connect, open_buffer, undo, mutate_batch methods.",
    )
    write_as(
        ts, "A-002", "create-api-init-py",
        parent_ts="T-010",
        name="Create ai_editor/api_init.py",
        target_file="ai_editor/api_init.py",
        operation="create_file", priority=2, depends_on=["A-001"], concepts=["C-047"],
        prompt=(
            "Project: ai_editor. Tactical step: T-010. "
            "File: ai_editor/api_init.py. Operation: create_file.\n\n"
            "Module singletons _ca_client, _session_manager. init_api builds both and "
            "runs startup_sweep once. get_* raise RuntimeError if not initialised.\n\n"
            f"Create with exact content:\n\n```python\n{API_INIT_PY}```"
        ),
        vtype="import", vtarget="ai_editor.api_init",
        vexpected="init_api and get_session_manager importable.",
    )
    write_as(
        ts, "A-003", "create-api-py",
        parent_ts="T-010",
        name="Create ai_editor/api.py",
        target_file="ai_editor/api.py",
        operation="create_file", priority=3, depends_on=["A-002"], concepts=["C-047"],
        prompt=(
            "Project: ai_editor. Tactical step: T-010. "
            "File: ai_editor/api.py. Operation: create_file.\n\n"
            "Thin module-level wrappers delegating to get_session_manager(). "
            "No classes, no singleton state, no G-005 direct imports. "
            "Includes mutate_batch and dry_run passthrough on destructive ops.\n\n"
            f"Create with exact content:\n\n```python\n{API_PY}```"
        ),
        vtype="import", vtarget="ai_editor.api",
        vexpected="connect, undo, mutate_batch, find importable one-liner wrappers.",
    )
    return ["A-001", "A-002", "A-003"]


def gen_t011() -> list[str]:
    ts = PLAN / "G-006-command-layer/T-011-buffer-extended-commands"
    all_ids: list[str] = []
    pri = 1
    ops_schema = (
        '"operations": {"type": "array", "items": {"type": "object", '
        '"properties": {"op": {"type": "string"}, "address": {}, "value": {}}, '
        '"required": ["op", "address"]}}'
    )
    specs = [
        ("buf_new", "new_buffer", False,
         f'{SESSION_KEY},\n        "formatter": {{"type": "string", "default": "auto"}},\n        "content": {{"type": "string", "default": ""}},\n        "display_name": {{"type": "string"}}',
         '"session_key"',
         "api.new_buffer(session_key=params['session_key'], formatter_name=params.get('formatter','auto'), initial_content=params.get('content',''), display_name=params.get('display_name'))"),
        ("buf_save_as", "save_as_buffer", True,
         f'{SESSION_KEY},\n        {BUFFER_ID},\n        "new_relative_path": {{"type": "string"}},\n        "overwrite": {{"type": "boolean", "default": False}},\n        {DRY_RUN_PROP}',
         '"session_key", "buffer_id", "new_relative_path"',
         "api.save_as_buffer(session_key=params['session_key'], buffer_id=params['buffer_id'], new_relative_path=params['new_relative_path'], overwrite=params.get('overwrite',False), dry_run=params.get('dry_run',False))"),
        ("buf_reload", "reload_buffer", False,
         f"{SESSION_KEY},\n        {BUFFER_ID}",
         '"session_key", "buffer_id"',
         "api.reload_buffer(session_key=params['session_key'], buffer_id=params['buffer_id'])"),
        ("buf_get_state", "get_buffer_state", False,
         f"{SESSION_KEY},\n        {BUFFER_ID}",
         '"session_key", "buffer_id"',
         "api.get_buffer_state(session_key=params['session_key'], buffer_id=params['buffer_id'])"),
        ("buf_write_all", "write_all", True,
         f'{SESSION_KEY},\n        "force": {{"type": "boolean", "default": False}},\n        {DRY_RUN_PROP}',
         '"session_key"',
         "api.write_all(session_key=params['session_key'], force=params.get('force',False), dry_run=params.get('dry_run',False))"),
        ("buf_mutate_batch", "mutate_batch", True,
         f"{SESSION_KEY},\n        {BUFFER_ID},\n        {ops_schema},\n        {DRY_RUN_PROP}",
         '"session_key", "buffer_id", "operations"',
         "api.mutate_batch(session_key=params['session_key'], buffer_id=params['buffer_id'], operations=params['operations'], dry_run=params.get('dry_run',False))"),
    ]
    for cmd, api_fn, dry, props, req, exec_call in specs:
        ids, pri = gen_command_triplet(
            ts, "T-011", cmd, start_priority=pri, api_fn=api_fn,
            schema_props=props, schema_required=req,
            metadata_params=SESSION_KEY,
            metadata_detailed=f"Extended buffer command {cmd}.",
            execute_call=exec_call, dry_run=dry,
            concepts=["C-010", "C-011", "C-013", "C-045", "C-047"],
        )
        all_ids.extend(ids)
    write_hooks_update(
        ts, "T-011", pri, all_ids, "T-011", "update-hooks-register-buf-extended",
        "Register buf_new, buf_save_as, buf_reload, buf_get_state, buf_write_all, buf_mutate_batch.",
    )
    return all_ids


def gen_g007_t001() -> list[str]:
    ts = PLAN / "G-007-adapter-integration/T-001-main-startup"
    write_as(
        ts, "A-001", "create-main-py",
        parent_ts="T-001",
        name="Create ai_editor/main.py",
        target_file="ai_editor/main.py",
        operation="create_file", priority=1, depends_on=[], concepts=["C-049", "C-050"],
        prompt=(
            "Project: ai_editor. Tactical step: G-007/T-001. "
            "File: ai_editor/main.py. Operation: create_file.\n\n"
            "Six-step startup: (1) SimpleConfig.load (2) AiEditorConfigValidator.validate "
            "(3) init_api from api_init (4) create_app (5) register_custom_commands_hook "
            "(6) UnifiedServerRunner.run_server. Never implement HTTP routes.\n\n"
            f"Create with exact content:\n\n```python\n{MAIN_PY}```"
        ),
        vtype="import", vtarget="ai_editor.main",
        vexpected="main() performs validate before init_api and create_app.",
    )
    return ["A-001"]


def gen_g007_t002() -> list[str]:
    ts = PLAN / "G-007-adapter-integration/T-002-config-integration"
    write_as(
        ts, "A-001", "test-config-integration",
        parent_ts="T-002",
        name="Create tests/integration/test_config_integration.py",
        target_file="tests/integration/test_config_integration.py",
        operation="create_file", priority=1, depends_on=[], concepts=["C-049", "C-018"],
        prompt=(
            "Project: ai_editor. Tactical step: G-007/T-002. "
            "File: tests/integration/test_config_integration.py. Operation: create_file.\n\n"
            "Integration tests only — no production code. Verify AiEditorConfig defaults, "
            "from_config_json, validator list return, and main.py validates before from_config_json.\n\n"
            f"Create with exact content:\n\n```python\n{TEST_CONFIG_INTEGRATION_PY}```"
        ),
        vtype="pytest",
        vtarget="tests/integration/test_config_integration.py",
        vexpected="pytest passes; main source order check passes.",
    )
    return ["A-001"]


def gen_g007_t003() -> list[str]:
    ts = PLAN / "G-007-adapter-integration/T-003-generator-integration"
    write_as(
        ts, "A-001", "test-generator-integration",
        parent_ts="T-003",
        name="Create tests/integration/test_config_generator_integration.py",
        target_file="tests/integration/test_config_generator_integration.py",
        operation="create_file", priority=1, depends_on=[], concepts=["C-051", "C-019"],
        prompt=(
            "Project: ai_editor. Tactical step: G-007/T-003. "
            "File: tests/integration/test_config_generator_integration.py. Operation: create_file.\n\n"
            "Round-trip: generate config, no .tmp left, validator passes, invalid kwargs raise "
            "ConfigGenerationError without .tmp file.\n\n"
            f"Create with exact content:\n\n```python\n{TEST_GENERATOR_INTEGRATION_PY}```"
        ),
        vtype="pytest",
        vtarget="tests/integration/test_config_generator_integration.py",
        vexpected="pytest passes for generate and invalid kwargs cases.",
    )
    return ["A-001"]


def gen_g007_t004() -> list[str]:
    ts = PLAN / "G-007-adapter-integration/T-004-aiedmgr"
    write_as(
        ts, "A-001", "create-aiedmgr",
        parent_ts="T-004",
        name="Create scripts/aiedmgr",
        target_file="scripts/aiedmgr",
        operation="create_file", priority=1, depends_on=[], concepts=["C-051", "C-018", "C-019"],
        prompt=(
            "Project: ai_editor. Tactical step: G-007/T-004. "
            "File: scripts/aiedmgr. Operation: create_file.\n\n"
            "Five subcommands: start, stop, status, restart, generate-config. "
            "start validates SimpleConfig.load().raw via AiEditorConfigValidator before Popen. "
            "PID file ai_editor.pid; log logs/ai_editor.log; 30s SIGTERM then SIGKILL.\n\n"
            f"Create with exact content:\n\n```python\n{AIEDMGR_PY}```"
        ),
        vtype="manual",
        vtarget="scripts/aiedmgr",
        vexpected="Script executable; start/stop/status subcommands present.",
    )
    return ["A-001"]


TS_README_PATHS: dict[str, str] = {
    "T-001": "G-006-command-layer/T-001-command-base-hooks/README.yaml",
    "T-002": "G-006-command-layer/T-002-session-commands/README.yaml",
    "T-003": "G-006-command-layer/T-003-buffer-commands/README.yaml",
    "T-004": "G-006-command-layer/T-004-history-commands/README.yaml",
    "T-005": "G-006-command-layer/T-005-edit-commands/README.yaml",
    "T-006": "G-006-command-layer/T-006-search-commands/README.yaml",
    "T-007": "G-006-command-layer/T-007-validation-commands/README.yaml",
    "T-008": "G-006-command-layer/T-008-yaml-commands/README.yaml",
    "T-009": "G-006-command-layer/T-009-cli/README.yaml",
    "T-010": "G-006-command-layer/T-010-api-facade/README.yaml",
    "T-011": "G-006-command-layer/T-011-buffer-extended-commands/README.yaml",
    "G-007-T-001": "G-007-adapter-integration/T-001-main-startup/README.yaml",
    "G-007-T-002": "G-007-adapter-integration/T-002-config-integration/README.yaml",
    "G-007-T-003": "G-007-adapter-integration/T-003-generator-integration/README.yaml",
    "G-007-T-004": "G-007-adapter-integration/T-004-aiedmgr/README.yaml",
}


def update_readme_atomic_steps(generated: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    for key, step_ids in generated.items():
        rel = TS_README_PATHS.get(key)
        if not rel:
            errors.append(f"no README path for {key}")
            continue
        path = PLAN / rel
        if not path.exists():
            errors.append(f"README missing: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        new_list = "atomic_steps:\n" + "".join(f"- {s}\n" for s in step_ids)
        text2, n = re.subn(r"atomic_steps:\s*\[\]\s*", new_list, text, count=1)
        if n == 0:
            text2, n = re.subn(
                r"atomic_steps:.*?(?=\ncascade_note:|\nstatus:|\Z)",
                new_list,
                text,
                count=1,
                flags=re.S,
            )
        if n == 0:
            errors.append(f"atomic_steps not updated in {path}")
            continue
        path.write_text(text2, encoding="utf-8")
    return errors


def main() -> None:
    generated: dict[str, list[str]] = {}
    errors: list[str] = []
    generators = [
        ("T-001", gen_t001),
        ("T-002", gen_t002),
        ("T-003", gen_t003),
        ("T-004", gen_t004),
        ("T-005", gen_t005),
        ("T-006", gen_t006),
        ("T-007", gen_t007),
        ("T-008", gen_t008),
        ("T-009", gen_t009),
        ("T-010", gen_t010),
        ("T-011", gen_t011),
        ("G-007-T-001", gen_g007_t001),
        ("G-007-T-002", gen_g007_t002),
        ("G-007-T-003", gen_g007_t003),
        ("G-007-T-004", gen_g007_t004),
    ]
    for key, fn in generators:
        try:
            generated[key] = fn()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{key}: {exc}")
    readme_errors = update_readme_atomic_steps(generated)
    errors.extend(readme_errors)
    total = sum(len(v) for v in generated.values())
    print(f"Generated {total} AS files")
    for k, v in sorted(generated.items()):
        print(f"  {k}: {len(v)} steps")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("No errors.")


if __name__ == "__main__":
    main()
