"""Build cross-reference graph for G-NNN plan steps."""

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
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path('/home/vasilyvz/projects/tools/yaml_editor')
PLANS = ROOT / 'docs/plans'
G_PAT = re.compile(r'G-(\d{3})')

LIVE_STEPS = {
    'G-001': 'G-001-package-foundation',
    'G-009': 'G-009-editor-core-buffer-registry',
    'G-010': 'G-010-text-ai-formatters',
    'G-011': 'G-011-universal-search',
    'G-012': 'G-012-foreign-formatters',
    'G-013': 'G-013-cst-formatter',
    'G-014': 'G-014-project-refactor',
    'G-015': 'G-015-session-layer',
}

live_files = []
for step_dir in LIVE_STEPS.values():
    live_files.extend(sorted((PLANS / step_dir).rglob('*.yaml')))
live_files.extend(sorted(PLANS.glob('*.yaml')))

ref_to_files = defaultdict(list)
for f in live_files:
    content = f.read_text(errors='replace')
    rel = str(f.relative_to(PLANS))
    for m in G_PAT.finditer(content):
        ref = f"G-{int(m.group(1)):03d}"
        if rel not in ref_to_files[ref]:
            ref_to_files[ref].append(rel)

print('=== CROSS-REFERENCE TABLE ===')
print(f'{"Ref":<8} {"Status":<10} Cnt  Referencing files')
print('-' * 90)
for ref in sorted(ref_to_files):
    status = 'OK' if ref in LIVE_STEPS else 'BROKEN'
    files = ref_to_files[ref]
    print(f'  {ref:<6} {status:<10} {len(files):<4} {files[0]}')
    for ff in files[1:]:
        print(f'  {"":<22} {ff}')
print()

print('=== BROKEN REFS (referencing deleted steps) ===')
any_broken = False
for ref in sorted(ref_to_files):
    if ref not in LIVE_STEPS:
        any_broken = True
        print(f'  {ref} -> referenced in:')
        for ff in ref_to_files[ref]:
            print(f'    {ff}')
if not any_broken:
    print('  (none)')
print()

print('=== RENAME MAP ===')
print(f'  {"Old":<8} {"New":<8} Directory')
for i, old in enumerate(sorted(LIVE_STEPS)):
    new = f"G-{i+1:03d}"
    print(f'  {old:<8} {new:<8} {LIVE_STEPS[old]}')
