"""Build cross-reference graph for G-NNN plan steps."""
import re
from pathlib import Path
from collections import defaultdict

PLANS_DIR = Path('/home/vasilyvz/projects/tools/yaml_editor/docs/plans')
G_PATTERN = re.compile(r'G-(\d{3})')

plan_files = sorted(PLANS_DIR.rglob('*.yaml'))

existing_steps = {}
for d in sorted(PLANS_DIR.iterdir()):
    if d.is_dir():
        m = re.match(r'G-(\d+)', d.name)
        if m:
            key = f"G-{int(m.group(1)):03d}"
            existing_steps[key] = d.name

print('=== EXISTING G-STEPS ===')
for k, v in sorted(existing_steps.items()):
    print(f'  {k} -> {v}')
print()

ref_to_files = defaultdict(list)
for f in plan_files:
    content = f.read_text(errors='replace')
    rel = str(f.relative_to(PLANS_DIR))
    refs = sorted(set(f"G-{int(m.group(1)):03d}" for m in G_PATTERN.finditer(content)))
    for r in refs:
        ref_to_files[r].append(rel)

print('=== CROSS-REFERENCE TABLE ===')
print(f'{"Reference":<12} {"Status":<10} Cnt  Files')
print('-' * 90)
for ref in sorted(ref_to_files):
    status = 'OK' if ref in existing_steps else 'BROKEN'
    files = ref_to_files[ref]
    print(f'  {ref:<10} {status:<10} {len(files):<4} {files[0]}')
    for ff in files[1:]:
        print(f'  {"":<26} {ff}')
print()

print('=== BROKEN REFS ===')
any_broken = False
for ref in sorted(ref_to_files):
    if ref not in existing_steps:
        any_broken = True
        print(f'  {ref} ->')
        for ff in ref_to_files[ref]:
            print(f'    {ff}')
if not any_broken:
    print('  (none)')
print()

print('=== RENAME MAP ===')
for i, old in enumerate(sorted(existing_steps)):
    new = f"G-{i+1:03d}"
    print(f'  {old} -> {new}   ({existing_steps[old]})')