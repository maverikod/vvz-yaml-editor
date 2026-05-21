#!/usr/bin/env python3
"""Verify a8 cross-TS file-state chains for atomic steps (outer_loop focus)."""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/plans/ai_editor"

CODE_BLOCK = re.compile(r"```(?:python)?\n(.*?)```", re.S)


def gs_t_order(path: Path) -> tuple[int, int]:
    parts = path.parts
    g = t = 0
    for p in parts:
        if p.startswith("G-"):
            g = int(p.split("-")[1])
        if p.startswith("T-"):
            t = int(p.split("-")[1])
    return g, t


def load_all_as() -> list[tuple[Path, dict]]:
    out = []
    for p in sorted(PLAN.glob("G-*/T-*/atomic_steps/A-*.yaml")):
        d = yaml.safe_load(p.read_text())
        if d:
            out.append((p, d))
    return out


def extract_blocks(prompt: str) -> list[str]:
    return [b.rstrip() + "\n" for b in CODE_BLOCK.findall(prompt)]


def normalize(code: str) -> str:
    return code.replace("\r\n", "\n").strip() + "\n"


def expected_output(op: str, blocks: list[str]) -> str | None:
    if not blocks:
        return None
    if op == "create_file":
        return normalize(blocks[-1])
    if op == "modify_file":
        return normalize(blocks[-1]) if len(blocks) >= 1 else None
    return None


def expected_input(op: str, blocks: list[str]) -> str | None:
    if op == "create_file":
        return None
    if op == "modify_file":
        if len(blocks) >= 2:
            return normalize(blocks[0])
        return None
    return None


def main() -> int:
    by_file: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    for path, d in load_all_as():
        tf = d.get("target_file", "")
        if tf:
            by_file[tf].append((path, d))

    findings: list[str] = []
    chains_ok = 0

    for tf, items in sorted(by_file.items()):
        if len({path.parent.parent for path, _ in items}) <= 1:
            continue

        ordered = sorted(
            items,
            key=lambda x: (gs_t_order(x[0]), x[1].get("priority", 0), x[1].get("step_id", "")),
        )

        prev_output: str | None = None
        for path, d in ordered:
            op = d.get("operation", "")
            blocks = extract_blocks(d.get("prompt") or "")
            inp = expected_input(op, blocks)
            out = expected_output(op, blocks)

            if op == "modify_file":
                if inp is None:
                    findings.append(f"{path}: modify_file missing current-state code block")
                    continue
                if prev_output is not None and normalize(inp) != normalize(prev_output):
                    findings.append(
                        f"{path}: a8 cross-TS mismatch\n"
                        f"  expected current == prior AS output for {tf}\n"
                        f"  step {d.get('step_id')} in {path.parent.parent.name}"
                    )
                elif prev_output is not None:
                    chains_ok += 1
            elif op == "create_file" and prev_output is not None:
                findings.append(f"{path}: create_file after prior modifications on {tf}")

            if out is not None:
                prev_output = out

        if not findings and prev_output:
            print(f"OK chain: {tf} ({len(ordered)} AS across TS)")

    print(f"\nCross-TS chains verified: {chains_ok} links OK")
    print(f"Findings: {len(findings)}")
    for f in findings:
        print(f)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
