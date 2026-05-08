"""Verify cross-references after renumbering."""
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path('/home/vasilyvz/projects/tools/yaml_editor')
PLANS = ROOT / 'docs/plans'
G_PAT = re.compile(r'G-(\d{3})')

# Expected live steps after renumbering
LIVE_STEPS = {
    'G-001', 'G-002', 'G-003', 'G-004',
    'G-005', 'G-006', 'G-007', 'G-008',
}

# Collect all live yaml files
live_files = []
for d in sorted(PLANS.iterdir()):
    if d.is_dir() and re.match(r'G-00[1-8]', d.name):
        live_files.extend(sorted(d.rglob('*.yaml')))
live_files.extend(sorted(PLANS.glob('*.yaml')))

ref_to_files = defaultdict(list)
for f in live_files:
    content = f.read_text(errors='replace')
    rel = str(f.relative_to(PLANS))
    for m in G_PAT.finditer(content):
        ref = f"G-{int(m.group(1)):03d}"
        if rel not in ref_to_files[ref]:
            ref_to_files[ref].append(rel)

print('=== VERIFICATION: CROSS-REFERENCE TABLE ===')
print(f'{"Ref":<8} {"Status":<10} Cnt')
print('-' * 50)
for ref in sorted(ref_to_files):
    status = 'OK' if ref in LIVE_STEPS else 'BROKEN'
    print(f'  {ref:<6} {status:<10} {len(ref_to_files[ref])}')
print()

broken = [r for r in ref_to_files if r not in LIVE_STEPS]
if broken:
    print('=== BROKEN REFS ===')
    for ref in sorted(broken):
        print(f'  {ref} -> referenced in:')
        for ff in ref_to_files[ref]:
            print(f'    {ff}')
else:
    print('=== ALL REFS OK - no broken references ===')
print()

print('=== DIRECTORIES IN docs/plans ===')
for d in sorted(PLANS.iterdir()):
    if d.is_dir():
        print(f'  {d.name}')