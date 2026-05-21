#!/usr/bin/env python3
"""Automated checks a1,a2,a5-a7,a9 for G-003..G-007 atomic steps (partial a3/a4/a8)."""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/plans/ai_editor"
MRS = yaml.safe_load((PLAN / "spec.yaml").read_text())
MRS_CONCEPTS = {c["concept_id"] for c in MRS.get("concepts", [])}

GROUPS = [
    "G-001-package-foundation",
    "G-002-editor-core",
    "G-003-formatters",
    "G-004-search",
    "G-005-session-layer",
    "G-006-command-layer",
    "G-007-adapter-integration",
]

REQUIRED = {
    "step_id", "parent_tactical_step", "name", "target_file", "operation",
    "priority", "depends_on", "concepts", "prompt", "verification", "status",
}

A5_PATTERNS = [
    re.compile(r"\bA-\d{3}\b"),
    re.compile(r"prior\s+A-", re.I),
    re.compile(r"after\s+A-", re.I),
    re.compile(r"post[- ]A-", re.I),
    re.compile(r"previous\s+atomic", re.I),
    re.compile(r"G-\d{3}/T-", re.I),
]

A2_READ_PATTERNS = [
    re.compile(r"do not open", re.I),
    re.compile(r"read\s+(?:the\s+)?(?:file|module)", re.I),
    re.compile(r"open\s+modules?", re.I),
    re.compile(r"from source files", re.I),
]

CODE_BLOCK = re.compile(r"```(?:python)?\n(.*?)```", re.S)


def load_as_files() -> list[tuple[Path, dict]]:
    out = []
    for g in GROUPS:
        for p in sorted((PLAN / g).glob("T-*/atomic_steps/A-*.yaml")):
            try:
                d = yaml.safe_load(p.read_text())
            except yaml.YAMLError as e:
                out.append((p, {"_parse_error": str(e)}))
                continue
            if d:
                d["_path"] = p
                out.append((p, d))
    return out


def line_count_in_prompt(prompt: str) -> int:
    blocks = CODE_BLOCK.findall(prompt)
    if not blocks:
        return 0
    # for modify chains use largest block (usually full file)
    return max(len(b.splitlines()) for b in blocks)


def main() -> int:
    findings: list[str] = []
    by_ts: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    by_file: dict[tuple[str, str], list[tuple[Path, dict, int]]] = defaultdict(list)

    for path, d in load_as_files():
        if "_parse_error" in d:
            findings.append(f"{path}: YAML parse error: {d['_parse_error']}")
            continue
        ts_key = str(path.parent.parent)
        by_ts[ts_key].append((path, d))
        tf = d.get("target_file", "")
        pr = d.get("priority", -1)
        by_file[(ts_key, tf)].append((path, d, pr))

        miss = REQUIRED - set(d.keys())
        if miss:
            findings.append(f"{path}: missing fields {sorted(miss)}")

        for cid in d.get("concepts") or []:
            if cid not in MRS_CONCEPTS:
                findings.append(f"{path}: a1 unknown concept {cid}")

        prompt = d.get("prompt") or ""
        for pat in A5_PATTERNS:
            if pat.search(prompt):
                findings.append(f"{path}: a5 cross-AS/G-T ref ({pat.pattern})")
                break

        for pat in A2_READ_PATTERNS:
            if pat.search(prompt):
                findings.append(f"{path}: a2 read-other-file hint ({pat.pattern})")
                break

        op = d.get("operation")
        lc = line_count_in_prompt(prompt)
        if lc > 400:
            findings.append(f"{path}: a3 code block ~{lc} lines > 400")

        if op == "modify_file":
            if lc < 5 and "Replace entire file" not in prompt and "```" not in prompt:
                findings.append(f"{path}: a8 modify_file without code block in prompt")
        elif op == "create_file" and "assume" in prompt.lower() and "pre-exist" in prompt.lower():
            findings.append(f"{path}: a8 create assumes pre-existing content")

        v = d.get("verification") or {}
        if v.get("type") not in ("pytest", "import", "static_analysis", "manual"):
            findings.append(f"{path}: a9 bad verification.type")
        if not v.get("target"):
            findings.append(f"{path}: a9 missing verification.target")

        for dep in d.get("depends_on") or []:
            if not re.match(r"A-\d{3}$", dep):
                findings.append(f"{path}: a7 bad depends_on id {dep}")

    # a6 priority uniqueness per (ts, file)
    for (ts_key, tf), items in by_file.items():
        prios = [pr for _, _, pr in items]
        if len(prios) != len(set(prios)):
            findings.append(f"{ts_key} file {tf}: a6 duplicate priority {prios}")

    # a7 depends_on exists in same TS
    for ts_key, items in by_ts.items():
        ids = {d["step_id"] for _, d in items if d.get("step_id")}
        for path, d in items:
            for dep in d.get("depends_on") or []:
                if dep not in ids:
                    findings.append(f"{path}: a7 dangling depends_on {dep}")

    # a10 rough: TS outputs vs AS target files
    for ts_readme in sorted(PLAN.glob("G-00[1-7]*/T-*/README.yaml")):
        data = yaml.safe_load(ts_readme.read_text())
        outputs = data.get("outputs") or []
        out_files = {o["name"].rstrip("/") for o in outputs if o.get("type") == "file" and not o["name"].endswith("/")}
        as_dir = ts_readme.parent / "atomic_steps"
        as_targets = set()
        if as_dir.is_dir():
            for af in as_dir.glob("A-*.yaml"):
                ad = yaml.safe_load(af.read_text())
                if ad:
                    as_targets.add(ad.get("target_file", ""))
        for of in out_files:
            if of and of not in as_targets:
                findings.append(f"{ts_readme}: a10 output file not in any AS target: {of}")

    # cross-TS same file (flag for manual a8)
    global_file: dict[str, list[str]] = defaultdict(list)
    for (ts_key, tf), _ in by_file.items():
        if tf:
            global_file[tf].append(Path(ts_key).name)
    cross_ts: list[str] = []
    for tf, tss in global_file.items():
        if len(tss) > 1:
            cross_ts.append(f"CROSS-TS a8 (manual): {tf} <- {', '.join(sorted(tss))}")

    print(f"Scanned {sum(len(v) for v in by_ts.values())} AS files")
    print(f"Blocking findings: {len(findings)}\n")
    for f in findings:
        print(f)
    if cross_ts:
        print(f"\nCross-TS file ownership ({len(cross_ts)} paths — verify modify_file chains):")
        for c in cross_ts:
            print(c)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
