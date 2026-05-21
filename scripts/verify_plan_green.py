#!/usr/bin/env python3
"""Run all plan verification checks; exit 0 when green."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(name: str) -> int:
    path = SCRIPTS / name
    print(f"=== {name} ===")
    r = subprocess.run([sys.executable, str(path)], cwd=ROOT)
    print()
    return r.returncode


def main() -> int:
    codes = [
        run("verify_atomic_steps.py"),
        run("verify_a8_cross_ts.py"),
    ]
    if any(codes):
        print("VERDICT: NOT GREEN")
        return 1
    print("VERDICT: GREEN (198+ AS, 5 cross-TS chains)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
