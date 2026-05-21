#!/usr/bin/env python3
"""Scaffold atomic step YAML files from tactical step README outputs.

Usage: python scripts/generate_atomic_step_scaffolds.py G-005 G-006 G-007
Only creates AS for TS whose atomic_steps is empty [].
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/plans/ai_editor"


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return s[:48] or "module"


def main(groups: list[str]) -> None:
    for gs_dir in sorted(PLAN.glob("G-*")):
        gs_id = gs_dir.name.split("-")[0]  # G-005
        if groups and gs_id not in groups and gs_dir.name.split("-")[0] not in groups:
            if gs_dir.name not in groups and gs_id not in groups:
                continue
        for ts_readme in sorted(gs_dir.glob("T-*/README.yaml")):
            data = yaml.safe_load(ts_readme.read_text())
            steps = data.get("atomic_steps") or []
            if steps:
                continue
            ts_id = data["step_id"]
            concepts = data.get("concepts", [])
            outputs = data.get("outputs", [])
            if not outputs:
                print(f"skip {ts_readme}: no outputs")
                continue
            as_dir = ts_readme.parent / "atomic_steps"
            as_dir.mkdir(exist_ok=True)
            ids: list[str] = []
            for i, out in enumerate(outputs, 1):
                aid = f"A-{i:03d}"
                ids.append(aid)
                path = out["name"]
                if path.endswith("/"):
                    continue
                op = "create_file"
                slug = slugify(Path(path).stem)
                fname = f"{aid}-{slug}.yaml"
                if (as_dir / fname).exists():
                    continue
                doc = {
                    "step_id": aid,
                    "parent_tactical_step": ts_id,
                    "name": f"Implement {path}",
                    "target_file": path,
                    "operation": op,
                    "priority": i,
                    "depends_on": [f"A-{j:03d}" for j in range(1, i)],
                    "concepts": concepts,
                    "status": "draft",
                    "prompt": (
                        f"Project: ai_editor. Tactical step: {ts_id} parent {data.get('parent_global_step')}.\n"
                        f"File: {path}. Operation: {op}.\n\n"
                        f"TS description:\n{data.get('description', '')}\n\n"
                        f"Output spec:\n{out.get('description', '')}\n\n"
                        f"MRS concept_ids: {', '.join(concepts)}.\n"
                        f"Read spec.yaml excerpts for these concepts and implement fully.\n"
                        f"Prompt must be self-contained with complete code (create_file) per atomic step standard.\n"
                        f"Constraints: file <= 400 lines; one file only.\n"
                    ),
                    "verification": {
                        "type": "import",
                        "target": path.replace("/", ".").replace(".py", ""),
                        "expected": f"Module {path} imports without error after G-001..G-003 dependencies exist.",
                    },
                }
                if i == 1:
                    doc["depends_on"] = []
                with (as_dir / fname).open("w") as f:
                    yaml.dump(doc, f, sort_keys=False, allow_unicode=True, width=1000)
                print(f"created {as_dir / fname}")
            if ids:
                text = ts_readme.read_text()
                if "atomic_steps: []" in text:
                    text = text.replace("atomic_steps: []", "atomic_steps:\n" + "\n".join(f"- {x}" for x in ids))
                    ts_readme.write_text(text)
                    print(f"updated {ts_readme} -> {ids}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["G-005", "G-006", "G-007"])
