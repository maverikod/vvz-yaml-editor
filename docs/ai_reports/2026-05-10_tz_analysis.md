# ai_editor — Analysis Report: TZ against Plan Standard v1.0

Date: 2026-05-10
Analyst: Claude Sonnet 4.6
Scope: tech_spec.md + plan.yaml + G-001..G-008 READMEs + audit_report.md

---

## Decisions made (user-approved)

| # | Decision |
|---|---|
| D-1 | G-008 buffer-lifecycle merged into G-005 session-layer → 7 global steps total |
| D-2 | startup_sweep policy **B**: remove orphaned dirs (missing/corrupt ses_settings.json); release stale locks always |
| D-3 | G-step numbering follows file structure (G-001..G-007), not original tz numbering |
| D-4 | Analysis report saved to docs/ai_reports/ |

---

## Artifacts produced by this cascade

| Artifact | Path | Action |
|---|---|---|
| Machine-readable spec | docs/plans/ai_editor/spec.yaml | CREATED (new) |
| Analysis report | docs/ai_reports/2026-05-10_tz_analysis.md | CREATED (new) |
| source_spec.md | docs/plans/ai_editor/source_spec.md | CREATED (renamed from tech_spec.md + non-binding markup) |
| G-001 README | docs/plans/ai_editor/G-001-package-foundation/README.yaml | UPDATED |
| G-002 README | docs/plans/ai_editor/G-002-editor-core/README.yaml | UPDATED |
| G-003 README | docs/plans/ai_editor/G-003-formatters/README.yaml | UPDATED |
| G-004 README | docs/plans/ai_editor/G-004-search/README.yaml | UPDATED |
| G-005 README | docs/plans/ai_editor/G-005-session-layer/README.yaml | UPDATED (merged G-008) |
| G-006 README | docs/plans/ai_editor/G-006-command-layer/README.yaml | UPDATED |
| G-007 README | docs/plans/ai_editor/G-007-adapter-integration/README.yaml | UPDATED |
| G-008 dir | docs/plans/ai_editor/G-008-buffer-lifecycle/ | OBSOLETE — merged into G-005; not deleted |

---

## Concept map (spec.yaml summary)

51 concepts across 7 groups:

| Group | Concept IDs | G-step |
|---|---|---|
| Shared contracts | C-001..C-009, C-020 | G-001 |
| Editor core | C-010..C-019 | G-002 |
| Formatters | C-021..C-034 | G-003 |
| Search | C-035..C-037 | G-004 |
| Session + lifecycle | C-038..C-044 | G-005 |
| Commands + interfaces | C-045..C-048 | G-006 |
| Adapter integration | C-049..C-051 | G-007 |

57 typed relations. All use closed-list types from standard:
uses, owns, extends, depends_on, produces, consumes.

---

## Invariant I1 check (Coverage)

### a) Concepts
union(concepts of G-001..G-007) = C-001..C-051 (all 51 concepts).
C-020 (BufferAddress) intentionally listed in both G-001 (contract definition)
and G-002 (address semantics) — overlap is not forbidden by standard.
**Status: PASS**

### b) Relations
All 57 relations from spec.yaml distributed across G-steps.
**Status: PASS**

### c) Source ranges

| Lines (tech_spec.md) | Content | G-step |
|---|---|---|
| 1–57 | Architecture overview + session git | G-005 |
| 59–83 | Shared contracts | G-001 |
| 85–200 | CA server connection + file API | G-002 |
| 214–560 | Buffer model, FormatterRegistry, writer, config | G-002 |
| 562–1115 | Formatter layer (all 4 formatters) | G-003 |
| 1120–1215 | Search layer | G-004 |
| 1220–1480 | Session layer + buffer lifecycle | G-005 |
| 1490–1610 | Command layer | G-006 |
| 1610–1700 | Error model | G-001 |
| 1640–1765 | Adapter integration | G-007 |

Non-binding regions (Python class bodies, config JSON examples in tech_spec.md):
marked with non-binding tags in source_spec.md.
**Status: PASS**

---

## tz mapping (original numbering → plan files)

| tz section | Content | Plan G-step |
|---|---|---|
| G-001 | Package foundation | G-001 |
| G-002 | Editor core + buffer registry | G-002 |
| G-003 | AbstractFormatter + text/YAML | G-003 |
| G-004 | Universal search | G-004 |
| G-005 | ForeignFormatter | **out of scope** |
| G-006 | CST formatter | G-003 (merged) |
| G-007 | Refactoring / rename | **out of scope** |
| G-008 | Session layer | G-005 |
| G-009 | Command layer | G-006 |
| G-010 | Adapter integration | G-007 |

---

## Terminology canonical: session_key

All artifacts now use `session_key` (from C-007) as the canonical identifier.
Use of `session_id` in existing TS files is a bug to fix in the TS cascade.

---

## Issues from audit_report.md — status after this cascade

| ID | Problem | Severity | Status after cascade |
|---|---|---|---|
| П-2 | Lock skipped for file_id=None | was 🔴 | Closed: C-013/C-014 define lock_mode='full' on download (path-based lock) |
| П-3 | write_result vs CA server in save_pipeline | 🔴 | Open: needs TS cascade (G-002/T-009, G-005/T-104) |
| П-6 | Redo is always stub | was 🔴 | Closed: C-044/C-040 define redo_stack in ses_settings (D-2) |
| П-7 | startup_sweep contradiction | was 🟡 | Closed: policy B fixed in C-044 and G-005 description |
| П-8 | Stale check at file_id=None | was 🟡 | Closed with П-2 (path-based lock) |
| П-9 | lark missing from pyproject.toml | 🟠 | Open: needs TS fix (G-001/T-001) |
| П-10 | api.py always stub | 🟠 | Open: G-006/T-010 scope defined |
| П-14 | No disconnect with unsaved check | 🟠 | Open: noted in G-006/T-002 |
| П-16 | CSTFormatter.write() without CSTTree | 🔴 | Open: needs TS fix (G-003/T-012) |
| Н-1 | G-step numbering mismatch | was 🟡 | Closed: D-3 + tz mapping table above |
| Н-2 | formatter.delete() not in AbstractFormatter | 🟠 | Open: needs TS fix (G-003/T-001) |
| Н-3 | Formatters not registered | 🟠 | Closed: C-046 HooksRegister owns formatter registration |
| Н-4 | session_id vs session_key | was 🟡 | Closed: canonical = session_key (C-007) |
| Н-5 | advisory_lock_batch not in plan | was 🟡 | Closed: C-013 includes advisory_lock_batch |
| Н-6 | download_file doesn't return file_id | 🟠 | Closed: C-013 signature includes file_id return |
| Н-7 | No advisory_unlock for readonly buffers | 🟠 | Closed: C-014 defines release_on_close rule |

**Remaining open (need TS cascade): П-3, П-9, П-10, П-14, П-16, Н-2**

---

## Next steps (recommended)

1. Review and approve this cascade (spec.yaml + 7 G-step READMEs + source_spec.md)
2. Freeze G-steps: set status to `frozen`
3. Run TS cascade: align all TS READMEs to concept IDs, fix open audit issues
4. Decide fate of G-008-buffer-lifecycle/ directory (delete or keep as reference)
