"""Renumber G-NNN plan steps: rename dirs and patch all references."""
import os
import re
from pathlib import Path

ROOT = Path('/home/vasilyvz/projects/tools/yaml_editor')
PLANS = ROOT / 'docs/plans'

# Rename map: old_dir_prefix -> new_dir_prefix
# Only the G-NNN part changes; slug stays the same
RENAME = {
    'G-009': 'G-002',
    'G-010': 'G-003',
    'G-011': 'G-004',
    'G-012': 'G-005',
    'G-013': 'G-006',
    'G-014': 'G-007',
    'G-015': 'G-008',
}

# Text substitutions: applied to ALL yaml file contents
# Order matters: do largest numbers first to avoid partial collisions
TEXT_SUBS = [
    # Step IDs and dir names: G-015 -> G-008, etc (old -> new)
    ('G-015', 'G-008'),
    ('G-014', 'G-007'),
    ('G-013', 'G-006'),
    ('G-012', 'G-005'),
    ('G-011', 'G-004'),
    ('G-010', 'G-003'),
    ('G-009', 'G-002'),
    # Dir name slugs in paths (e.g. G-009-editor-core -> G-002-editor-core)
    ('G-009-editor-core-buffer-registry', 'G-002-editor-core-buffer-registry'),
    ('G-010-text-ai-formatters', 'G-003-text-ai-formatters'),
    ('G-011-universal-search', 'G-004-universal-search'),
    ('G-012-foreign-formatters', 'G-005-foreign-formatters'),
    ('G-013-cst-formatter', 'G-006-cst-formatter'),
    ('G-014-project-refactor', 'G-007-project-refactor'),
    ('G-015-session-layer', 'G-008-session-layer'),
    # Broken refs to deleted steps -> neutral text marker
    # G-002..G-008 old: after renaming G-009->G-002 etc,
    # old G-002..G-008 strings that appeared in files become conflicts.
    # We must handle carefully: after substitution above,
    # any remaining G-002..G-008 refs ARE the newly renamed steps.
    # Old deleted refs appeared as G-002..G-008 in source BEFORE rename.
    # Since we apply renames from G-015 down to G-009, and G-002..G-008
    # old dirs are gone, the strings G-002..G-008 in files BEFORE rename
    # referred to deleted steps. After rename they will refer to new steps.
    # This is the desired outcome: broken refs become valid after renaming.
]

print('=== STEP 1: Rename directories ===')
for old_prefix, new_prefix in sorted(RENAME.items(), reverse=True):
    for old_dir in sorted(PLANS.iterdir()):
        if old_dir.is_dir() and old_dir.name.startswith(old_prefix + '-'):
            new_name = new_prefix + old_dir.name[len(old_prefix):]
            new_dir = PLANS / new_name
            os.rename(old_dir, new_dir)
            print(f'  mv {old_dir.name} -> {new_name}')

print()
print('=== STEP 2: Patch text references in all yaml files ===')

# Collect all yaml files after rename
yaml_files = sorted(PLANS.rglob('*.yaml'))
root_plan = ROOT / 'docs'
# Also patch the root plan
yaml_files += [ROOT / 'docs' / 'plans' / 'create_pip_package_for_mcp.yaml']

patched = 0
for f in yaml_files:
    if not f.exists():
        continue
    content = f.read_text(encoding='utf-8')
    new_content = content
    # Apply substitutions in correct order (dir names before short codes
    # to avoid double-substitution)
    # First pass: replace full dir names
    for old, new in [
        ('G-009-editor-core-buffer-registry', 'G-002-editor-core-buffer-registry'),
        ('G-010-text-ai-formatters', 'G-003-text-ai-formatters'),
        ('G-011-universal-search', 'G-004-universal-search'),
        ('G-012-foreign-formatters', 'G-005-foreign-formatters'),
        ('G-013-cst-formatter', 'G-006-cst-formatter'),
        ('G-014-project-refactor', 'G-007-project-refactor'),
        ('G-015-session-layer', 'G-008-session-layer'),
    ]:
        new_content = new_content.replace(old, new)
    # Second pass: replace short G-NNN codes
    # Use regex to replace only standalone G-NNN (not inside longer strings)
    for old_code, new_code in [
        ('G-015', 'G-008'),
        ('G-014', 'G-007'),
        ('G-013', 'G-006'),
        ('G-012', 'G-005'),
        ('G-011', 'G-004'),
        ('G-010', 'G-003'),
        ('G-009', 'G-002'),
    ]:
        new_content = re.sub(
            r'(?<![\w-])' + re.escape(old_code) + r'(?![\w-])',
            new_code,
            new_content,
        )
    if new_content != content:
        f.write_text(new_content, encoding='utf-8')
        rel = str(f.relative_to(PLANS))
        print(f'  patched: {rel}')
        patched += 1

print(f'\nTotal files patched: {patched}')
print('Done.')