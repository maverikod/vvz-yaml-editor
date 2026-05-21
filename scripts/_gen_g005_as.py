#!/usr/bin/env python3
"""Generate G-005 session-layer atomic step YAML files. Run with project venv python."""
from __future__ import annotations

import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _g005_modules import (
    BUFFER_CLOSE_PY,
    BUFFER_MUTATION_PY,
    BUFFER_NEW_PY,
    BUFFER_OPEN_PY,
    BUFFER_RELOAD_PY,
    BUFFER_SAVE_PY,
    CLIPBOARD_PY,
    RECOVERY_PY,
    SESSION_API_PY,
    SESSION_DIR_PY,
    SESSION_GIT_PY,
    SESSIONS_INIT_EXPORTS,
    SESSIONS_INIT_MINIMAL,
    UNDO_REDO_PY,
    WRITE_ALL_PY,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/plans/ai_editor"
G5 = "G-005-session-layer"

MRS: dict[str, str] = {
    "C-010": (
        "C-010 Buffer: one file + one formatter for buffer lifetime; buffer_id and "
        "formatter immutable after open; fields include modified, readonly, buf_file_path."
    ),
    "C-032": (
        "C-032 Sidecar: session <session_dir>/<buffer_id>.tree; project <dir>/.tree/<stem>.tree; "
        "header TREE_V1 fmt=<formatter> sha256=<source> tree_sha256=<tree>; written after "
        "every mutation once modified=True (SourceOfTruth)."
    ),
    "C-008": (
        "C-008 SessionDescriptor: session_key, open_buffers list[BufferDescriptor], "
        "diagnostics; returned by connect/reconnect/session_status."
    ),
    "C-038": (
        "C-038 Session: buffers share session_dir + session git + clipboard; external "
        "CASession (ca_session_id) — never session_create/delete; canonical id session_key."
    ),
    "C-039": (
        "C-039 SessionDirectory: <sessions_base_dir>/<session_key>/ with ses_settings.json, "
        "git/, buffer files, clipboard.json; exists iff directory exists."
    ),
    "C-040": (
        "C-040 SessionGit: non-bare repo at <session_dir>/git/; branch buf/<buffer_id>; "
        "commit on mutation and clipboard cut/paste; undo via commits + redo_stack."
    ),
    "C-041": (
        "C-041 Clipboard: <session_dir>/clipboard.json {formatter, body, source_revision, "
        "paste_policy}; copy does not modify buffer; cut/paste use write-then-commit."
    ),
    "C-042": (
        "C-042 SessionAttributes: ses_settings.json — session_key, created_at, readonly, "
        "ca_session_id, open_buffers (buf_dict with redo_stack per buffer)."
    ),
    "C-043": (
        "C-043 BufferFile: session working copy at <session_dir>/<buffer_id>.<ext>; "
        "full source via write_buf after every mutation."
    ),
    "C-044": (
        "C-044 StartupSweep: policy B — delete orphan dirs (missing/corrupt ses_settings); "
        "release stale locks on valid dirs via unlock_file; no TTL."
    ),
    "C-062": (
        "C-062 CASession: external ca_session_id at connect; used for lock_file/unlock_file; "
        "stored in ses_settings.json; ai_editor never owns CA session lifecycle."
    ),
    "C-066": (
        "C-066 SourceOfTruth: source file at open; tree sidecar authoritative once "
        "buffer.modified=True (all formats)."
    ),
    "C-067": (
        "C-067 AutoCreateTree: formatter.open_tree immediately after CA fetch and when "
        "preview would miss tree file."
    ),
    "C-021": (
        "C-021 AbstractFormatter: open_tree, export, render_skeleton, structural mutations, "
        "write pipeline; produces Sidecar (C-032)."
    ),
    "C-068": (
        "C-068 WritePipeline: export, diff preview, temp write, linters, atomic rename; "
        "session save uses run_save_pipeline after formatter export."
    ),
}

IMPORTS_BLOCK = """\
Preconditions (modules from G-001/G-002/G-003 — do not open other repo files):
  from ai_editor.contracts import (
      BufferDescriptor, Diagnostic, ErrorCode, OperationResult,
      SessionDescriptor, WriteAllResult,
  )
  from ai_editor.editor_core.ca_client import CodeAnalysisClient
  from ai_editor.editor_core.registry import FormatterRegistry
  from ai_editor.editor_core.save_pipeline import run_save_as_pipeline, run_save_pipeline, run_validate
  from ai_editor.editor_core.writer import Writer
  from ai_editor.formatters.base import AbstractFormatter
  from ai_editor.formatters.sidecar import save_sidecar, session_sidecar_path
  ErrorCode: use UNDO_NOT_AVAILABLE / REDO_NOT_AVAILABLE for undo/redo limits (not SEARCH_*).
  Git failures: append Diagnostic(code='HISTORY_UNAVAILABLE', message=...) — not ErrorCode enum.
"""


def yaml_block(d: dict) -> str:
    import yaml

    return yaml.dump(d, sort_keys=False, allow_unicode=True, width=1000)


def write_as(rel_path: str, data: dict) -> Path:
    path = PLAN / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_block(data), encoding="utf-8")
    print("wrote", path)
    return path


def update_ts_atomic(ts_rel: str, step_ids: list[str]) -> Path:
    path = PLAN / ts_rel
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
        raise RuntimeError(f"atomic_steps not updated in {path}")
    path.write_text(text2, encoding="utf-8")
    print("updated TS", path)
    return path


def mrs_block(concept_ids: list[str]) -> str:
    return "MRS:\n" + "\n".join(f"  {MRS[cid]}" for cid in concept_ids) + "\n\n"


def prompt_create(
    ts: str,
    path: str,
    code: str,
    concepts: list[str],
    extra: str = "",
) -> str:
    return (
        f"Project: ai_editor. Parent: G-005/{ts}. File: {path}. Operation: create_file.\n\n"
        + mrs_block(concepts)
        + IMPORTS_BLOCK
        + extra
        + f"\nCreate parent package directories if missing. Create {path} with exactly:\n\n"
        f"```python\n{code}\n```\n"
    )


def prompt_modify(
    ts: str,
    path: str,
    current: str,
    new_code: str,
    concepts: list[str],
    extra: str = "",
) -> str:
    return (
        f"Project: ai_editor. Parent: G-005/{ts}. File: {path}. Operation: modify_file.\n\n"
        + mrs_block(concepts)
        + IMPORTS_BLOCK
        + extra
        + "\nCurrent file content:\n\n```python\n"
        + current
        + "\n```\n\nReplace entire file with:\n\n```python\n"
        + new_code
        + "\n```\n"
    )


def as_create(
    ts_slug: str,
    ts_id: str,
    step: str,
    slug: str,
    target: str,
    code: str,
    concepts: list[str],
    verification: dict,
    extra: str = "",
    priority: int = 1,
    depends_on: list[str] | None = None,
) -> Path:
    rel = f"{G5}/{ts_slug}/atomic_steps/{step}-{slug}.yaml"
    return write_as(
        rel,
        {
            "step_id": step,
            "parent_tactical_step": ts_id,
            "name": f"Create {target}",
            "target_file": target,
            "operation": "create_file",
            "priority": priority,
            "depends_on": depends_on or [],
            "concepts": concepts,
            "status": "draft",
            "prompt": prompt_create(ts_id, target, code, concepts, extra),
            "verification": verification,
        },
    )


def as_modify(
    ts_slug: str,
    ts_id: str,
    step: str,
    slug: str,
    target: str,
    current: str,
    new_code: str,
    concepts: list[str],
    verification: dict,
    extra: str = "",
    priority: int = 2,
    depends_on: list[str] | None = None,
) -> Path:
    rel = f"{G5}/{ts_slug}/atomic_steps/{step}-{slug}.yaml"
    return write_as(
        rel,
        {
            "step_id": step,
            "parent_tactical_step": ts_id,
            "name": f"Modify {target}",
            "target_file": target,
            "operation": "modify_file",
            "priority": priority,
            "depends_on": depends_on or [],
            "concepts": concepts,
            "status": "draft",
            "prompt": prompt_modify(ts_id, target, current, new_code, concepts, extra),
            "verification": verification,
        },
    )


def generate_g005() -> tuple[list[Path], list[Path]]:
    created: list[Path] = []
    ts_updated: list[Path] = []

    # T-001
    created.append(
        as_create(
            "T-001-session-dir",
            "T-001",
            "A-001",
            "session-dir-py",
            "ai_editor/sessions/session_dir.py",
            SESSION_DIR_PY,
            ["C-039", "C-042"],
            {
                "type": "import",
                "target": "ai_editor.sessions.session_dir",
                "expected": "create_session_dir, read_session_settings, write_session_settings, add_buffer_to_settings import.",
            },
        )
    )
    created.append(
        as_create(
            "T-001-session-dir",
            "T-001",
            "A-002",
            "sessions-init-py",
            "ai_editor/sessions/__init__.py",
            SESSIONS_INIT_MINIMAL,
            ["C-038"],
            {
                "type": "import",
                "target": "ai_editor.sessions",
                "expected": "Package imports without error; minimal module docstring only.",
            },
            extra="T-001: package docstring only. Public exports added in T-013.\n",
        )
    )
    ts_updated.append(
        update_ts_atomic(f"{G5}/T-001-session-dir/README.yaml", ["A-001", "A-002"])
    )

    # T-002
    created.append(
        as_create(
            "T-002-session-git",
            "T-002",
            "A-001",
            "session-git-py",
            "ai_editor/sessions/session_git.py",
            SESSION_GIT_PY,
            ["C-040"],
            {
                "type": "import",
                "target": "ai_editor.sessions.session_git",
                "expected": "init_session_git, get_repo, create_buffer_branch, commit_buffer, delete_buffer_branch import.",
            },
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-002-session-git/README.yaml", ["A-001"]))

    # T-003
    created.append(
        as_create(
            "T-003-buffer-open",
            "T-003",
            "A-001",
            "buffer-open-py",
            "ai_editor/sessions/buffer_open.py",
            BUFFER_OPEN_PY,
            ["C-010", "C-038", "C-062", "C-066", "C-067", "C-032", "C-021"],
            {
                "type": "import",
                "target": "ai_editor.sessions.buffer_open",
                "expected": "open_buffer function imports; signature matches TS README.",
            },
            extra=(
                "G-005 executor_brief: sidecar session_path <session_dir>/<buffer_id>.tree; "
                "AutoCreateTree after CA fetch via formatter.open_tree.\n"
            ),
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-003-buffer-open/README.yaml", ["A-001"]))

    # T-004
    created.append(
        as_create(
            "T-004-buffer-new",
            "T-004",
            "A-001",
            "buffer-new-py",
            "ai_editor/sessions/buffer_new.py",
            BUFFER_NEW_PY,
            ["C-038", "C-010", "C-043"],
            {
                "type": "import",
                "target": "ai_editor.sessions.buffer_new",
                "expected": "create_new_buffer imports.",
            },
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-004-buffer-new/README.yaml", ["A-001"]))

    # T-005
    created.append(
        as_create(
            "T-005-buffer-mutation",
            "T-005",
            "A-001",
            "buffer-mutation-py",
            "ai_editor/sessions/buffer_mutation.py",
            BUFFER_MUTATION_PY,
            ["C-010", "C-038", "C-066", "C-032", "C-021"],
            {
                "type": "import",
                "target": "ai_editor.sessions.buffer_mutation",
                "expected": "execute_mutation imports.",
            },
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-005-buffer-mutation/README.yaml", ["A-001"]))

    # T-006
    created.append(
        as_create(
            "T-006-buffer-save",
            "T-006",
            "A-001",
            "buffer-save-py",
            "ai_editor/sessions/buffer_save.py",
            BUFFER_SAVE_PY,
            ["C-010", "C-068", "C-032", "C-021"],
            {
                "type": "import",
                "target": "ai_editor.sessions.buffer_save",
                "expected": "save_buffer and save_as_buffer import.",
            },
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-006-buffer-save/README.yaml", ["A-001"]))

    # T-007
    created.append(
        as_create(
            "T-007-buffer-reload",
            "T-007",
            "A-001",
            "buffer-reload-py",
            "ai_editor/sessions/buffer_reload.py",
            BUFFER_RELOAD_PY,
            ["C-010", "C-067", "C-021", "C-032"],
            {
                "type": "import",
                "target": "ai_editor.sessions.buffer_reload",
                "expected": "reload_buffer imports.",
            },
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-007-buffer-reload/README.yaml", ["A-001"]))

    # T-008
    created.append(
        as_create(
            "T-008-buffer-close",
            "T-008",
            "A-001",
            "buffer-close-py",
            "ai_editor/sessions/buffer_close.py",
            BUFFER_CLOSE_PY,
            ["C-038", "C-010"],
            {
                "type": "import",
                "target": "ai_editor.sessions.buffer_close",
                "expected": "close_buffer and close_session import.",
            },
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-008-buffer-close/README.yaml", ["A-001"]))

    # T-009
    created.append(
        as_create(
            "T-009-undo-redo",
            "T-009",
            "A-001",
            "undo-redo-py",
            "ai_editor/sessions/undo_redo.py",
            UNDO_REDO_PY,
            ["C-040", "C-042"],
            {
                "type": "import",
                "target": "ai_editor.sessions.undo_redo",
                "expected": "undo, redo, buf_history, buf_checkout, buf_diff import.",
            },
            extra="Use ErrorCode.UNDO_NOT_AVAILABLE and REDO_NOT_AVAILABLE per G-001.\n",
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-009-undo-redo/README.yaml", ["A-001"]))

    # T-010
    created.append(
        as_create(
            "T-010-clipboard",
            "T-010",
            "A-001",
            "clipboard-py",
            "ai_editor/sessions/clipboard.py",
            CLIPBOARD_PY,
            ["C-041"],
            {
                "type": "import",
                "target": "ai_editor.sessions.clipboard",
                "expected": "copy_to_clipboard, cut_to_clipboard, paste_from_clipboard import.",
            },
            extra="copy: no write_buf, no commit_buffer per T-010 README.\n",
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-010-clipboard/README.yaml", ["A-001"]))

    # T-011
    created.append(
        as_create(
            "T-011-write-all",
            "T-011",
            "A-001",
            "write-all-py",
            "ai_editor/sessions/write_all.py",
            WRITE_ALL_PY,
            ["C-038", "C-010"],
            {
                "type": "import",
                "target": "ai_editor.sessions.write_all",
                "expected": "write_all imports; returns WriteAllResult.",
            },
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-011-write-all/README.yaml", ["A-001"]))

    # T-012
    created.append(
        as_create(
            "T-012-session-recovery",
            "T-012",
            "A-001",
            "recovery-py",
            "ai_editor/sessions/recovery.py",
            RECOVERY_PY,
            ["C-038", "C-039", "C-044"],
            {
                "type": "import",
                "target": "ai_editor.sessions.recovery",
                "expected": "startup_sweep, reconnect_session, release_all_locks_for_session import.",
            },
            extra="Use ca_client.unlock_file (not advisory_unlock alias).\n",
        )
    )
    ts_updated.append(update_ts_atomic(f"{G5}/T-012-session-recovery/README.yaml", ["A-001"]))

    # T-013
    created.append(
        as_create(
            "T-013-public-api",
            "T-013",
            "A-001",
            "session-api-py",
            "ai_editor/sessions/session_api.py",
            SESSION_API_PY,
            ["C-038", "C-008"],
            {
                "type": "import",
                "target": "ai_editor.sessions.session_api",
                "expected": "connect, reconnect, close_session_api, session_status import.",
            },
            extra="connect has no save_always; close_session_api has no project_id param.\n",
        )
    )
    created.append(
        as_modify(
            "T-013-public-api",
            "T-013",
            "A-002",
            "sessions-init-exports",
            "ai_editor/sessions/__init__.py",
            SESSIONS_INIT_MINIMAL,
            SESSIONS_INIT_EXPORTS,
            ["C-038", "C-008"],
            {
                "type": "import",
                "target": "ai_editor.sessions",
                "expected": "from ai_editor.sessions import connect, reconnect, close_session_api, session_status succeeds.",
            },
            depends_on=["A-001"],
        )
    )
    ts_updated.append(
        update_ts_atomic(f"{G5}/T-013-public-api/README.yaml", ["A-001", "A-002"])
    )

    return created, ts_updated


if __name__ == "__main__":
    paths, ts_paths = generate_g005()
    print(f"G-005 done: {len(paths)} AS files, {len(ts_paths)} TS READMEs updated")
