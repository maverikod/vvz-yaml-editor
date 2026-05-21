# Task brief — ai_editor plan: complete a cascade of edits

You are a model-executor working in a **fresh context**. You know nothing
about this project, this plan, or what was done before. Everything you
need is in this document. Read it all before doing anything.

You will:
1. Connect to one MCP server.
2. Apply a list of textual edits to several files in that server's project.
3. Verify the result.
4. Produce a short completion report.

You will **not** invent edits, optimize the plan, fix unrelated things,
guess at file contents, or run any reindex/rebuild commands.

---

## Part A — What this plan is (just enough to do the job)

The project being edited is a Python product called **ai_editor**: a
universal document editor for AI models that talks to a separate "code
analysis server" over an API. The architectural details do not matter to
you. What matters:

- The project has a **development plan** stored as files under
  `docs/plans/ai_editor/`.
- The plan has five levels of artifacts (Level 1 to Level 5). You will
  touch Levels 1, 2, 3, and 4.

### A.1. The five plan levels

| Level | Name             | File(s)                                        |
|-------|------------------|------------------------------------------------|
| 1     | Source spec      | `docs/plans/ai_editor/source_spec.md` (Markdown) |
| 2     | Machine spec     | `docs/plans/ai_editor/spec.yaml` (YAML)          |
| 3     | Global step (GS) | `docs/plans/ai_editor/G-NNN-<slug>/README.yaml`  |
| 4     | Tactical step (TS) | `docs/plans/ai_editor/G-NNN-<slug>/T-NNN-<slug>/README.yaml` |
| 5     | Atomic step (AS) | inline inside each TS README under `atomic_steps:` |

The cascade rule: changes flow strictly **top-down**. Level 1 is the
human-readable source of truth; Level 2 is its structured projection;
Levels 3/4/5 reference Level 2 concepts. You will apply changes in
exactly that order.

### A.2. The architectural decision driving these edits

There is one functional decision behind every edit below. Internalize it:

> The CA server's **advisory lock** on a file is released **only when the
> buffer is closed**, never on save. The `save()` and `file_send()`
> commands accept a new optional parameter `close=False`. When `close=True`
> they perform a save and then an explicit unlock+remove (a "save and
> close"). `write_all` never accepts `close`. The CA client's
> `unlock_after_write` parameter is **always `False`** at the
> `ai_editor` call site.

Every edit below is a consequence of this decision. If you find yourself
about to write text that says "save releases the lock" or
"unlock_after_write=True", you are wrong.

---

## Part B — MCP server connection

All file I/O goes through one MCP server. **Do not edit files on local
disk directly.**

```
server_id    = "code-analysis-server"
copy_number  = 1
project_id   = "84ec55c8-cefd-480d-beb6-fa1d35e60362"
project_root = "/home/vasilyvz/projects/tools/ai_editor"
```

Every MCP call has the form:

```
MCP-Proxy:call_server(
  server_id   = "code-analysis-server",
  copy_number = 1,
  command     = "<command_name>",
  params      = { "project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362", ... }
)
```

### B.1. Commands you will use

| Purpose              | Command                  | Key params                              |
|----------------------|--------------------------|-----------------------------------------|
| Check server health  | `get_database_status`    | `project_id`                            |
| List files           | `list_project_files`     | `project_id`                            |
| Read file (full)     | `universal_file_read`    | `project_id`, `file_path`               |
| Read lines           | `get_file_lines`         | `project_id`, `file_path`, `start_line`, `end_line` |
| Replace line range   | `replace_file_lines`     | `project_id`, `file_path`, `start_line`, `end_line`, `new_lines` (list of strings), `backup` |
| Restore from backup  | `restore_backup_file`    | `project_id`, `file_path`, `backup_uuid` |
| Search text on disk  | `fs_grep`                | `project_id`, `pattern`, `file_pattern` |
| Help on a command    | `help`                   | `cmdname`                               |

`file_path` is always relative to the project root, e.g.
`docs/plans/ai_editor/source_spec.md`.

### B.2. Hard prohibitions

- **Never** call `update_indexes` (a.k.a. reindex). It destroys the index
  and is owner-permission-only. After a write you may see a benign warning
  like "failed to refresh code indexes" — that is fine, ignore it.
- **Never** edit files outside the project root.
- **Never** use `universal_file_replace`'s text-range mode in this task.
  An earlier session observed it inserting lines instead of replacing on
  some inputs in this project. Use **`replace_file_lines`** exclusively
  for range replacements. It is the lower-level, predictable tool.

### B.3. Safe edit protocol

For every edit:

1. Call `get_file_lines` for a window covering 5 lines before and 5 lines
   after the target range, to confirm the anchor text matches what this
   brief expects.
2. Call `replace_file_lines` with `backup=true`. Save the returned
   `backup_uuid` to a local note — you may need it for rollback.
3. Re-read the same window with `get_file_lines` and confirm the new
   content is exactly what you wrote (no duplication, no missing lines).
4. If anything looks wrong, immediately call `restore_backup_file` with
   the saved `backup_uuid` and stop. Report.

You apply edits **one at a time, top to bottom**, and re-anchor each
edit by content after the previous one — line numbers shift as edits
land. For each edit below, the **anchor** is the literal text you must
find with `fs_grep` or `get_file_lines`. The line numbers given are
hints from the pre-edit state; trust the anchor text over the numbers.

### B.4. Startup check (do this first)

```
MCP-Proxy:call_server(
  server_id="code-analysis-server", copy_number=1,
  command="get_database_status",
  params={"project_id": "84ec55c8-cefd-480d-beb6-fa1d35e60362"}
)
```

If the result has `processing_paused=true`, stop and report. Otherwise
proceed.

---

## Part B.5. Required reading before any edits

Before touching anything, **read the files you will be editing** so that
when this brief says "the concept whose `concept_id` is `C-014`" you
know exactly what the surrounding YAML looks like. Do these reads
through MCP, not from disk:

1. `universal_file_read` on `docs/plans/ai_editor/source_spec.md`.
   Skim it. Note where each `## G-NNN` heading starts and at which line.
   This is the Level 1 document and the canonical authority for everything
   else in the plan. You will be doing the §D.1 edits against this file.

2. `universal_file_read` on `docs/plans/ai_editor/spec.yaml`.
   Skim it. Learn the exact YAML syntax style used for `concepts:` and
   `relations:` (indentation, flow vs block, quoting). When the §D.2
   edits below say "add a property" or "add a relation entry", match the
   surrounding style exactly. Do not introduce a different style.

3. `list_project_files` with pattern `docs/plans/ai_editor/G-*` to confirm
   the global step directory names.

4. `universal_file_read` on each of the five READMEs you will edit
   (D.3.1, D.3.2, D.4.1, D.4.2, D.4.3). These are small files; read each
   fully. Note the field layout (what fields each README has, in what
   order, what style).

After this reading, you should be able to picture each edit before
making it.

---

## Part C — State of the files at the start of your work

One earlier edit has already been applied. Do not re-apply it.

- File `docs/plans/ai_editor/source_spec.md` has 1765 lines.
- Inside it, the section starting with the heading line `### save pipeline`
  (around line 345) is already rewritten to the new semantics
  (`unlock_after_write=False` and a step 6 about `advisory_unlock` when
  `close=True`). Verify with `get_file_lines` lines 345–356 once at the
  start of your work, before touching anything else. The block should
  contain the literal text:
  `unlock_after_write=False)  → lock kept; write only`
  and
  `6. If close=True: ca_client.advisory_unlock(`.
  If it does not, **stop and report** — your starting state is different
  from what this brief assumes.

Everything else in this brief is **not yet applied**.

---

## Part D — Edits to apply

There are four groups, applied in this order:

- D.1 — three edits in `source_spec.md` (Level 1).
- D.2 — three edits in `spec.yaml` (Level 2).
- D.3 — two edits in global step READMEs (Level 3).
- D.4 — three edits in tactical step READMEs (Level 4).

Total: 11 edits. After D.1 is done, re-anchor D.2 (line numbers in
`source_spec.md` may have shifted by ±1 or ±2). The same applies for
each subsequent group.

---

### D.1. `docs/plans/ai_editor/source_spec.md` (Level 1)

#### D.1.1. Add `close=False` to AbstractBuffer signatures

**Anchor — find this exact 4-line block** (around line 207):

```
new(session_key, formatter_name, initial_content, display_name=None) -> buffer_id
save(session_key, buffer_id) -> OperationResult
save_as(session_key, buffer_id, relative_path, overwrite=False) -> OperationResult
close(session_key, buffer_id, force=False) -> OperationResult
```

**Replace lines 2 and 3 of the anchor** (the `save` and `save_as` lines)
with these two lines:

```
save(session_key, buffer_id, close=False) -> OperationResult
save_as(session_key, buffer_id, relative_path, overwrite=False, close=False) -> OperationResult
```

So you are doing a 2-line for 2-line replacement. After the replacement
the 4-line block must look like:

```
new(session_key, formatter_name, initial_content, display_name=None) -> buffer_id
save(session_key, buffer_id, close=False) -> OperationResult
save_as(session_key, buffer_id, relative_path, overwrite=False, close=False) -> OperationResult
close(session_key, buffer_id, force=False) -> OperationResult
```

**Why.** The AbstractBuffer contract is the public-API source of truth;
the new `close` flag must be visible here.

**Accept after edit:**
- The four lines above appear in the file, in that order, exactly once.
- The total line count of the file is unchanged by this edit.

---

#### D.1.2. Rewrite the `Releasing a lock — on save (upload)` block

**Anchor — find this 15-line block** (starts around line 284):

```
**Releasing a lock — on save (upload):**
```
project_file_transfer_upload_save(
  project_id        = "<uuid>",
  file_path         = "relative/path/to/file.py",
  transfer_id       = "<from upload_begin>",
  backup            = true,
  commit_message    = "ai_editor: save <file_path>",
  unlock_after_write = True   # True = release lock after saving; False = keep lock held
)
```

- `unlock_after_write=True` — lock released atomically with the write. Use for `save` (explicit save, done editing).
- `unlock_after_write=False` — file saved but lock remains held. Use for `write_all`
  (bulk save without closing buffers; session continues editing).
```

**Replace the entire 15-line block with this 19-line block:**

```
**Releasing a lock — on save (upload):**
```
project_file_transfer_upload_save(
  project_id        = "<uuid>",
  file_path         = "relative/path/to/file.py",
  transfer_id       = "<from upload_begin>",
  backup            = true,
  commit_message    = "ai_editor: save <file_path>",
  unlock_after_write = False   # ALWAYS False — save never releases the lock
)
```

- `unlock_after_write` is **always `False`** at the CA-client call site.
  Saving writes content; it never releases the advisory lock. Lock
  release is decoupled from write and happens only via an explicit
  `advisory_unlock` (in `close`, or in `save(close=True)` — see below).
- `save(close=True)` — write-and-close convenience flag (single-buffer
  only): performs the same `upload_save(unlock_after_write=False)`, then
  immediately calls `advisory_unlock` and removes the buffer from
  `ses_settings.json`. Analogous to "save and close" in a regular editor.
  Default: `close=False`.
- `write_all` does not accept a `close` flag — all buffers remain open
  after a bulk save.
```

**Why.** The old block says save releases the lock; the new semantics
say save never does.

**Accept after edit:**
- `unlock_after_write = False` appears in the block.
- The string `unlock_after_write=True` does not appear in this block.
- The three bullets describe the new semantics.

---

#### D.1.3. Rewrite the `Lock lifecycle summary` block

**Anchor — find this 8-line block** (starts around line 332):

```
**Lock lifecycle summary:**
```
open(readonly=False)  → download_begin(lock_mode='full')        → lock_session_id stored in ses_settings
save()                → upload_save(unlock_after_write=True)    → lock released, buffer stays open
write_all()           → upload_save(unlock_after_write=False)   → lock kept, buffer stays open
close()               → advisory_lock_batch(action='unlock')    → lock released, buffer removed  [AUTOMATIC]
startup_sweep         → advisory_lock_batch(allow_foreign=true) → stale lock released
open(readonly=True)   → download_begin(lock_mode='none')        → no lock_session_id
```
```

**Replace the entire 8-line block** (the 6 content lines between the
two fence lines, plus the bold heading, plus the fences themselves — 10
lines total counting the heading and fences) **with this:**

```
**Lock lifecycle summary:**
```
open(readonly=False)  → download_begin(lock_mode='full')        → lock_session_id stored in ses_settings
save(close=False)     → upload_save(unlock_after_write=False)   → lock kept, buffer stays open
save(close=True)      → upload_save(unlock_after_write=False)   → then advisory_unlock + remove buffer
                                                                  (write-and-close convenience flag)
write_all()           → upload_save(unlock_after_write=False)   → lock kept, buffer stays open
close()               → advisory_lock_batch(action='unlock')    → lock released, buffer removed  [AUTOMATIC]
startup_sweep         → advisory_lock_batch(allow_foreign=true) → stale lock released
open(readonly=True)   → download_begin(lock_mode='none')        → no lock_session_id
```
```

**Why.** The summary table is what downstream readers cite most. It must
match the canonical semantics exactly.

**Accept after edit:**
- Two `save(...)` rows present (`close=False` and `close=True`).
- No row contains `unlock_after_write=True`.
- The `close()` row is unchanged in semantics.

---

#### D.1.4. Also fix the G-005 buffer-lifecycle `save` snippet in the same file

There is **another** mention of `unlock_after_write=True` further down in
`source_spec.md`, inside the G-005 (session-layer) "Buffer lifecycle"
section. Find it and fix it too.

**Anchor — find this 6-line block** (around line 1075–1080, under the
heading `**save (always explicit — no auto-save):**`):

```
**save (always explicit — no auto-save):**
```
1. formatter.validate_document(document) -> abort on failure.
2. raw_content = formatter.render(document).
3. ca_client.upload_file(..., unlock_after_write=True) -> releases advisory lock.
4. modified=False, saved=True in ses_settings.
```
```

**Replace the entire block with:**

```
**save (always explicit — no auto-save):**
```
1. formatter.validate_document(document) -> abort on failure.
2. raw_content = formatter.render(document).
3. ca_client.upload_file(..., unlock_after_write=False) -> lock kept; write only.
4. modified=False, saved=True in ses_settings.
5. If close=True: ca_client.advisory_unlock(lock_session_id, project_id, relative_path),
   then remove buffer from ses_settings.json. Otherwise buffer stays open with lock held.
```
```

**Why.** Same as D.1.2/D.1.3 but for the duplicate description in
G-005's buffer-lifecycle subsection.

**Accept after edit:**
- The block contains `unlock_after_write=False`.
- A step 5 about `close=True` and `advisory_unlock` is present.

---

#### D.1.5. Verification at end of D.1

Run a `fs_grep` over `docs/plans/ai_editor/source_spec.md` for the literal
pattern `unlock_after_write=True`. **It must return zero hits.** If it
returns any hit, you missed a spot — find and fix it before moving on.

Also `fs_grep` for `unlock_after_write = True` (with spaces around `=`).
Also zero hits.

---

### D.2. `docs/plans/ai_editor/spec.yaml` (Level 2)

This file is YAML. After every edit it must remain valid YAML. If your
edit breaks the YAML, roll back via `restore_backup_file` and try again
with a smaller, more careful change.

Useful starting move: read the whole file once with `universal_file_read`
to learn its structure. The relevant top-level keys are likely `concepts:`
(a list of concept entries each having `concept_id`, `name`, `definition`,
`properties`, `source_ranges`) and `relations:` (a list of relation
entries each having `from_concept`, `to_concept`, `type`).

#### D.2.1. Update concept `C-014` (AdvisoryLock)

Find the concept whose `concept_id` is `C-014` (and whose `name` is
`AdvisoryLock`). Look at its `properties:` list. There is currently a
property along the lines of "released on save" or "release_on_save:
true" — the exact wording depends on the file.

**Replace the relevant property item(s) with these three items** (keep
them in the existing `properties:` list, preserving YAML list syntax —
`- ` prefix and indentation matching the surrounding items):

```
- no release on save; unlock_after_write is always False at the CA-client call site
- release only via explicit advisory_unlock during close, or during save(close=True)
- release on startup_sweep for stale locks via allow_foreign_session=true
```

Do **not** change `concept_id`, `name`, `definition`, or `source_ranges`
of C-014.

**Accept after edit:**
- The C-014 properties no longer claim that save releases the lock.
- The three bullets above are present in the C-014 properties.
- The file is still valid YAML.

---

#### D.2.2. Update concept `C-013` (CodeAnalysisClient)

Find the concept whose `concept_id` is `C-013` (and whose `name` is
`CodeAnalysisClient`). In its `properties:` list, find the property
about `upload_file` (it likely mentions `unlock_after_write`). Replace
that one property item with:

```
- upload_file is invoked with unlock_after_write=False always; lock release is never performed by upload_file. Caller invokes advisory_unlock separately when closing a buffer or when save(close=True).
```

If there is no existing property about `upload_file`, add this one as a
new item at the end of the `properties:` list.

**Accept after edit:**
- The C-013 properties mention `unlock_after_write=False` as the only
  used value.
- The file is still valid YAML.

---

#### D.2.3. Add a missing relation `(C-044, C-039, uses)`

Find the top-level `relations:` list. Append one new entry to the end:

```
- from_concept: C-044
  to_concept:   C-039
  type:         uses
```

Preserve list indentation matching the surrounding entries.

**Accept after edit:**
- The relations list contains exactly one entry with
  `from_concept: C-044`, `to_concept: C-039`, `type: uses`.
- No other relation entry was modified.
- The file is still valid YAML.

---

#### D.2.4. Verification at end of D.2

Run the following sanity check via `bash_tool` (if you have it) or via
the project's `.venv` python through MCP if available:

```
import yaml, sys
with open("/home/vasilyvz/projects/tools/ai_editor/docs/plans/ai_editor/spec.yaml") as f:
    data = yaml.safe_load(f)
# C-014 and C-013 present
ids = {c["concept_id"] for c in data["concepts"]}
assert "C-013" in ids and "C-014" in ids
# new relation present
assert any(
    r.get("from_concept") == "C-044" and r.get("to_concept") == "C-039" and r.get("type") == "uses"
    for r in data["relations"]
)
print("OK")
```

If you do not have shell access, instead read the file via
`universal_file_read` and confirm by eye that:
- C-014 and C-013 still exist.
- The relations list ends with the `(C-044, C-039, uses)` entry.
- The file looks well-formed YAML (no stray dashes, no unclosed quotes).

---

### D.3. Global step READMEs (Level 3)

Two READMEs have wrong `source_ranges` fields. Fix both.

`source_ranges` is a list of objects `{start: <int>, end: <int>}` (or in
some encodings a list of pairs `[start, end]`). It declares which line
ranges of `source_spec.md` belong to that global step. The ranges are
**1-based, inclusive**.

#### D.3.1. `docs/plans/ai_editor/G-001-package-foundation/README.yaml`

Read the file. Find the `source_ranges:` field. Its current value points
to a range like `start: 1391, end: 1436` which is wrong (that range
belongs to a different global step).

**The correct value for G-001's `source_ranges` is:**

```
source_ranges:
  - start: 66
    end:   97
  - start: 1714
    end:   1765
```

(Use whichever YAML syntax style the file already uses — flow `[a, b]`
pairs or block `start:`/`end:` mappings.)

Reason: G-001 covers the "Package foundation" section (lines 66–97) and
the "Error model" section at the end of the file (lines 1714–1765, post-
save-pipeline-edit). The mistakenly-included range 1391–1436 belongs
inside the G-008 section.

**Accept after edit:**
- `source_ranges` has exactly two entries with the values above.
- All other fields of the README (`step_id`, `name`, `concepts`,
  `relations`, `depends_on`, `tactical_steps`, `status`) are unchanged.

---

#### D.3.2. `docs/plans/ai_editor/G-008-extended-formatters/README.yaml`

Read the file. Find `source_ranges:`. The current value is along the
lines of `start: 1437, end: 1765` which is wrong on both ends.

**The correct value for G-008's `source_ranges` is:**

```
source_ranges:
  - start: 1386
    end:   1713
```

Reason: G-008 covers the "Extended formatter backends" section, which
starts at the `## G-008 (plan)` heading (line 1386) and ends just before
the `## Error model` heading (line 1714). The previous range began too
late and ran past the file end.

**Accept after edit:**
- `source_ranges` has exactly one entry with `start: 1386, end: 1713`.
- All other fields of the README are unchanged.

---

#### D.3.3. Verification at end of D.3

For each of the two READMEs:
- Read it via `universal_file_read`.
- Confirm `source_ranges` has the values listed above.
- Confirm the file is still valid YAML.

Then read `source_spec.md` line 1386 and confirm it is the line
`## G-008 (plan) — Extended formatter backends and cross-formatter conversion matrix`.
Read line 1714 and confirm it is `## Error model`. If either does not
match, the line numbers shifted during D.1 — recompute and re-edit
accordingly.

---

### D.4. Tactical step READMEs (Level 4)

Three READMEs have inconsistencies with the canonical decision. Each is
a small textual fix. For each file, read it first with
`universal_file_read`, locate the field/text described below, and edit.

#### D.4.1. `docs/plans/ai_editor/G-003-formatters/T-003-text-formatter/README.yaml`

This tactical step describes the **text formatter**. Somewhere in its
`description:` (or in an `outputs:` field) it lists the file extensions
registered to the text formatter. The list currently includes `.md`.

**Remove `.md` from that list.** The correct text-formatter extensions
are: `.txt`, `.log`, `.rst`, `.ini`, `.cfg`, `.toml`. Markdown belongs
to the dedicated Markdown formatter (in G-008), not the text formatter.

**Accept after edit:**
- `.md` does not appear in the text-formatter extensions list inside
  this README.
- The other extensions remain.

---

#### D.4.2. `docs/plans/ai_editor/G-006-command-layer/T-001-command-base-hooks/README.yaml`

This tactical step describes formatter registration in `hooks_register`.
Currently it registers `.md` and `.json` against the text formatter and
then describes the JSON formatter as "overriding" text for `.json`. Both
parts are wrong.

In whatever field describes the registration (likely `description:` or
`outputs:`):
- Remove `.md` from the text-formatter extension list.
- Remove `.json` from the text-formatter extension list.
- Remove any phrasing like "overrides text fallback" or "json overrides
  text" — there is no override mechanism, each extension belongs to
  exactly one formatter.

The corrected registration order should read (as documented in
`source_spec.md` near the end of G-008):

```
1. text:     .txt .log .rst .ini .cfg .toml
2. yaml:     .yaml .yml
3. json:     .json
4. cst:      .py
5. markdown: .md .markdown
6. xml:      .xml .xsd .xsl .xslt .svg
7. html:     .html .htm .xhtml
```

**Accept after edit:**
- The text formatter line lists only `.txt .log .rst .ini .cfg .toml`.
- The json formatter line lists `.json` (without any "override" language).
- The markdown formatter line lists `.md .markdown`.

---

#### D.4.3. `docs/plans/ai_editor/G-002-editor-core/T-007-abstract-buffer/README.yaml`

This tactical step describes the AbstractBuffer contract. In its
`outputs:` (or `description:`) it currently mentions parameter names for
`open()` and `save_as()`. The parameter name `file_path` is used; the
canonical name is `relative_path`.

**Replace every occurrence of `file_path` with `relative_path` in this
README, but only when it refers to the buffer's path parameter.** Do
**not** rename anything that refers to something else (e.g. a generic
"file path string"). When in doubt, only touch occurrences inside
function signatures or argument lists of `open`, `save_as`, `new`, or
`close`.

**Accept after edit:**
- The signatures of `open(...)` and `save_as(...)` in this README use
  `relative_path` not `file_path`.
- Any unrelated `file_path` mentions outside signatures are unchanged.

---

#### D.4.4. Verification at end of D.4

For each of the three READMEs:
- Read it via `universal_file_read`.
- Visually confirm the change.
- Confirm the file is still valid YAML.

---

## Part E — Final verification (do all of these)

After all 11 edits are applied:

### E.1. Global text checks

Run `fs_grep` against `docs/plans/ai_editor/source_spec.md`:

| Pattern                       | Expected hits |
|-------------------------------|---------------|
| `unlock_after_write=True`     | 0             |
| `unlock_after_write = True`   | 0             |
| `unlock_after_write=False`    | ≥ 3 (in save pipeline, save block, G-005 save snippet) |
| `save(close=False)`           | ≥ 1 (in Lock lifecycle summary) |
| `save(close=True)`            | ≥ 1 (in Lock lifecycle summary) |
| `close=False)` (signatures)   | ≥ 2 (AbstractBuffer save/save_as) |

Run `fs_grep` against `docs/plans/ai_editor/spec.yaml`:

| Pattern               | Expected hits |
|-----------------------|---------------|
| `release_on_save`     | 0             |
| `C-013`               | ≥ 1           |
| `C-014`               | ≥ 1           |
| `from_concept: C-044` | ≥ 1           |

### E.2. YAML validity

For each YAML file you touched (`spec.yaml` and the five READMEs), do a
parse check. If you have shell access via `bash_tool`:

```
python3 -c "import yaml; yaml.safe_load(open('<path>'))" && echo OK
```

If you do not have shell access, read the file via `universal_file_read`
and confirm there are no obvious YAML syntax issues (unbalanced quotes,
bad indentation at the edit site, missing colons).

### E.3. Cross-file consistency

- `source_spec.md` line 1386 must be `## G-008 (plan) — Extended formatter backends and cross-formatter conversion matrix`.
- `source_spec.md` line 1714 must be `## Error model`.
- `G-001-package-foundation/README.yaml` `source_ranges` covers exactly
  lines 66–97 and 1714–1765 (the second range may need recomputation if
  the file gained/lost lines during edits — check `total_lines` after
  D.1).
- `G-008-extended-formatters/README.yaml` `source_ranges` covers exactly
  lines 1386–1713 (recompute if needed, same reason).

---

## Part F — Rollback policy

If at any point any of these conditions occurs:

- An edit produces unexpected content (duplicated lines, missing lines,
  truncated text, etc.).
- A YAML file fails to parse after your edit.
- A verification check in Part E fails.

…then **stop immediately** and roll back:

1. Use the `backup_uuid` saved from the last successful
   `replace_file_lines` call.
2. Call `restore_backup_file` with that UUID and the same `file_path`.
3. Report in your completion summary which edit failed, what the
   anomaly was, and which `backup_uuid` you restored to.

Do not try to "fix forward" a broken edit by adding more edits on top.

---

## Part G — Completion report

When you finish (whether fully or partially), produce a short report
covering:

1. Which of the 11 edits in Part D you successfully applied (by ID:
   D.1.1, D.1.2, …, D.4.3).
2. For each edit: the `backup_uuid` returned by the write call.
3. The result of every verification check in Part E (pattern → hit count).
4. Any rollback you performed and why.
5. Any edit you could not apply, with the reason and the file state you
   left it in.

Format: plain text or Markdown, in chat. Do not commit any code, do not
run any reindex, do not push anything. The owner will review the report
and decide on next steps (including whether to run a reindex).

---

## Part H — Quick reference: edit index

| ID    | File                                                                 | What                                       |
|-------|----------------------------------------------------------------------|--------------------------------------------|
| D.1.1 | `source_spec.md`                                                     | AbstractBuffer save/save_as add `close=False` |
| D.1.2 | `source_spec.md`                                                     | "Releasing a lock — on save" block rewrite |
| D.1.3 | `source_spec.md`                                                     | "Lock lifecycle summary" block rewrite     |
| D.1.4 | `source_spec.md`                                                     | G-005 save snippet rewrite                 |
| D.2.1 | `spec.yaml`                                                          | C-014 AdvisoryLock properties              |
| D.2.2 | `spec.yaml`                                                          | C-013 CodeAnalysisClient upload_file       |
| D.2.3 | `spec.yaml`                                                          | add relation (C-044, C-039, uses)          |
| D.3.1 | `G-001-package-foundation/README.yaml`                               | source_ranges fix                          |
| D.3.2 | `G-008-extended-formatters/README.yaml`                              | source_ranges fix                          |
| D.4.1 | `G-003-formatters/T-003-text-formatter/README.yaml`                  | remove `.md` from text extensions          |
| D.4.2 | `G-006-command-layer/T-001-command-base-hooks/README.yaml`           | fix text/json registration, remove override |
| D.4.3 | `G-002-editor-core/T-007-abstract-buffer/README.yaml`                | `file_path` → `relative_path`              |

End of brief.
