#!/usr/bin/env python3
"""sync_ported.py - update ai_editor/ported/ from code_analysis.

Usage: python scripts/sync_ported.py
"""
import hashlib
import shutil
from pathlib import Path

SRC = Path("/home/vasilyvz/projects/tools/code_analysis/code_analysis")
DST = Path("/home/vasilyvz/projects/tools/ai_editor/ai_editor/ported")

FILES = [
    ("core/backup_manager.py",                               "backup_manager.py"),
    ("core/file_handlers/__init__.py",                       "file_handlers/__init__.py"),
    ("core/file_handlers/base.py",                           "file_handlers/base.py"),
    ("core/file_handlers/diff_support.py",                   "file_handlers/diff_support.py"),
    ("core/file_handlers/json_handler.py",                   "file_handlers/json_handler.py"),
    ("core/file_handlers/path_utils.py",                     "file_handlers/path_utils.py"),
    ("core/file_handlers/python_handler.py",                 "file_handlers/python_handler.py"),
    ("core/file_handlers/registry.py",                       "file_handlers/registry.py"),
    ("core/file_handlers/text_handler.py",                   "file_handlers/text_handler.py"),
    ("core/file_handlers/text_ranges.py",                    "file_handlers/text_ranges.py"),
    ("core/file_handlers/yaml_handler.py",                   "file_handlers/yaml_handler.py"),
    ("commands/universal_file_edit/__init__.py",              "universal_file_edit/__init__.py"),
    ("commands/universal_file_edit/close_command.py",         "universal_file_edit/close_command.py"),
    ("commands/universal_file_edit/edit_command.py",          "universal_file_edit/edit_command.py"),
    ("commands/universal_file_edit/edit_draft_path_utils.py", "universal_file_edit/edit_draft_path_utils.py"),
    ("commands/universal_file_edit/errors.py",                "universal_file_edit/errors.py"),
    ("commands/universal_file_edit/format_group.py",          "universal_file_edit/format_group.py"),
    ("commands/universal_file_edit/open_command.py",          "universal_file_edit/open_command.py"),
    ("commands/universal_file_edit/session.py",               "universal_file_edit/session.py"),
    ("commands/universal_file_edit/sha_sync_policy.py",       "universal_file_edit/sha_sync_policy.py"),
    ("commands/universal_file_edit/sidecar_cst_apply.py",     "universal_file_edit/sidecar_cst_apply.py"),
    ("commands/universal_file_edit/text_draft_apply.py",      "universal_file_edit/text_draft_apply.py"),
    ("commands/universal_file_edit/tree_temp_edit_batch.py",  "universal_file_edit/tree_temp_edit_batch.py"),
    ("commands/universal_file_edit/tree_temp_edit_nodes.py",  "universal_file_edit/tree_temp_edit_nodes.py"),
    ("commands/universal_file_edit/tree_temp_legacy_apply.py","universal_file_edit/tree_temp_legacy_apply.py"),
    ("commands/universal_file_edit/tree_temp_open_support.py","universal_file_edit/tree_temp_open_support.py"),
    ("commands/universal_file_edit/tree_temp_write_commit.py","universal_file_edit/tree_temp_write_commit.py"),
    ("commands/universal_file_edit/write_command.py",         "universal_file_edit/write_command.py"),
]


def sha256(p: Path) -> str:
    """Return SHA-256 hex digest of file content."""
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    """Copy changed files from code_analysis into ported/."""
    new = upd = ok = miss = 0
    for src_rel, dst_rel in FILES:
        src = SRC / src_rel
        dst = DST / dst_rel
        if not src.exists():
            print(f"MISS  {src_rel}")
            miss += 1
            continue
        if dst.exists() and sha256(src) == sha256(dst):
            print(f"OK    {dst_rel}")
            ok += 1
            continue
        tag = "UPD" if dst.exists() else "NEW"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"{tag}   {dst_rel}")
        if tag == "UPD":
            upd += 1
        else:
            new += 1
    print(f"\nResult: {new} new, {upd} updated, {ok} unchanged, {miss} missing")


if __name__ == "__main__":
    main()
