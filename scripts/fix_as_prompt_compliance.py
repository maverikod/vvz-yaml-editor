#!/usr/bin/env python3
"""Batch-fix common a5/a2 prompt violations in G-003..G-007 atomic steps."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PLAN = Path(__file__).resolve().parents[1] / "docs/plans/ai_editor"
GROUPS = [
    "G-003-formatters", "G-004-search", "G-005-session-layer",
    "G-006-command-layer", "G-007-adapter-integration",
]

REPLACEMENTS = [
    (re.compile(r"\bG-\d{3}/T-\d{3}\b"), "parent tactical step"),
    (re.compile(r"\bG-\d{3}\b(?=/T-)"), "parent global step"),
    (re.compile(r"\bprior\s+A-\d{3}\b", re.I), "lower-priority changes on this file"),
    (re.compile(r"\bafter\s+A-\d{3}\b", re.I), "after lower-priority changes on this file"),
    (re.compile(r"\bpost[- ]A-\d{3}\b", re.I), "post lower-priority state"),
    (re.compile(r"\(after\s+[^)]*A-\d{3}[^)]*\)", re.I), "(inlined post-prior state below)"),
    (re.compile(r"until\s+T-\d{3}\b", re.I), "until catalog module exists"),
    (re.compile(r"do not open (?:those )?modules?", re.I),
     "Use only the inlined excerpts below, not live imports from the codebase."),
    (re.compile(r"do not open files?", re.I),
     "Use only the inlined excerpts below, not live imports from the codebase."),
    (re.compile(r"do not open\b", re.I),
     "Use only the inlined excerpt below, not live imports from the codebase."),
    (re.compile(r"Dependency \(inline API from [^)]+\):", re.I),
     "Inlined API excerpt:"),
    (re.compile(r"inline — do not open[^:]*:", re.I),
     "inlined API excerpt:"),
]

# Remove bare A-NNN in prompt body (keep yaml depends_on)
A_IN_PROMPT = re.compile(r"(?m)(^|\s)A-\d{3}\b")


def fix_prompt(text: str) -> str:
    for pat, repl in REPLACEMENTS:
        text = pat.sub(repl, text)
    # drop standalone step id mentions in prose
    text = A_IN_PROMPT.sub(r"\1", text)
    return text


def main() -> None:
    changed = 0
    for g in GROUPS:
        for path in sorted((PLAN / g).glob("T-*/atomic_steps/A-*.yaml")):
            data = yaml.safe_load(path.read_text())
            if not data or not data.get("prompt"):
                continue
            old = data["prompt"]
            new = fix_prompt(old)
            if new != old:
                data["prompt"] = new
                path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True, width=1000))
                changed += 1
    print(f"Updated {changed} AS files")


if __name__ == "__main__":
    main()
