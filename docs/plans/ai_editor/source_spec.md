<!-- source_spec.md — Level 1 Source Specification (ai_editor plan) -->
<!-- Renamed from tech_spec.md. Standard: plan_standard_machine.yaml v1.0 -->
<!--
  PLAN STANDARD NOTES:
  - Canonical session identifier: session_key (UUID4). Do NOT use session_id.
  - G-step numbering in this file follows plan file structure (G-001..G-008, G-009).
    Original draft used G-001..G-010 with gaps; mapping in docs/ai_reports/2026-05-10_tz_analysis.md.
  - startup_sweep policy B: release stale locks + delete orphaned dirs
    (dirs with missing or corrupt ses_settings.json). No TTL.
  - G-005 (ForeignFormatter) and G-007 (Refactoring) are explicitly out of scope.
  - G-003 covers both AbstractFormatter/YAML/Text (original G-003) and CST (original G-006).
  - G-005 covers both session infrastructure (original G-008) and buffer lifecycle.
  - G-008 covers additional formatter backends (XML, HTML, Markdown) and the
    cross-formatter conversion matrix (clipboard paste between different formats).
-->

# AI Editor — Technical Specification

Product: **ai_editor** — a universal document editor for AI models and MCP servers.
Editing operates on structural paths and formatter units, not raw line ranges.
Line ranges are an emergency fallback only.

---

## Architecture: three independent layers

```
Session
  └─ owns: session directory, session git (single), buf files, clipboard, session attributes
       │
Buffer
  └─ owns: binding of one file to one formatter, modified flag, locked flag
       │
Formatter
  └─ owns: parse, render, validate, write, open, close, delete,
            copy, cut, paste, search, replace, and format-specific commands
```

Formatters do not know about sessions or buffers.
Buffers do not know about other buffers or sessions.
Sessions coordinate buffers and own session git history and clipboard.

### Session directory isolation (binding)

Each session is a **separate directory** on disk. Session artifacts never share
paths and never mix between sessions.

```
Layout:
  <sessions_base_dir>/
    <session_key_A>/   — all artifacts for session A only
    <session_key_B>/   — all artifacts for session B only; no overlap with A
```

Invariants:
- **I1. One session, one directory:** path = `<sessions_base_dir>/<session_key>/`.
  **Directory name equals session id:** `session_key` (UUID4) is both the canonical
  session identifier and the on-disk directory name. Session exists iff this
  directory exists and contains valid `ses_settings.json`.
- **I2. No cross-session files:** tree, native, baseline, `.pending`, git repo,
  clipboard, and buffer files live **only** under their session directory.
  No global shared buffer store. No hardlinks/symlinks between session dirs.
- **I3. session_key is the access gate:** every API call carries `session_key`.
  Resolver computes `session_dir = base_dir / session_key` and rejects:
  - missing directory → `SESSION_NOT_FOUND`
  - `ses_settings.json.session_key != session_key` (path/dir mismatch) → `SESSION_NOT_FOUND`
  - malformed session_key (path traversal, `/`, `..`) → `SESSION_NOT_FOUND`
- **I4. buffer_id scoped to session:** `(session_key, buffer_id)` resolves buffer
  metadata from **that** session's `open_buffers` only. Same buffer_id in another
  session's directory is a different buffer → `BUFFER_NOT_FOUND` if used with
  wrong session_key.
- **I5. No foreign directory access:** commands must never open, read, or write
  paths outside the resolved `session_dir` for the given `session_key`.
  Passing another session's UUID as session_key without that directory → denied.

CA file lock isolation (separate concern): a project file locked under one
`ca_session_id` is unavailable to other CA sessions (`BUFFER_LOCKED`). Session
directory isolation is **local disk** isolation; both apply.

All session-layer path helpers (`buffer_file_path`, `write_tree_file`, etc.)
take `session_dir` derived from validated `session_key` — never a raw path from
the caller.

The system uses **one git repository per session**, located at `<session_dir>/git/`.
There is no project git. The CA server manages its own versioning (backup + commit on upload).

**Session git:**
- Created when a session is created: **after** session directory exists (`session_connect`).
- Repository path: `<session_dir>/git/` (non-bare).
- One branch per open buffer: `buf/<buffer_id>`.
- A commit is made on every operation that mutates the buffer.
- This is the undo/redo mechanism — any buffer state can be recovered as long as the session exists.
- Clipboard operations (`copy`, `cut`) also produce commits in session git.
- Deleted together with the session directory when the session is closed.

**File lifecycle — local vs remote:**
- `relative_path=None` → **local**: created via `file_create`, never sent to CA server.
  No file lock. On `file_close` without `file_send` + `modified=True` + `force=False` → `FILE_HAS_UNSENT_CHANGES`.
  On `force=True` → delete artifacts, no unlock.
- `relative_path!=None` → **remote**: downloaded via `file_open`, or became remote after `file_send`.
  Writable remote: `locked=True` (lock acquired at open). Read-only remote: `locked=False`,
  `readonly=True` forced. On `file_close` without write+send + `modified=True` + `force=False`
  → `FILE_HAS_UNSENT_CHANGES`.
- `readonly=True`: close freely regardless of `modified`. Includes all `lock=False` opens.
  Not counted in unsent-files check. No CA lock to release on close.
- `modified` is set `True` after every **tree mutation**; reset to `False` only after
  **write/export** (tree → native session file). `file_send` is relay only and does
  not clear `modified` or touch the tree (see G-009 buffer command semantics).

---

## G-001 — Package foundation

Owns: `pyproject.toml`, `ai_editor/__init__.py`, `ai_editor/contracts/`, `ai_editor/py.typed`.

Shared contracts used by all subsystems:

- **ResultEnvelope** — `success (bool)`, `error_code (str|None)`, `message (str)`, `details (dict)`, `diagnostics (list)`
- **ErrorCode** — enum covering all typed errors from all G-steps (see error model at end)
- **Diagnostic** — `code (str)`, `message (str)`, `path (str|None)`, `details (dict)`
- **ValidationResult** — `success (bool)`, `diagnostics (list[Diagnostic])`
- **OperationResult** — `success (bool)`, `error_code (str|None)`, `message (str)`, `diagnostics (list[Diagnostic])`
- **WriteAllResult** — `success (bool)`, `written_buffers (list[str])`, `failed_buffers (list[dict])`, `skipped_buffers (list[str])`, `diagnostics (list[Diagnostic])`
- **SessionKey** — type alias: `str` (UUID4). Canonical name: `session_key`. Never `session_id`.
- **SessionDescriptor** — `session_key`, `open_buffers (list[BufferDescriptor])`, `diagnostics`
- **BufferDescriptor** — `buffer_id`, `session_key`, `filename`, `relative_path`, `formatter`, `project_id`, `modified (bool)`, `readonly (bool)`, `buf_file_path`
- **BufferAddress** — `buffer_id (str)`, `address (Any)` — opaque to editor core, interpreted only by formatter

Rules:
- All subsystems import contracts only from `ai_editor/contracts/`.
- No subsystem edits another subsystem's owned paths.
- No subsystem patches `.venv`, `venv`, `site-packages`.
- CLI entry point `ai-editor = ai_editor.interfaces.cli:main` declared in `pyproject.toml`, implemented in G-006.

Runtime dependencies (`pyproject.toml`):
- `mcp-proxy-adapter` — adapter framework
- `ruamel.yaml>=0.18.0` — YAML round-trip parse/render
- `jsonpath-ng>=1.6.0` — YAML path filters
- `jsonschema>=4.0.0` — schema validation
- `libcst>=1.1.0` — CST formatter
- `lark>=1.1.0` — XPath LALR query engine (CSTFormatter)
- `gitpython>=3.1.0` — session git
- `cryptography>=41.0.0` — mTLS cert handling

---

## Code analysis server connection

All file access goes through the code analysis server API.
`ai_editor` never reads or writes project files directly from disk.

Auth modes:
- **mTLS** — client certificate + CA. `use_token: false`.
- **HTTPS + token** — `use_token: true`, token from env var (`token_env`). Header: `X-API-Key: <token>`.

Passwords and tokens **never** stored in `config.json` — only env var name references.

### File API — key commands

| Operation | Command | Required params |
|---|---|---|
| Download file (chunks) | `project_file_transfer_download_begin` | `project_id`, `file_path`, `compression` |
| Backup history | `list_backup_versions` | `project_id`, `file_path` |
| Upload new content | `transfer_upload_begin` → PUT chunks → `transfer_upload_complete` → `project_file_transfer_upload_save` | `project_id`, `file_path`, `transfer_id`, `unlock_after_write` |
| Restore version | `restore_backup_file` | `project_id`, `file_path`, `backup_uuid?` |
| List project files | `list_project_files` | `project_id` |
| File lock acquire / release | `session_open_file` / `session_close_file` | `session_id` (=ca_session_id), `project_id`, `file_id` |

### Download flow

```
1. project_file_transfer_download_begin(
     project_id, file_path, compression='identity',
   )
   → { transfer_id, size_bytes, checksum_value (SHA-256), file_id }
2. GET /api/transfer/downloads/{transfer_id}/chunks?offset=0&limit=1048576
   → raw bytes chunk
3. Repeat until offset >= size_bytes. Verify SHA-256.
```

### Upload flow

```
1. transfer_upload_begin(filename, size_bytes, checksum_value, compression='identity')
   → { transfer_id }
2. PUT /api/transfer/uploads/{transfer_id}/chunks  (body = raw bytes)
3. transfer_upload_complete(transfer_id)
4. project_file_transfer_upload_save(
     project_id, file_path, transfer_id,
     backup=true, commit_message
   )
```

### `project_id` in buffer

Each buffer stores `project_id` + `file_path` (relative). This pair is sufficient for all CA server operations.
`file_id` (UUID from `files` table) stored when known; returned by `download_begin`. May be `None` if file not yet indexed — lock still acquired by path.

### Sessions survive restart

After restart, `ai_editor` recovers sessions from directories on disk.

**startup_sweep policy B:**
```
startup_sweep(sessions_base_dir, ca_client):
  for session_dir in sessions_base_dir:
    ses_settings = try_read(session_dir / 'ses_settings.json')
    if ses_settings is None or corrupt:
      # orphaned directory — delete it
      delete session_dir
      continue
    # valid session — release stale file locks under its ca_session_id
    for buf in ses_settings.open_buffers:
      if buf.locked and not buf.saved:
        ca_client.unlock_file(ses_settings.ca_session_id, buf.project_id, buf.file_id)
```
No TTL. No time-based deletion. Only orphaned dirs (missing/corrupt ses_settings.json) are removed.

---

## G-002 — Editor core and buffer registry

Owns: `ai_editor/editor_core/`, `ai_editor/config/`, `ai_editor/writer.py`, `tests/editor_core/`.

### Buffer model

One buffer = one open document. Buffer is bound to a file and a formatter at open time.
Both never change for the lifetime of the buffer.

```
buffer fields:
  buffer_id          UUID4, stable for the lifetime of the buffer
  project_id         UUID4 of the code_analysis project
  file_id            UUID from files table (null if not yet indexed)
  filename           bare filename, e.g. README.yaml
  relative_path      path relative to project root (null for local buffers never sent)
  formatter          formatter name, set at open, never changes
  modified           bool — True after tree mutation; False after write/export
  locked             bool — CA lock held; True only on writable remote open (lock=True)
  readonly           bool — immutable after open; forced True when locked=False (remote).
                         Blocks write and file_send only; local tree edit still allowed.
  buf_file_path      str — session path to native session file (<buffer_id>.<ext>); absent until write
  tree_file_path     str — session path to tree file (<buffer_id>.tree)
  baseline_native_path str — native bytes at open/last write; diff baseline
  saved              bool — True after file_send relay completed
  redo_stack         list[str] — SHA list for redo
```

### AbstractBuffer public contract

```
open(session_key, project_id, file_path, formatter=auto,
  open_as_text=False, lock=True) -> buffer_id
  # lock=True (default): session_open_file + writable buffer.
  # lock=False: download only; readonly=True forced.
new(session_key, formatter_name, initial_content, display_name=None) -> buffer_id
save(session_key, buffer_id, close=False) -> OperationResult
save_as(session_key, buffer_id, relative_path, overwrite=False, close=False) -> OperationResult
close(session_key, buffer_id, force=False) -> OperationResult
reload(session_key, buffer_id) -> OperationResult
get_state(session_key, buffer_id) -> BufferState
get_formatter(session_key, buffer_id) -> AbstractFormatter
validate(session_key, buffer_id) -> ValidationResult
write_all(session_key, force=False) -> WriteAllResult
```

### BufferState

```
BufferState:
  buffer_id      str
  formatter      str
  preview        str   — render_skeleton output
  modified       bool
  readonly       bool
  relative_path  str | None
```

### FormatterRegistry

```
FormatterRegistry:
  register(formatter_name, extensions, formatter_class)
  get_by_extension(ext) -> formatter_class | None
  get_by_name(name) -> formatter_class | None
  list_formatters() -> list[str]
```

Invariant: one extension maps to exactly one formatter.
Registration happens in HooksRegister (G-006) at startup — not at import time.

### Open rules

Remote buffer open (`file_open`) — **lock and writability are coupled:**

```
lock=True  (default for edit intent):
  session_open_file → buffer.locked=True, buffer.readonly=False
  Mutations, write, send allowed (subject to session.readonly).

lock=False:
  download only — NO session_open_file
  buffer.locked=False, buffer.readonly=True  (forced; not overridable)
  Local editing allowed: tree mutate, undo/redo, preview, search, clipboard, close.
  Forbidden only: **write** (export to native session file) and **file_send** (relay to CA)
  → BUFFER_READONLY on write/send attempts.
```

Invariant for remote buffers: **`locked=False` ⇔ `readonly=True`**. Writable open
always acquires CA lock first. `BUFFER_LOCKED` if another CA session holds the file.

- `formatter=auto`: `get_by_extension(ext)`. `open_as_text=True`: always text.
- Small file (len < threshold): text formatter.
- Parse error: fallback text, status=format_fallback.

### Advisory lock (CA server)

All file locking is managed exclusively via the CA server API under an **external CA session**
(`ca_session_id`). The CA session is the user session (e.g. the chat): created at user login,
**outside ai_editor**, and shared with other consumers (terminal sessions, etc.). ai_editor never
calls `session_create` or `session_delete` and does NOT own the CA session lifecycle.

`ca_session_id` is received externally at editor-session creation and stored at the **session level**
in `ses_settings.json` (not per buffer). The lock is a server-side cooperative DB lock keyed by
`(ca_session_id, project_id, file_id)` in `session_file_locks`.

**The editor's session-related responsibility is exactly two things:**
1. Lock each fetched file on the CA server (`session_open_file`).
2. Hard-isolate file access between sessions: a file locked by one session is unavailable to
   another (`BUFFER_LOCKED`).

**Acquiring a lock — on remote buffer open (writable path only):**

- Caller requests writable open (`lock=True`, default for edit).
- Pre-check existing locks via `session_list_file_locks`. If the file is held by a different
  CA session → `BUFFER_LOCKED`, no content is fetched.
- Otherwise `session_open_file(ca_session_id, project_id, file_id)` acquires the lock (idempotent;
  `acquired=false` if this same session already holds it), then transfer-download fetches content.
- `file_id` is resolved via `list_project_files`; required for `session_open_file`.
- On success: `buffer.locked=True`, `buffer.readonly=False`.

**Read-only open (`lock=False`):**

- No `session_open_file`. Download content.
- `buffer.locked=False`, `buffer.readonly=True` — **mandatory coupling**.
- All local session operations allowed (tree mutate, git, preview, undo, close).
- **write** and **file_send** rejected (`BUFFER_READONLY`). No CA upload, no native export.

**Releasing a lock — on save (upload):**

`project_file_transfer_upload_save` writes content. It NEVER releases the lock. The lock is released
only by an explicit `session_close_file` (in buffer close, or in `save(close=True)`).

`save(close=True)`: performs the upload, then immediately calls `session_close_file` and removes the
buffer from `ses_settings.json`. Analogous to "save and close" in a regular editor. Default
`close=False`.

**Releasing a lock — on buffer close:**

`session_close_file(ca_session_id, project_id, file_id)` releases the lock for one file. Called when
`close(buffer_id, force=False|True)` runs and the buffer is `locked`. Local buffers
(`relative_path=None`): no lock was acquired, no unlock needed. Readonly buffers: no lock, no unlock.

**Releasing locks — on startup_sweep (recovery):**

For every locked buffer recorded in an orphaned `ses_settings.json`, call
`session_close_file(ca_session_id, project_id, file_id)` to release the stale lock, then delete the
session directory. The CA session itself is never deleted (it outlives the editor).

**Lifecycle summary:**

```
open(lock=True)       → session_open_file + download  → locked=True, readonly=False
open(lock=False)      → download only                 → locked=False, readonly=True (forced)
file_write/send       → rejected when buffer.readonly=True (or session.readonly)
mutate/undo/preview   → allowed when buffer.readonly=True; blocked only by session.readonly
save(close=False)     → write + optional file_send    → lock kept if locked
save(close=True)      → write + file_send + close     → lock released, buffer removed
write_all()           → write per buffer              → lock kept
close()               → session_close_file if locked  → artifacts removed
session.close()       → session_close_file for ALL locked files → delete session dir
startup_sweep         → session_close_file for orphaned locks → delete session dir
```

CA session itself (`session_delete`) is **never** touched — it outlives the editor.

`ca_session_id` (session-level) and `buffer.locked` (per buffer) are stored in `ses_settings.json`
and survive process restart, enabling lock release on startup_sweep even if the editor process that
acquired the lock has crashed.


### save pipeline (write / export — NOT send)

Every write/export compares **baseline native** (source at open or last successful
write) against **candidate native** (Exporter.render from current tree). Write
proceeds only when there are changes AND caller confirms.

```
Baseline: stored at ingest (<buffer_id>.baseline.<ext>).
Pending:  <buffer_id>.<ext>.pending — temp candidate after preview; deleted on reject.

1. formatter.validate_document(document) → abort on failure
2. candidate = formatter.export(document)
3. diff = compute_export_diff(baseline, candidate)
4. If diff.identical:
     return success OK; no temp; no native write; modified=False
5. Preview (approve not True, no pending yet):
     write candidate to .pending temp; return diff for model review
6. approve=True (model agreed):
     promote .pending → native session file; update baseline; delete .pending; modified=False
7. approve=False (model rejected):
     delete .pending if exists; no baseline change; modified unchanged; tree unchanged
     return success cancelled
```

**file_export_diff** — export+diff in memory only; never creates `.pending`.

**file_write** params: `approve: bool | None = None`
```
None / omitted  → preview: create .pending + return diff (if has_changes)
approve=True    → commit pending temp to native file
approve=False   → reject: delete .pending, no other side effects
```

**file_send (relay — separate command, no tree/export):**
```
Precondition: buffer.modified == False (write must have run).
1. Read native session file bytes
2. ca_client.upload_file(...) by file_id (project resolved from file_id)
3. buffer.saved = True
4. If unlock=True: session_close_file; may chain to file_close
```

Legacy `save(close=True)` decomposes to: write (steps 1–4) + optional file_send + file_close.

`validate(buffer_id)` calls `formatter.validate_document` only, no write.

### BufferAddress

```
BufferAddress:
  buffer_id   str
  address     Any  — opaque to editor core, interpreted only by formatter
```

`copy` and `cut` require `source: BufferAddress`.
`paste` requires `target: BufferAddress` and `mode`.
Editor core never parses address content.

### writer.py

Two write paths:

- `write_tree_file(graph, path)` — atomic write of serialised DocumentGraph to
  `<buffer_id>.tree` (or `.cst`). After every tree mutation and on ingest.
- `write_native_session_file(content, path)` — atomic write of exported native
  bytes to `<buffer_id>.<ext>`. After write/export command only.
- `write_result(content, path)` — backup + atomic write + read-back verification.
  For project-side derived artifacts (e.g. `.tree/<stem>.tree` on save). NOT for
  session tree file (use write_tree_file).

Project/CA files: uploaded only via **file_send** relay of native session file.
Never write project paths directly from mutation path.

### Config

Config read from adapter's `config.json`, sections `ai_editor` and `code_analysis_server`.
`ai_editor` does not create its own config file.

`ai_editor` config section fields:
- `formatter.small_file_threshold`: str (e.g. "1k"). Threshold units: bare int = chars, `k` = thousands, `0` = disabled.
- `formatter.small_file_formatter`: str — one of: `text`, `yaml`, `cst`.
- `sessions.base_dir`: str (default: `.ai_editor_sessions`).

`code_analysis_server` config section fields:
- `host`, `port`, `protocol` (https|mtls), `servername`, `check_hostname`.
- `ssl`: cert, key, ca, crl (paths resolved relative to config.json dir).
- `auth.use_token`: bool. `auth.token_env`: env var name (not the token itself).

`AiEditorConfigGenerator` extends `SimpleConfigGenerator` (adapter).
Calls `super().generate(...)` first, then appends `ai_editor` and `code_analysis_server` sections.

`AiEditorConfigValidator` extends `BaseValidator` (adapter).
Calls `SimpleConfigValidator` first, then validates `ai_editor` and `code_analysis_server` sections.

SSL validation fully delegated to `SSLValidator` from adapter. No duplication.

Config reader: `SimpleConfig.load()` from adapter. `ai_editor` does not implement its own.

---

## G-003 — AbstractFormatter and formatter backends (Text, YAML, JSON, CST)

Owns: `ai_editor/formatters/`, `ai_editor/schemas/`, `tests/formatters/`.

### AbstractFormatter required contract

AbstractFormatter is the **base class for every format**. It owns the tree and
all operations over the tree. Subclasses own ONLY the conversion between the
tree representation and the concrete file format. The editor works with the
tree, not with the format: all structural editing is done by the base class.

```
# ---- Base class: tree ownership and structural operations (NOT overridden) ----

# Document lifecycle (delegates conversion to subclass hooks)
open_tree(raw_content) -> tree        # parse via subclass, assign stable_ids, build sidecar
export(tree) -> raw_content           # render whole tree via subclass
render_skeleton(tree, selector=None, options=None) -> str   # unified preview/navigation

# Navigation / search (uniform across all formats; address = node stable_id)
normalize_address(address) -> normalized_address
get_unit(tree, address) -> unit
iter_units(tree, scope=None) -> Iterator[unit]
match_unit(unit, query) -> bool | score
compare_units(unit_a, unit_b, options) -> ComparisonResult
diagnostics(tree) -> list[Diagnostic]

# Structural mutations over the tree (base class moves/deletes/inserts nodes)
insert(tree, parent_address, position, content) -> tree
  # position (uniform across ALL formats — tree-temp, sidecar, text):
  #   "first"              — insert as first child
  #   "last"               — insert as last child (default)
  #   "before:<addr>"      — insert immediately before sibling at <addr>
  #   "after:<addr>"       — insert immediately after sibling at <addr>
  #   <0-based integer>    — insert at explicit sibling index
  #
  # <addr> resolution by format:
  #   tree-temp (JSON/YAML):
  #     starts with "/" → JSON Pointer (e.g. "before:/items/1")
  #     UUID v4           → stable node id (before_node_id / after_node_id)
  #     otherwise         → object key name (before_key / after_key)
  #   text/markdown:
  #     node_ref slug path (e.g. "before:some-section")
  #     or bare "before" / "after" — relative to the node_ref of the op
  #
  # content is raw block source; base calls node_from_source() to build node.
delete(tree, address) -> tree
move(tree, address, target_parent_address, position) -> tree
replace_node(tree, address, content) -> tree
  # Replaces FULL node including its structural marker:
  #   text/markdown — includes heading line (e.g. "### Section Title\n")
  #   tree-temp     — includes mapping key
  #   sidecar       — includes function/class signature
  # To replace body only (text/md): use address suffix "/<node_ref>/__content"
  # Preserves existing stable_id.
mutate_batch(tree, operations) -> tree    # atomic ordered list of structural ops
  # All-or-nothing: if any op or resulting tree fails validation (parse
  # failure or tree invariant violation), the entire batch is rolled back
  # to the pre-batch tree. Returns MUTATION_ROLLBACK with diagnostics.
multiple_replace(tree, [(address, content), ...]) -> tree
  # Same all-or-nothing rollback semantics as mutate_batch.

# Post-mutation validation (applies to every single mutation op above
# except mutate_batch which has its own batch rollback):
#   After insert/delete/move/replace_node/multiple_replace the base runs:
#     a) subclass parse on export(tree) — syntax check
#     b) tree invariants — stable_id uniqueness, parent-child consistency
#   On failure: roll back ONLY that operation to pre-mutation tree state.
#   Return MUTATION_ROLLBACK with diagnostics. No git commit on rollback.

# Fragments / clipboard (structure handled by base; body via subclass converters)
copy_fragment(tree, source_address) -> fragment
cut_fragment(tree, source_address) -> (tree, fragment, changed_addresses)
paste_fragment(tree, target_parent_address, position, fragment) -> (tree, changed_addresses)
  # position: same values as insert() above

# Identity (owned entirely by the base class)
#  - stable_id is assigned by the base class to every node.
#  - editing a node's content via replace_node preserves its stable_id.
#  - structural ops (insert/delete/move) maintain stable_id integrity.
#  - subclasses never assign, read, or depend on stable_ids.

# Write orchestration (base class; uniform for all formats)
write(tree, path) -> WriteResult
  # 0. validate(tree): subclass parse on export(tree) + tree invariants.
  #    Failure -> PRE_WRITE_VALIDATION_FAILED immediately. No diff shown.
  # 1. raw = export(tree) via subclass render
  # 2. show diff to caller (preview phase)
  # 3. on confirm: write raw to a temp file
  # 4. run all subclass-provided linters/validators on the temp file
  # 5. no errors  -> atomic rename temp -> target (commit)
  #    errors     -> abort, temp discarded, errors returned to caller

# Discovery
list_commands() -> FormatterCommandCatalog
```

```
# ---- Subclass: conversion hooks ONLY (each new format implements these) ----

parse(raw_content) -> tree_nodes        # whole file source -> tree nodes (no ids)
render(tree) -> raw_content             # whole tree -> file source
node_from_source(raw_block) -> node     # block source -> one tree node/subtree (no id)
node_to_source(node) -> raw_block       # one tree node -> block source
linters() -> list[Linter]               # validators run by base over the temp file on write
```

The base class never knows the concrete syntax; the subclass never moves,
deletes, inserts, or identifies nodes. Editing flow: caller passes block
source -> base calls subclass node_from_source -> base performs the structural
operation on the tree -> on write, base calls subclass render and runs subclass
linters before the atomic rename.

The base class (via the session/buffer layer) does NOT:
- Open, save, or close files for buffer lifecycle.
- Own buffer registry or stale disk checks.
- Perform git operations.
- Know about `session_key`, `.buf` files, or session directory.

### InvalidOnOpen mode

If a file fails to parse at open time (any format — JSON, YAML, .py, etc.),
the buffer enters **InvalidOnOpen mode** instead of returning an error:

```
open response when is_invalid=True:
  format_group:          text  (TextFormatter used regardless of extension)
  original_format_group: str   (format_group that would apply if file were valid)
  is_invalid:            true
  fallback_reason:       str   (parse error message)
  warning:               str   (human-readable notice to model)
  available_operations:  [insert, delete, replace]  (text-mode only)

InvalidOnOpen invariants:
  I1. format_group is always determined by file extension. Model cannot set it.
  I2. If file is invalid at open → format_group=text, is_invalid=True.
      Model is explicitly warned via `warning` field.
  I3. format_group stays text until first successful commit that passes re-parse.
  I4. write_mode=preview is always allowed regardless of is_invalid.
  I5. write_mode=commit when is_invalid=True:
        a) Re-parse draft with original_format_group formatter.
        b) Parse fails → FORMAT_INVALID_ON_OPEN error; no disk write.
           Response includes parse_errors: list[{line, col, message}].
        c) Parse succeeds → atomic write; format_group restored to
           original_format_group; is_invalid cleared.
           Response includes recovered_format_group, available_operations.
  I6. Every edit response when is_invalid=True includes `warning` field.
  I7. windowed_preview(offset, limit) is always available for navigation
      in text-mode (InvalidOnOpen or native text files).
```

InvalidOnOpen applies to all formats. TextFormatter itself never enters
InvalidOnOpen (plain text always parses).

### render_skeleton

`render_skeleton(document, options=None) -> str` — compact structural overview for model-facing display.
NOT `render()`. Used by: `BufferState.preview`, `get_state` response, session open/new return value.

`SkeletonOptions` dataclass:
- `depth: int = 2` — max nesting depth before collapse
- `hint_fields: list[str] = [name, id, step_id, type]` — promoted on collapse
- `collapse_threshold: int = 3` — collapse children block if count > N
- `string_preview_len: int = 60` — truncate long scalar strings
- `offset: int = 0` — for text formatter: start line

Shared rendering rules (YAML + JSON):
- Scalar: shown inline.
- Long string: truncated with char count, e.g. `description: "Adapted..." # 847 chars`
- Mapping depth <= max: scalar children inline, nested mappings/sequences collapsed.
- Sequence depth <= max: items up to collapse_threshold inline, then `... N more`.
- Hint fields promoted after collapse marker.

### Validation three-level chain

```
Formatter: formatter.validate_document(doc)
Buffer:    buffer.validate(buffer_id)      → calls formatter.validate_document
Session:   session.write_all()             → calls buffer.validate per buffer
```

Validation always precedes write. Write rejected on any validation failure.

### FormatterCommandCatalog

```
FormatterCommandCatalog:
  formatter_name, formatter_version
  standard_commands: list[FormatterCommandMetadata]
  specific_commands: list[FormatterCommandMetadata]
  openapi_schemas: dict

FormatterCommandMetadata:
  name, kind ('standard'|'formatter_specific'), description
  input_schema, output_schema (OpenAPI-compatible)
  side_effects: list[str], writes_files: bool
  requires_buffer: bool, requires_file_path: bool
  examples: list
```

### FormatterUnit

```
address       Any   — opaque; matches BufferAddress.address semantics
unit_kind     str
display_text  str
metadata      dict
```

### Text formatter

```
document model: list[str]
address model:  int (line index) | tuple[int,int] (inclusive range) | None (whole doc)
payload kinds:  text_lines, text_block
paste modes:    insert, replace_range, append, prepend
render_skeleton: lines[offset : offset + collapse_threshold*10] (sliding window)
validate_document: always success=True
windowed_preview(offset, limit) -> str:
  Returns lines [offset, offset+limit) with 1-based line numbers prefixed.
  offset: 0-based line index. limit: max lines to return.
  Supported for all TextFormatter consumers at all times, including
  InvalidOnOpen mode. Does not require a valid tree — operates on raw
  line array. Used for navigation when structural preview is unavailable.
Registered extensions: .txt .log .rst .ini .cfg .toml
```
### YAML formatter

```
document model: ruamel.yaml CommentedMap / CommentedSeq (round-trip)
address model:  structural YAML path string
  top_level_key
  dotted.path.to.key
  list[0]
  commands[name=buf_diff]
  commands[name=buf_diff].metadata.best_practices[1]
payload kinds:  yaml_node, yaml_block, rendered_text
paste modes:    set, replace_block, append, insert_before, insert_after
```

Invariants:
- `render(parse(render(doc))) == render(doc)` (deterministic)
- Mapping order and comments preserved where ruamel.yaml allows
- Empty path: `mutate_replace_block` only
- Non-existent path: `PATH_NOT_FOUND`
- Non-unique filter match: `PATH_NOT_UNIQUE`

`validate_document`: YAML parse + optional JSON schema + `plan_task_v1` semantic checks + render determinism check.

plan_task_v1 semantic checks:
- `format == plan_task_v1`
- `kind` in `[spec, global, tactical, atomic]`
- `depends_on` is list of strings
- `commands[].name` values unique
- `commands[].schema.required` references only existing properties
- `verification` is non-empty list
- `status` in `[draft, ready_for_review, ready_for_implementation, blocked]`

Clipboard compatibility:
- yaml → yaml: allowed
- yaml → text: allowed only with `rendered_text` mode
- text → yaml: rejected by default; allowed with `parse_as_yaml` mode
- other: `CLIPBOARD_FORMAT_MISMATCH`

Emergency fallback (not normal workflow):
- `yaml_read_lines` — read by line range (diagnostic only)
- `yaml_write_lines_unsafe` — write by line range (emergency repair only)

Compatibility wrappers (legacy names → new architecture):
```
yaml_load          → buffer.open + formatter.parse
yaml_write_checked → buffer.save / buffer.save_as
yaml_validate      → buffer.validate
yaml_get           → search.find_one or formatter.get_unit
yaml_set           → formatter.paste_fragment(mode=set)
yaml_replace_block → formatter.paste_fragment(mode=replace_block)
yaml_append        → formatter.paste_fragment(mode=append)
yaml_delete        → formatter.cut_fragment + discard
yaml_move          → formatter.cut_fragment + formatter.paste_fragment
```

Registered extensions: `.yaml`, `.yml`

### JSON formatter

```
document model: dict | list | scalar (stdlib json, Python natives)
address model:  JQ-style dot-path string
  server.host
  commands[0]
  commands[name=buf_open]
  commands[1].metadata.tags[0]
payload kinds:  json_node, json_block, rendered_text
paste modes:    set, replace_block, append, insert_before, insert_after
render: json.dumps(document, indent=2, ensure_ascii=False)
validate_document: JSON parse + optional jsonschema
NOTE: no comment preservation. Key order = Python dict insertion order.
Registered extensions: .json
```
### CST formatter (.py files)

Owns: `ai_editor/formatters/cst/`. Built-in formatter, NOT ForeignFormatter.
Adapted from `cst-code/` source snapshot. Registered for `.py`, name `cst`.

#### Document model: CSTTree

```
CSTTree:
  tree_id        runtime UUID
  module         libcst.Module
  metadata_map   node_id -> TreeNodeMetadata
  node_map       node_id -> libcst.CSTNode
  root_node_id   stable_id of module root node
```

`TreeNodeMetadata` — frozen dataclass: `stable_id (str UUID4)`, `start_line (int)`, `end_line (int)`, `docstring (DocstringMeta | None)`.

Public address for callers: `stable_id` (UUID4). `node_id` is internal, never exposed.

#### stable_id — identity, lifecycle, and mutation protocol

**Identity:** UUID4 assigned once per node at first `_build_tree_index`. Never reassigned.
Stored in `TreeNodeMetadata.stable_id` (in-memory) and sidecar JSON (on disk). Never written into `.py` source as persistent data.

**Survival through mutations — node_id_aliases mechanism:**
After any mutation libcst rebuilds internal node objects; old `python_object_id → node_id` mappings become invalid.
Protocol:
1. Snapshot `previous_metadata_map` (node_id → TreeNodeMetadata) and `previous_obj_to_id` (object id → node_id).
2. Apply mutation via libcst.
3. Run `_build_tree_index` on the new module. For each new node:
   - Object identity matches `previous_obj_to_id` → reuse old node_id → inherit old stable_id.
   - No match → assign new UUID4.
4. Build `node_id_aliases` from `previous_obj_to_id` for libcst wrapper-object cases.

**Transient embedding during mutation (IMPORTANT):**
Some libcst operations re-parse the code string passed to them, creating new Python objects with no identity link to existing nodes. To preserve stable_id through this re-parse, the formatter temporarily embeds stable_ids as special comments in the code string:

```python
# @node-id: <uuid4>
```

This comment is injected immediately before the libcst call and stripped immediately after libcst returns — via `strip_inline_node_id_lines_from_source` — before any write, any render, any sidecar update. **The comment never reaches the `.py` file on disk.**

**Legacy cleanup on open (mandatory):**
Before `cst.parse_module` on every open:
1. `strip_persisted_node_ids(raw)` — removes trailing `# cst-node-ids: begin...end` block.
2. `strip_inline_node_id_lines_from_source(logical)` — removes `# @node-id: <uuid>` lines.
If logical source differs from raw → overwrite file atomically before indexing.

#### Sidecar (CSTSidecar)

Two locations:
```
Session-side:  <session_dir>/<buffer_id>.cst   — written after every mutation
Project-side:  <py_dir>/.cst/<py_stem>.tree    — written on save
```

Format:
```
CST_TREE_V1 sha256=<source_sha256> tree_sha256=<tree_body_sha256>
<JSON body: serialised metadata_map {node_id -> {stable_id, start_line, end_line, docstring}}>
```

Load: both checksums validated. Either mismatch → rebuild from scratch.
Write: atomic via tempfile + `os.replace`. `sidecar_matches_built_tree` verifies layout after rebuild.

`write()` signature: `write(self, content: str, path, *, tree: CSTTree | None = None) -> None`
Writes: (1) `.py` source via `writer.write_result`; (2) project-side sidecar.
#### Declarative skeleton — structure and navigation

The primary view for a `.py` file. Gives the model a maximally compact understanding
of file structure. Never shows implementation code unless explicitly requested.

**Line format for every visible node:**
```
[<stable_id>] <start_line>-<end_line>  <node_representation>
```
Both start and end line are always present. The model can use them to navigate
or request a specific node by stable_id.

**What is shown at each level:**

Module level (default, `render_skeleton(document)`):
```
[uuid] 1-1    """Module docstring first sentence."""
[uuid] 4-4    import libcst as cst
[uuid] 6-6    CONSTANT = 42
[uuid] 7-7    # module-level comment (not inside any class/function)
[uuid] 10-25  class CSTFormatter(AbstractFormatter):
[uuid] 11-11      """Formatter for .py files."""
[uuid] 13-16      def parse(self, raw_content: str) -> CSTTree:
[uuid] 14-14          """Parse source. Args: raw_content."""
[uuid] 18-22      def render(self, document: CSTTree) -> str:
[uuid] 19-19          """Render to string."""
[uuid] 27-35  def top_level_function(x: int) -> str:
[uuid] 28-28      """Top-level function docstring."""
```

Class level (`get_unit(class_stable_id)`):
- Class header + full class docstring.
- All attribute/property declarations with types.
- Module-level comments inside the class body.
- All method signatures + their docstrings (first sentence).
- Bodies of methods hidden with placeholder.

Method/function level (`get_unit(method_stable_id)`):
- Expanded into **AST nodes** of the body — each node on its own line with stable_id and line range.
- Node types shown: assignments, calls, conditionals, loops, return statements, etc.
- Each AST node is individually addressable by stable_id.
- Implementation code is NOT shown by default — only AST node structure.

**Shown at module level:**
- Module docstring
- Module-level variables and constants (`name = value`, `name: type = value`)
- Module-level comments (not inside any class or function)
- Class headers (`class Name(Base):`) + class docstrings
- Method/function signatures (`def name(params) -> type:`) + their docstrings

**NOT shown by default (hidden with placeholder or omitted):**
- Method/function bodies
- Nested implementation details
- Imports are shown verbatim (they are module-level nodes)

**`as_text=True` flag:**
Any node can be retrieved as raw source text:
```
get_unit(document, stable_id, as_text=True)
```
Returns the complete source of that node and all its descendants as plain text.
No stable_id prefixes, no structure — just the raw code. Used when the model
needs to read or edit the actual implementation.

**Pre-read validation:**
Before returning any node content to the model, the formatter compiles the
file via `compile()`. If errors are found:
- Node is returned as raw text (equivalent to `as_text=True`).
- Response includes a structured list of errors: `{line, col, message}`.
- Model sees both the code and the errors together.
This applies to `get_unit`, `render_skeleton`, and any read command.

**Selector filter (XPath-like):**
`render_skeleton` and `get_unit` accept an optional `selector` parameter.
When provided, only nodes matching the selector are shown.
```
render_skeleton(document)                              # full file, no filter
render_skeleton(document, selector='//class')          # all classes
render_skeleton(document, selector='class > method')   # methods inside classes
render_skeleton(document, selector='//FunctionDef[@name^="_"]')  # private funcs
render_skeleton(document, selector='//FunctionDef[start_line>=100]')
```
Selector syntax is the same XPath engine used by `cst_query` (Lark LALR).
Result always uses the same line format: `[stable_id] start-end  representation`.

**Edit command:**
Viewing and editing are explicitly separate commands.
`render_skeleton` / `get_unit` — read-only, return structure or text.
`cst_edit(document, stable_id, new_code)` — write command:
- Takes `stable_id` of the target node and `new_code` as string.
- Before writing to disk: compiles `new_code` via `compile()`.
- If compilation fails → returns error list, does NOT write. File unchanged.
- If compilation succeeds → applies mutation, writes sidecar, writes `.py` file.
- Returns updated skeleton view of the parent node.

#### DocstringMeta

```
DocstringMeta:
  summary         str             — first sentence
  args            dict[str, str]  — {param: description} from Args: section
  returns         str | None      — from Returns: section
  attributes      dict[str, str]  — {attr: description} from Attributes: section
  docstring_body  str | None      — raw fallback if not Google-style
```

Rules:
- Google-style sections: `Args:`, `Returns:`, `Attributes:`, `Raises:`.
- No sections found → stored in `docstring_body`.
- Applied automatically on `save` into the LibCST node. Never embed manually in `new_code`.
- Serialised to sidecar JSON via `to_dict()` / `from_dict()`.
- File-level docstring: module node's `summary` = first sentence; `docstring_body` = full text.

#### Mutation operations

All mutations address nodes by `stable_id`.

```
insert(parent_stable_id, position, code)
  position: first | last | after:<stable_id>

delete(node_stable_id)

move(node_stable_id, parent_stable_id, position)

replace(node_stable_id, code)
  ClassDef/FunctionDef target: _replace_node_header used automatically
  (replaces name/params/bases only; body preserved).

replace_docstring(node_stable_id, text)
  Updates docstring; updates DocstringMeta in TreeNodeMetadata.
```

**Execution paths:**
- **Sequential:** one operation at a time, index rebuilt after each. Used for fine-grained node types (Param, Name).
- **Mutable batch** (`mutable_cst` layer): `replace > 1 OR insert > 1 OR any delete`, AND no REPLACE_RANGE/MOVE.

**Operation sort before apply:**
- DELETE, REPLACE: bottom-to-top by source position (prevents position-shift cascade).
- INSERT: bottom-to-top by parent position.

**On failed save:** `rollback_tree_to_code` restores in-memory tree to last-known-good source; clears SHA snapshots.

#### Multiple mutations — position-safe batch ordering

`mutate_batch(document, operations)` accepts a mixed list of insert / replace / delete operations.
Applying them naively top-to-bottom would shift source line numbers after each operation,
invalidating positions captured for subsequent ones.

**Protocol (bottom-to-top position map):**
1. **Resolve positions.** For each operation look up `start_line` of the target node from `metadata_map`.
2. **Build a position map:** `{target_start_line: operation}`.
3. **Sort descending by `target_start_line`.** Operations targeting lower line numbers (end of file) apply first.
4. **Apply in sorted order.** Each operation modifies lines below all not-yet-applied operations —
   so previously resolved positions remain valid.

Invariant: once sorted descending, no applied operation can shift the target line of any
not-yet-applied operation. This allows arbitrary batch sizes without pre-computing cumulative offsets.

```
Example — three inserts at lines 80, 50, 30:
  Sorted order: 80 → 50 → 30.
  Insert at 80: shifts lines 81+ only → positions 50 and 30 unaffected.
  Insert at 50: shifts lines 51+ only → position 30 unaffected.
  Insert at 30: no subsequent operations to affect.
```

This is the same principle used internally in `modify_tree`:
- DELETE / REPLACE: sorted bottom-to-top by `start_line`.
- INSERT: sorted bottom-to-top by parent `start_line`.

**Constraint:** two operations targeting the same `stable_id` in one batch → `DUPLICATE_TARGET_IN_BATCH` error.

#### Search within CST

```
iter_units(document, scope=None) -> Iterator[FormatterUnit]
  Recursive descent over all nodes. FormatterUnit.address = stable_id.

match_unit(unit, query) -> bool
  Comparison by stable_id only. Units match iff stable_id equal.

compare_units(unit_a, unit_b, options) -> ComparisonResult
  Structural: node type + node data must match; children compared recursively.
```

#### CST-specific commands

```
cst_query(selector) — XPath-like queries (tree structure only).
  Returns nodes in declarative format; full body via get_unit(stable_id).

  Syntax (Lark LALR):
    //FunctionDef[@name='foo']              descendant
    class > method:first                    direct child, first
    Def:*[start_line>=100]                  FunctionDef or ClassDef from line 100
    function[@name^='_']:not([name^='__'])  private non-dunder
  Axis:       space=descendant, >=child, //=recursive
  Predicates: [attr op value], @-prefix optional
  Pseudo:     :first, :last, :nth(N), :not(selector)
  Wildcard:   :* (Def:* → FunctionDef + ClassDef)
  Operators:  = != ~= ^= $= > < >= <=
  Attributes: name, qualname, type, kind, start_line, end_line, children_count

cst_get_skeleton() — full declarative skeleton of current buffer.
cst_get_unit(stable_id) — full source of one node including body.
cst_list_units() — flat list: {stable_id, type, kind, name, qualname, start_line, end_line}
```

#### validate_document

Compiles `tree.module.code` via Python `compile()`. Returns syntax diagnostics. Does not write files.

#### Clipboard serialization

```python
CSTFormatter.to_string(fragment) -> str    # serialize → stored as body in clipboard.json
CSTFormatter.from_string(body) -> fragment # deserialize on paste
```

#### Adaptation from cst-code

`cst-code/` is a source snapshot inside the `ai_editor` repo.
Adapted into `ai_editor/formatters/cst/` — NOT imported as a package.

| Module | Take | Skip |
|---|---|---|
| `cst_tree/tree_builder.py` | `_build_tree_index`, stable_id, `node_id_aliases`, `previous_obj_to_id` | — |
| `cst_tree/tree_modifier.py` | sequential + batch paths, operation sort | — |
| `cst_tree/tree_modifier_ops*.py` | INSERT/DELETE/REPLACE, `_replace_node_header` | — |
| `cst_tree/tree_sidecar.py` | `CST_TREE_V1` format, atomic write, `sidecar_matches_built_tree` | — |
| `cst_tree/skeleton.py` | `build_declarative_overview`, VISIBLE_KINDS, `ast.get_docstring` | — |
| `cst_tree/models.py` | `CSTTree`, `TreeNodeMetadata` frozen dataclass | — |
| `cst_tree/node_stable_id.py` | `get_stable_id`, `strip_inline_node_id_lines_from_source` | `set_stable_id`, `ensure_stable_id` |
| `cst_tree/node_id_markers.py` | `strip_persisted_node_ids` | `append_persisted_node_ids`, `render_marker_block` |
| `cst_tree/tree_range_finder.py` | range lookup | — |
| `cst_query/` | XPath Lark LALR engine (parser, executor, index_builder) | — |
| `core/mutable_cst/` | batch mutation layer | — |
| `core/database*/` | — | entire block |
| `commands/` | — | entire block (rewrite under ai_editor arch) |

Additional binding constraints:
- `_build_tree_index`: `MetadataWrapper` + `PositionProvider`. stable_id priority: (1) `previous_metadata_map` match, (2) new UUID4.
- `_find_parent_for_node`: walks parent_id chain → nearest insertable container (Module, IndentedBlock, ClassDef, FunctionDef).
- `_apply_libcst_codegen_compat()`: patches `SimpleStatementLine._codegen_impl` for libcst ≥ 1.8. Copy as-is.

Do NOT take:
- Global `_trees` dict + TTL loop — tree lifecycle owned by session layer.
- `append_persisted_node_ids`, `render_marker_block` — writing stable_ids into source forbidden.
- `set_stable_id`, `ensure_stable_id` — embedding `# @node-id:` in `leading_lines` forbidden.
---

## G-004 — Universal search (AbstractSearch)

Owns: `ai_editor/search/`, `tests/search/`.

Search is an interface layer on top of the formatter.
Does not open or write files. Takes a query, returns formatter blocks
with formatter-specific addresses and previews.

### AbstractSearch contract

```
find(session_key, buffer_id, query, scope=None) -> list[SearchMatch]
find_one(session_key, buffer_id, query, scope=None) -> SearchMatch | error
list_units(session_key, buffer_id, scope=None) -> list[SearchMatch]
```

Calls on formatter: `iter_units`, `match_unit`, `compare_units`.

### SearchMatch

```
SearchMatch:
  buffer_id(str), formatter(str), address(Any), preview(str),
  unit_kind(str), metadata(dict)
```

Address by formatter:
- cst: stable_id UUID4 e.g. `"a3f1c8d2-..."`
- yaml: structural path string e.g. `"commands[name=buf_open]"`
- text: `"start_line:end_line"` e.g. `"42:47"`

Returned addresses are directly usable in `BufferAddress` for copy/cut/paste.

### Query model

```
base fields: kind, value, options
text kinds:  contains_text, regex
yaml kinds:  field_equals, node_type
cst kinds:   xpath, stable_id
```

Query examples:
```
# text
{kind: contains_text, value: "buf_diff"}
{kind: regex, value: "^## "}

# yaml
{kind: field_equals, field: name, value: buf_diff}
{kind: node_type, value: mapping}

# cst
{kind: xpath, value: "//FunctionDef[@name='foo']"}
{kind: stable_id, value: "a3f1c8d2-..."}
```

`find` returns zero or more matches.
`find_one` returns exactly one or `SEARCH_NO_MATCH` | `SEARCH_NOT_UNIQUE`.

`preview` content by formatter:
- cst: declarative skeleton line (signature + docstring first sentence).
- yaml: rendered YAML node.
- text: the matched lines verbatim.

---

## G-005 (plan) — Session layer: infrastructure, buffer lifecycle, clipboard, recovery

Owns: `ai_editor/sessions/`, `tests/sessions/`.

A session is a directory on disk. It exists as long as its directory exists.
No TTL. No auto-deletion. **Sessions do not share files** — see architecture
section "Session directory isolation".

### Session directory isolation (enforcement)

Every session-layer entry point calls `resolve_session_dir(base_dir, session_key)`:
```
1. Reject session_key containing '/', '\\', '..', or empty → SESSION_NOT_FOUND
2. session_dir = base_dir / session_key; must be existing directory
3. Load ses_settings.json; settings["session_key"] must equal session_key
4. Return session_dir
```

Every buffer operation calls `resolve_buffer(session_dir, buffer_id)`:
```
1. Find buffer_id in settings["open_buffers"] for THIS session only
2. Compute artifact paths as children of session_dir (never absolute external paths)
3. Missing buffer → BUFFER_NOT_FOUND
```

`reconnect(session_key)` uses the same resolver; no access to sibling session dirs.

### Session create (`session_connect`) — directory then git

Binding order when a **new** session is created (command `session_connect` /
API `connect()`):

```
1. Allocate session_key (UUID4) — this IS the future directory name.
2. Create session directory: mkdir <sessions_base_dir>/<session_key>/
3. Write ses_settings.json with session_key field == directory name (same UUID).
4. Initialize session git INSIDE the directory: init <session_dir>/git/
   (non-bare repo, empty initial commit on branch master).
5. Return SessionDescriptor { session_key, open_buffers: [] }.
```

Rules:
- Git init runs **after** the session directory exists; never before.
- Git lives at `<session_dir>/git/` only; not at sessions_base_dir root.
- Reconnect to existing session: skip mkdir; ensure git exists (lazy repair if missing).
- `session_key` in every API call must match the directory basename exactly.

### Session directory layout
```
<sessions_base_dir>/<session_key>/
  ses_settings.json       — session attributes and open buffer list
  git/                    — non-bare git repository
    buf/<buffer_id>       — one branch per open buffer (tree snapshots)
  <buffer_id>.tree        — DocumentGraph + stable_ids (authoritative for edit)
  <buffer_id>.<ext>            — native session copy (after approved write)
  <buffer_id>.<ext>.pending    — temp candidate awaiting approve/reject; deleted on reject
  <buffer_id>.baseline.<ext>   — diff baseline
  clipboard.json          — current clipboard state
```

`ses_settings.json` fields:
```
session_key    UUID4, canonical name (not session_id)
created_at     ISO-8601
readonly       bool (default false)
open_buffers   list[BufferDescriptor extended with: file_type, readonly, locked,
                    modified, saved, redo_stack(list[str])]
```

### Session git

Non-bare repo. One branch per buffer `buf/<buffer_id>`. Commit on every mutation.
Clipboard cut/copy also produce commits. Deleted with session directory.
Undo/redo implemented via branch commits + `redo_stack` in ses_settings.

### Buffer lifecycle

**open (file from CA server):**
```
1. Determine formatter by extension (FormatterRegistry).
2. If lock=True (writable): session_open_file + download → locked=True, readonly=False.
   If lock=False: download only → locked=False, readonly=True (forced).
   BUFFER_LOCKED if another CA session holds the file (writable path only).
3. ingest: Reader.parse -> assign_stable_ids ONCE -> DocumentGraph.
   Store baseline_native from downloaded bytes.
4. write_tree_file; git commit "open: …"; modified=False.
5. add_buffer_to_settings: file_type='remote', locked/readonly per step 2, redo_stack=[].
6. Return buffer_id and PreviewEnvelope.
```

**new (unsaved buffer / file_create):**
```
1. FormatterRegistry.get_by_name(formatter_name).
2. No CA download. No file lock.
3. ingest from initial_content -> tree; modified=True (no native session file yet).
4. write_tree_file; git commit "new: <display_name>".
5. add_buffer_to_settings: relative_path=None until first file_send, file_type='local'.
6. Return buffer_id and PreviewEnvelope.
```

**reload (remote buffers only):**
```
1. Validate file_type='remote'. Local -> BUFFER_INVALID.
2. ca_client.download_content(..., readonly=True). No lock.
3. Re-ingest: Reader.parse -> assign_stable_ids (reload discards old tree ids policy: preserve where semantically match OR full re-index — implementation in T-002).
4. write_tree_file; git commit "reload: <relative_path>"; modified=False; redo_stack=[].
5. Return PreviewEnvelope.
```

**mutation (tree file + git commit — native unchanged):**
```
1. Readonly check: session.readonly -> SESSION_READONLY.
   buffer.readonly does NOT block mutations (RO allows local tree edit).
2. Load tree file -> in-memory graph.
3. Execute formatter tree mutation.
4. If unchanged: return, no write, no commit.
5. write_tree_file(graph).
6. modified=True, redo_stack=[] written atomically to ses_settings.
7. Git commit: "<command>: <params_summary>".
   Native session file NOT updated. CA upload does NOT happen here.
```

**write / export (tree -> native session file):**
```
1. Readonly check: session.readonly or buffer.readonly -> BUFFER_READONLY.
2. Run save pipeline (preview / approve / reject per approve param).
3. approve=None: if has_changes write .pending temp, return diff.
4. approve=True: promote .pending -> .<ext>, update baseline, delete .pending.
5. approve=False: delete .pending; return cancelled; modified and tree unchanged.
```

**file_export_diff (preview only — no write):**
```
1. Load tree; candidate = formatter.export(document).
2. diff = compute_export_diff(baseline_native, candidate).
3. Return ExportDiffResult (unified_diff + structured hunks: added/removed/changed ranges).
   Allowed in RO. Does not change modified or write files.
```

**file_send (relay only — after write):**
```
Precondition: modified=False.
1. Readonly check: session.readonly or buffer.readonly -> BUFFER_READONLY.
2. Read native session file; upload to CA by file_id.
3. saved=True. Optional unlock + close per params.
```

**save (deprecated composite):** write + optional file_send + optional close.
Prefer explicit file_write and file_send commands.

**close:**
```
1. modified=True without force -> FILE_HAS_UNSENT_CHANGES.
2. Delete <buffer_id>.tree and <buffer_id>.<ext>.
3. if locked: session_close_file(ca_session_id, project_id, file_id).
4. Delete branch buf/<buffer_id> from session git.
5. remove_buffer_from_settings(session_dir, buffer_id).
```

**close_session:**
```
Without force=True:
  If any non-readonly buffer has modified=True -> SESSION_HAS_UNSENT_FILES.
  All clean: release file locks (session_close_file per locked file) + delete session directory.
With force=True:
  Release file locks best-effort (session_close_file per file). Delete directory unconditionally.
Readonly buffers excluded from modified check.
```

### Undo / redo

```
undo(session_key, buffer_id, steps=1):
  Walk back commit.parents. Push current SHA to redo_stack.
  branch.set_commit(target). write_tree_file from commit snapshot. Persist redo_stack.
  UNDO_AT_BEGINNING if no parents.

redo(session_key, buffer_id, steps=1):
  Pop SHA from redo_stack (LIFO). REDO_AT_END if empty.
  branch.set_commit(target). write_tree_file from commit snapshot. Persist redo_stack.
  redo_stack survives restart (lives in ses_settings.json).

New mutation clears redo_stack atomically.
```

### Clipboard

Session-scoped. Stored in `<session_dir>/clipboard.json` as `{formatter, body}`.

```
copy: copy_fragment -> to_string -> clipboard.json -> git commit.
     Does NOT mutate document. Does NOT set modified=True.
cut:  cut_fragment -> to_string -> clipboard.json -> write_tree_file -> commit.
     Sets modified=True and redo_stack=[] atomically.
paste: read clipboard -> from_string -> paste_fragment -> write_tree_file -> commit.
      Sets modified=True and redo_stack=[] atomically.
      CLIPBOARD_FORMAT_MISMATCH if formatter differs.
```

**Source revision policy:**
Each clipboard item stores `source_revision` (SHA of the buffer's git HEAD at copy/cut time).
Two paste policies:
- `snapshot` (default): paste uses the fragment captured at copy/cut time regardless of
  whether the source buffer has changed since. Always succeeds if formatter matches.
- `reject_if_source_revision_changed`: before paste, checks current HEAD of source buffer
  against stored `source_revision`. If they differ → `CLIPBOARD_SOURCE_STALE`. No paste occurs.

Policy is set per clipboard item at copy/cut time, not at paste time.
Default policy: `snapshot`.

Cross-session paste not supported. Clipboard deleted with session directory.

### write_all

```
write_all(session_key, force=False) -> WriteAllResult
For each open buffer where readonly=False and modified=True:
  run write/export (tree -> native session file); modified=False per buffer.
  Does NOT file_send. Does NOT unlock.
Result: success=True only if all eligible buffers exported.
```

Separate batch send (if needed) is explicit file_send per buffer after write_all.

### Session public API

```
connect(readonly=False) -> SessionDescriptor
reconnect(session_key) -> SessionDescriptor
close_session(session_key) -> void
session_status(session_key) -> SessionDescriptor
```

---

## G-006 (plan) — Command layer and public interfaces

Owns: `ai_editor/commands/`, `ai_editor/hooks_register.py`,
`ai_editor/api.py`, `ai_editor/interfaces/cli.py`, `tests/commands/`, `tests/interfaces/`.

### Command registration

All commands follow `docs/metadatastd.md`. Three files per command:
```
ai_editor/commands/<name>_command.py    — Command subclass
ai_editor/commands/<name>_schema.py    — get_schema() -> dict (JSON Schema)
ai_editor/commands/<name>_metadata.py  — metadata() -> dict
```

**Command class shape:**
```python
class BufOpenCommand(Command):  # Command from mcp_proxy_adapter.commands.base
    name = "buf_open"
    version = "1.0.0"
    descr = "Open a file buffer"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict:        # from <cmd>_schema.py
        return get_buf_open_schema()

    def validate_params(self, params):
        params = super().validate_params(params)  # super() ALWAYS FIRST
        # then semantic validation
        return params

    async def execute(self, ...) -> dict:
        ...

    @classmethod
    def metadata(cls) -> dict:          # from <cmd>_metadata.py
        return get_buf_open_metadata(cls)
```

**Command rules:**
- `get_schema()` and `metadata()` are SEPARATE layers. Never mix them.
- `validate_params()` always calls `super()` first, then semantic validation.
- Destructive commands must include `dry_run: bool` parameter in schema.
- Commands using job queue: `use_queue=True` class attribute +
  `register_auto_import_module("ai_editor.commands.<cmd>_command")` in hooks.

**Required `metadata()` fields:**
`name, version, description, category, author, email,`
`detailed_description, parameters, return_value, usage_examples, error_cases, best_practices`

Registered in `hooks_register.py` via `register_custom_commands_hook(_register)`.
`hooks_register.py` also registers all formatters in `FormatterRegistry`.

`mcp_proxy_adapter` auto-generates JSON-RPC, OpenAPI, and MCP tool surface.
Do not implement HTTP routes or API handlers manually.
### Command groups

```
Session:    session_connect, session_reconnect, session_close, session_status
File:       file_open, file_close, file_get, file_send, file_create, file_export_diff
Buffer:     buf_new, buf_save_as, buf_reload, buf_get_state, buf_write_all, buf_mutate_batch,
            buf_export_diff
History:    undo, redo
Edit:       copy, cut, paste
Search:     find, find_one, list_units
Validation: validate, validate_file, formatter_commands
YAML:       yaml_get_command, yaml_update_command, yaml_validate_plan_task
```

### validate_file

```
validate_file(file_path=None, buffer_id=None, project_id=None,
              formatter=auto, schema=None) -> ValidationResult
- buffer_id given: formatter.validate_document on in-memory document.
- file_path given (no buffer_id): project_id required.
  ca_client.download_file -> raw_content -> parse -> validate_document.
- formatter=auto: .yaml/.yml->yaml, .py->cst, .json->json, else->text.
- Does not write files, does not change modified state.
```

### api.py

Thin synchronous wrappers over the session layer. Consumed by CLI and integration tests.
All session/buffer/search/edit operations delegated to session layer.

### CLI

Thin diagnostic wrapper over `api.py`. Target: `ai_editor.interfaces.cli:main`.
Subcommands: `connect`, `disconnect`, `open`, `find`, `copy`, `paste`, `save`, `undo`, `redo`, `validate-file`.

### Config components (owned by ai_editor)

`AiEditorConfig` (`ai_editor/config/config_section.py`)
— dataclass for the `ai_editor` section of `config.json`.
— provides `from_dict()` and `from_config_json()` class methods.

`AiEditorConfigValidator` (`ai_editor/config/config_validator.py`)
— inherits `BaseValidator` from adapter. Called inside adapter's validation pipeline.
— validates `ai_editor` section: threshold syntax, allowed formatter names, etc.
— calls `SimpleConfigValidator` first, then `ai_editor`-specific checks.
— SSL validation delegated to `SSLValidator` from adapter. No duplication.

`AiEditorConfigGenerator` (`ai_editor/config/config_generator.py`)
— inherits `SimpleConfigGenerator` from adapter.
— adds generation of the `ai_editor` section. Calls adapter generator internally, then extends.
— invoked by `aiedmgr generate-config`.

**Full `config.json` structure:**
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "protocol": "https"
  },
  "registration": {
    "enabled": true,
    "auto_on_startup": true,
    "auto_on_shutdown": true,
    "server_id": "ai-editor",
    "server_name": "AI Editor",
    "register_url": "https://mcp-proxy.techsup.od.ua:3004/register",
    "unregister_url": "https://mcp-proxy.techsup.od.ua:3004/unregister",
    "heartbeat_interval": 30,
    "instance_uuid": "<uuid4>"
  },
  "ai_editor": {
    "formatter": {
      "small_file_threshold": "1k",
      "small_file_formatter": "text"
    },
    "sessions": {
      "base_dir": ".ai_editor_sessions"
    }
  }
}
```
Config is JSON only. `ai_editor` does NOT write its own `config.json` — uses a section
inside the adapter's config. Reader: `SimpleConfig.load()` from adapter.

---

## G-007 (plan) — mcp_proxy_adapter integration

Owns: `ai_editor/main.py`, `scripts/aiedmgr`, `config.json` (runtime, not committed).

### Principle

`mcp_proxy_adapter` generates the entire external API surface automatically.
**ai_editor never implements HTTP routes, API handlers, or JSON-RPC manually.**

### Startup sequence (main.py)

```
1. SimpleConfig(config_path).load()                   # adapter config reader
2. AiEditorConfigValidator().validate(model.raw)      # abort if errors
3. AiEditorConfig.from_config_json(config_path)
4. create_app(app_config=model.raw, config_path)      # ASGI app
5. register_custom_commands_hook(register_ai_editor_commands)  # commands + formatters
6. UnifiedServerRunner().run_server(app, server_config)  # hypercorn
```

### Proxy auto-registration

Controlled by `registration` section in `config.json`:
- `auto_on_startup=true`: register at startup, start heartbeat.
- `auto_on_shutdown=true`: unregister on stop.
- `instance_uuid`: UUID4 identifying this server instance on the proxy.
- Retry: up to 5 attempts with exponential backoff. Unreachable proxy: server still starts.

### Service manager (aiedmgr)

Console script in `.venv`:
```
aiedmgr start            — validate config, start in background, write PID
aiedmgr stop             — SIGTERM, wait 30s, SIGKILL
aiedmgr status           — running/stopped, PID, port
aiedmgr restart          — stop + start
aiedmgr generate-config  — run AiEditorConfigGenerator to produce initial config.json
```


PID: `<project_root>/ai_editor.pid`. Log: `logs/ai_editor.log`.
Config from `--config` arg or env `AI_EDITOR_CONFIG`.
Status check: `os.kill(pid, 0)`.
### mcp_proxy_adapter imports used by ai_editor

| Import path | Used for |
|---|---|
| `...core.config.simple_config` | `SimpleConfig`, `SimpleConfigModel`, `SSLConfig` |
| `...core.config.simple_config_generator` | `SimpleConfigGenerator` (base for AiEditorConfigGenerator) |
| `...core.config.simple_config_validator` | `SimpleConfigValidator` (called first in AiEditorConfigValidator) |
| `...core.config.validators.base_validator` | `BaseValidator`, `ValidationError`, `_resolve_path()` |
| `...core.config.validators.ssl_validator` | `SSLValidator.validate_ssl_files()` — all SSL checks |
| `...commands.base` | `Command` base class |
| `...commands.hooks` | `register_custom_commands_hook`, `register_auto_import_module` |
| `...api.app` | `create_app` |
| `...core.server_adapter` | `UnifiedServerRunner` |

### pyproject.toml runtime dependencies

```toml
dependencies = [
  "mcp-proxy-adapter",    # SimpleConfig, Command, create_app, UnifiedServerRunner,
                          # BaseValidator, SSLValidator, register_custom_commands_hook
  "ruamel.yaml>=0.18.0", # YAML formatter: round-trip parse/render, preserves comments
  "jsonpath-ng>=1.6.0",  # YAML formatter: path filters (commands[name=buf_diff])
  "jsonschema>=4.0.0",   # YAML + JSON formatter: schema validation
  "libcst>=1.1.0",       # CST formatter: Python CST parse/render/mutate
                          # _apply_libcst_codegen_compat patched for libcst>=1.8
  "lark>=1.1.0",         # CST formatter: XPath LALR query engine
  "gitpython>=3.1.0",    # Session git: branch-per-buffer, commit on mutation
  "cryptography>=41.0.0",# mTLS cert handling
]
```

---

## G-008 (plan) — Extended formatter backends and cross-formatter conversion matrix

Owns: `ai_editor/formatters/xml/`, `ai_editor/formatters/html/`,
`ai_editor/formatters/markdown/`, `ai_editor/formatters/conversion/`,
`tests/formatters/xml/`, `tests/formatters/html/`, `tests/formatters/markdown/`,
`tests/formatters/conversion/`.

This global step adds three new formatter backends and a cross-formatter
conversion matrix that enables clipboard paste between different formats.

---

### G-008 Part 1 — Markdown formatter

Markdown is promoted from a text-fallback (`.md` registered to TextFormatter)
to a first-class structural formatter.

**Library selection:**
`mistune>=3.0` — pure Python Markdown parser with AST output.
Chosen over alternatives for the following reasons:

| Library | Reason not chosen |
|---|---|
| `markdown` (stdlib-style) | Extension-based, output is HTML only, no AST |
| `commonmark` / `cmark-gfm` | C binding, complex install, no pure-Python AST |
| `mistletoe` | AST available but slower, less maintained |
| `marko` | Good AST but smaller ecosystem, GFM support less mature |
| `mistune>=3` | ✅ Pure Python, AST renderer, GFM support, active maintenance |

New dependency to add to `pyproject.toml`: `mistune>=3.0`.

**Document model:** `list[MdNode]` where `MdNode` is a dataclass wrapping
a mistune AST node with additional fields:
```
MdNode:
  node_type   str   — heading, paragraph, code_block, list, list_item,
                       blockquote, thematic_break, html_block, table,
                       table_head, table_body, table_row, image, link
  level       int | None   — heading level (1-6), None otherwise
  content     str          — raw text content of the node
  children    list[MdNode] — nested nodes (list items, table rows)
  attrs       dict         — node-type-specific attributes (url, alt, lang)
  source_pos  tuple[int,int] | None  — (start_line, end_line) if available
```

**Address model:** `int` (node index at top level) or `"heading:<text>"` (first
heading with matching text). Sub-node address: `"N.M"` (Nth top-level node,
Mth child). Empty address: whole document (`mutate_replace_block` only).

**Registered extensions:** `.md`, `.markdown` — overrides TextFormatter registration
for these extensions. `.txt`, `.rst`, `.log` remain with TextFormatter.

**render_skeleton:**
- Headings shown with level indicator: `# Heading`, `## Sub`, etc.
- Paragraphs: first 60 chars + char count.
- Code blocks: language tag + first line + line count.
- Lists: item count shown, first 3 items previewed.
- Tables: column headers shown, row count.
- Images and links: alt text + url.

**validate_document:** mistune parse round-trip check. All Markdown is valid;
validation only checks that `render(parse(content))` produces equivalent structure
(structural round-trip, not byte-identical — Markdown has no canonical form).

**paste modes:** `append`, `prepend`, `insert_before`, `insert_after`,
`replace_block` (whole node), `replace_range` (line range within text node).

**Clipboard serialization:** `to_string(fragment)` → raw Markdown text of the
fragment. `from_string(body)` → parse body back into `list[MdNode]`.

---

### G-008 Part 2 — XML formatter

**Library selection:**
`lxml>=5.0` — chosen as the primary library.

| Library | Reason not chosen |
|---|---|
| `xml.etree.ElementTree` (stdlib) | No comment preservation, no namespace handling, no XPath 1.0 |
| `minidom` (stdlib) | Verbose API, no XPath, poor large-file performance |
| `beautifulsoup4` with `lxml` | HTML-oriented, lossy for XML |
| `lxml>=5` | ✅ XPath 1.0+, comment nodes, namespace support, C-backed fast parse, ElementTree-compatible API |

New dependency: `lxml>=5.0`.

**Document model:** `lxml.etree._Element` (root element). The document is the
tree rooted at the root element. Comments and processing instructions preserved
as `lxml.etree._Comment` and `lxml.etree._ProcessingInstruction` nodes.

**Address model:** XPath 1.0 expression string.
```
/root/child           — absolute path
//tag                 — any descendant
//tag[@attr='value']  — with attribute
//tag[1]              — first occurrence (XPath 1-based)
```
Non-existent path → `PATH_NOT_FOUND`. Non-unique match when unique expected → `PATH_NOT_UNIQUE`.

**Registered extensions:** `.xml`, `.xsd`, `.xsl`, `.xslt`, `.svg`.

**render:** `lxml.etree.tostring(root, pretty_print=True, encoding='unicode',
xml_declaration=True)`. Preserves attribute order and namespace declarations.

**render_skeleton:**
- Root element shown with tag name, namespace, attribute count.
- First two levels of children shown with tag + first attribute.
- Deeper levels collapsed with child count.
- Text content: first 60 chars if no child elements.
- Comment nodes shown inline as `<!-- ... -->`.

**validate_document:** XML well-formedness check (always done). Optional XSD
validation via `lxml.etree.XMLSchema` if `schema` parameter provided as XSD string.

**paste modes:** `set` (replace element), `append` (add child), `insert_before`,
`insert_after`, `replace_block` (replace subtree).

**Clipboard serialization:** `to_string(fragment)` → `lxml.etree.tostring` of fragment
as unicode string. `from_string(body)` → `lxml.etree.fromstring`.

---

### G-008 Part 3 — HTML formatter

**Library selection:**
`beautifulsoup4>=4.12` with `lxml` parser — chosen for HTML-specific handling.

| Library | Reason not chosen |
|---|---|
| `html.parser` (stdlib) | No tree manipulation, parse-only |
| `lxml.html` | Good but less Pythonic API for tree navigation |
| `html5lib` | Strict HTML5 but very slow, no XPath |
| `beautifulsoup4 + lxml parser` | ✅ Lenient parser, CSS selectors, tree manipulation, wide adoption |

New dependency: `beautifulsoup4>=4.12` (lxml already a dependency from XMLFormatter).

**Document model:** `bs4.BeautifulSoup` object. Preserves original HTML structure
including doctype, comments, and script/style blocks.

**Address model:** CSS selector string.
```
div.container           — tag + class
#main-content           — by id
nav > ul > li           — child combinator
h1, h2, h3              — multiple selectors (returns list)
p:nth-child(2)          — pseudo-class
[data-role="editor"]    — attribute selector
```
Non-existent → `PATH_NOT_FOUND`. Multiple matches when unique expected → `PATH_NOT_UNIQUE`.

**Registered extensions:** `.html`, `.htm`, `.xhtml`.

**render:** `str(soup)` — BeautifulSoup's default serializer. Preserves structure.
`soup.prettify()` used for skeleton rendering only (not for save).

**render_skeleton:**
- Document structure: `<html>`, `<head>` (title, meta count), `<body>` subtree.
- Body: first 3 levels of block elements (div, section, article, nav, main, header, footer).
- Each element: tag + id/class if present + first 60 chars of text content.
- Script and style blocks: shown as `<script>` or `<style>` with byte count only.

**validate_document:** HTML5 structural check via BeautifulSoup parse round-trip.
Optional: check for required elements (`<html>`, `<head>`, `<body>`) in full HTML documents.

**paste modes:** `set`, `append` (add child), `insert_before`, `insert_after`,
`replace_block` (replace element subtree).

**Clipboard serialization:** `to_string(fragment)` → `str(fragment)` (BS4 element
to string). `from_string(body)` → `BeautifulSoup(body, 'lxml').body.next`.

---

### G-008 Part 4 — Cross-formatter conversion matrix

The conversion matrix defines which clipboard paste operations are permitted
between different source and target formatters, and how the conversion is performed.

**Core principle:** when source formatter ≠ target formatter, the clipboard layer
calls `ConversionRegistry.convert(fragment, source_fmt, target_fmt)` before
calling `target_formatter.paste_fragment`. If conversion is not defined →
`CLIPBOARD_FORMAT_MISMATCH`.

**Conversion rule:** `ConversionRule` dataclass:
```
ConversionRule:
  source_formatter   str
  target_formatter   str
  converter          Callable[[fragment, source_fmt_instance, target_fmt_instance] -> fragment]
  lossy              bool   — True if conversion may lose structure/content
  description        str    — human-readable description of what is preserved/lost
```

**ConversionRegistry:**
```
register(rule: ConversionRule) -> None
can_convert(source_fmt: str, target_fmt: str) -> bool
convert(fragment, source_fmt: str, target_fmt: str,
        source_instance, target_instance) -> fragment
list_conversions() -> list[ConversionRule]
```

**Full conversion matrix (v1):**

| Source \ Target | text | markdown | yaml | json | xml | html | cst |
|---|---|---|---|---|---|---|---|
| **text** | ✅ same | ✅ as paragraph | ⚠️ as scalar | ⚠️ as string | ⚠️ as text node | ⚠️ as `<p>` | ❌ |
| **markdown** | ✅ render→text | ✅ same | ⚠️ structure→map | ❌ | ⚠️ render→html→xml | ✅ render→html | ❌ |
| **yaml** | ✅ render→text | ⚠️ as code block | ✅ same | ✅ if JSON-compat | ⚠️ as text node | ⚠️ as `<pre>` | ❌ |
| **json** | ✅ render→text | ⚠️ as code block | ✅ always | ✅ same | ⚠️ as text node | ⚠️ as `<pre>` | ❌ |
| **xml** | ✅ tostring→text | ⚠️ as code block | ⚠️ tag→map | ❌ | ✅ same | ⚠️ lxml.html | ❌ |
| **html** | ✅ get_text() | ✅ html2text | ❌ | ❌ | ⚠️ parse→lxml | ✅ same | ❌ |
| **cst** | ✅ module.code | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ same* |

Legend:
- ✅ — fully supported, lossless or well-defined
- ⚠️ — supported with data loss, conversion is explicitly lossy
- ❌ — not supported, returns `CLIPBOARD_FORMAT_MISMATCH`
- `same*` — CST → CST: cross-buffer paste, stable_id reassigned in target tree

**Conversion descriptions:**

`text → markdown`: wrap text lines as a Markdown paragraph node. Lossless
(text is valid Markdown content).

`text → yaml`: insert text as a YAML scalar string at target address.
Lossy if text contains YAML-special characters (will be quoted).

`text → json`: insert text as a JSON string value at target address. Lossless.

`text → xml`: insert text as a text node in XML. Lossless for plain text;
Lossy if text contains `<`, `>`, `&` (will be escaped).

`text → html`: wrap text in `<p>` tag at target address. Lossless for plain text.

`markdown → text`: `mistune` renders fragment to plain text via text renderer.
Lossy (links become `[text](url)`, formatting stripped).

`markdown → yaml`: serialize each top-level Markdown node as a YAML mapping
`{type: str, content: str, ...}`. Structural but lossy (Markdown formatting lost).

`markdown → xml`: render Markdown to HTML via mistune HTML renderer, then
parse HTML to lxml XML. Lossy (HTML semantics, not Markdown).

`markdown → html`: render Markdown to HTML via mistune. Well-defined, lossy
(Markdown source structure lost, HTML structure created).

`yaml → text`: `ruamel.yaml` dumps fragment to YAML string. Lossless.

`yaml → json`: convert CommentedMap/CommentedSeq to Python dict/list via
`json.loads(yaml.dump(fragment))`. Lossless if no YAML-only types (anchors,
tags, binary). Lossy if YAML-specific types present (they become strings).
Comments lost.

`json → text`: `json.dumps(fragment, indent=2)`. Lossless.

`json → yaml`: `ruamel.yaml.load(json.dumps(fragment))`. Lossless.

`json → markdown`: render JSON as fenced code block in Markdown.
Lossy (structure becomes opaque text).

`xml → text`: `lxml.etree.tostring(fragment, encoding='unicode')`. Lossless
(XML serialization).

`xml → yaml`: convert XML element to YAML mapping `{tag: str, attrs: dict,
children: list, text: str}`. Structural, lossy (namespace info simplified).

`xml → html`: `lxml.html.tostring(lxml.html.fragment_fromstring(xml_str))`.
Lossy if XML uses non-HTML namespaces.

`html → text`: `BeautifulSoup.get_text(separator='\n')`. Lossy (all markup stripped).

`html → markdown`: `html2text` library (new dependency: `html2text>=2020.1.16`).
Lossy (HTML features without Markdown equivalent become plain text).

`html → xml`: `lxml.etree.fromstring(str(fragment))`. May fail on malformed HTML;
returns `CLIPBOARD_FORMAT_MISMATCH` on parse error.

`cst → text`: `fragment.module.code` (full source text). Lossless.

`cst → cst` (cross-buffer): fragment serialized via `CSTFormatter.to_string`,
deserialized via `from_string` in target context. On paste, `_build_tree_index`
assigns new `stable_id` values to all nodes in the pasted fragment — source
`stable_id` values are NOT carried into the target tree. This is by design:
stable_ids must be unique within a tree.

**New dependencies for conversion matrix:**
```
html2text>=2020.1.16   — html → markdown conversion
```
(lxml and beautifulsoup4 already required by XML and HTML formatters)

**ConversionRegistry registration:** in `hooks_register.py`, after all formatters
are registered. All rules registered at startup.

**Error behaviour:** if conversion raises any exception (e.g. lxml parse error
on malformed HTML → XML), the clipboard layer catches it and returns
`CLIPBOARD_FORMAT_MISMATCH` with `details.conversion_error` field set.

---

### G-008 Part 5 — Formatter registration updates

Registration order in `hooks_register.py` (updated):
```
1. text:     .txt .log .rst .ini .cfg .toml   (no longer .md .markdown)
2. yaml:     .yaml .yml
3. json:     .json
4. cst:      .py
5. markdown: .md .markdown                    (overrides text for these)
6. xml:      .xml .xsd .xsl .xslt .svg
7. html:     .html .htm .xhtml
```

Updated `pyproject.toml` dependencies (additions only):
```toml
"mistune>=3.0",         # Markdown formatter: AST parse/render
"lxml>=5.0",            # XML formatter + HTML formatter lxml backend
"beautifulsoup4>=4.12", # HTML formatter: lenient parse, CSS selectors
"html2text>=2020.1.16", # Conversion: HTML → Markdown
```

`small_file_formatter` config option extended: now accepts `text`, `yaml`, `cst`,
`markdown`, `xml`, `html` (any registered formatter name).

---

## G-009 — Unified DocumentNode graph and CA-aligned preview envelope

Owns: `ai_editor/formatters/` (refactor), `ai_editor/sessions/` (preview wiring),
`tests/formatters/`, `tests/sessions/`, `docs/plans/ai_editor/viewer_features.yaml`.

Corrective global step: closes the gap between G-003 design (one Tree, one preview
protocol) and implementation drift (parallel `TreeNode` graph vs `CSTTree`, string
`render_skeleton` instead of structured navigation). Does not change session git,
clipboard, or command registration semantics.

### Formatter three-part architecture

Every formatter backend is exactly three cooperating parts plus a shared base.
The base class owns the in-memory graph, stable identifiers, structural mutations,
preview navigation, and sidecar persistence. Subclasses supply conversion only.

```
Part 1 — Reader (C-076):
  read(source) -> un-ID'd tree structure
  Maps raw file bytes/text into DocumentNode subtree(s) without stable_id.
  Whole-file entry: parse(raw_content). Block entry: node_from_source(raw_block).
  Reader never assigns stable_id and never performs structural ops.

Part 2 — Classifier (C-073 FormatterClassifier):
  Per-format node_kind vocabulary and parent-child rules.
  Reader output is classified: each node gets node_kind from the registry.
  Python: libcst type names. JSON: root, object, objectProp, array, primitive.
  YAML: mapping, sequence, scalar, mappingItem. Text: document, paragraph, line.
  Classifier validates that children match allowed kinds for the parent kind.

Part 3 — Exporter (C-078):
  export(tree) -> native source bytes
  Maps DocumentGraph back to native file format. Called only on explicit export
  (write / write_all) — NOT on every edit mutation; NOT on file_send.
  Whole-file: render(tree). Block: node_to_source(node).
  Output never contains stable_id markers.
```

AbstractFormatter orchestration:
```
ingest(raw_native):
  nodes = Reader.parse(raw_native)
  Classifier.validate_and_tag(nodes)
  graph = base.assign_stable_ids(nodes)   # ONCE per open/reload
  write_tree_file(graph)
  return graph

mutate(graph, op):
  graph = base.apply_op(graph, op)
  write_tree_file(graph)                  # every change; ids in tree file
  return graph

export(graph):                            # write command only
  raw = Exporter.render(graph)            # no stable_id markers
  write_native_session_file(raw)          # <buffer_id>.<ext>
  modified = False
  # file_send relays this file separately; does not call export
```

Subclass implements Reader + Classifier hooks + Exporter hooks only.
Base never parses syntax; subclass never insert/delete/move or assign stable_id.

### Tree file — session working copy (binding)

Native project file and session tree file are **different artifacts** with
different roles. stable_id markers live in the **tree file on disk**, never in
committed native source.

```
Lifecycle:

1. INGEST (once per open/reload):
   native_bytes = read project or CA download
   graph = Reader.parse(native_bytes) -> Classifier -> assign_stable_ids ONCE
   write_tree_file(session_dir/<buffer_id>.tree, graph)   # ids persisted here
   git commit "open: ..."                                  # snapshot for undo

2. EDIT (all subsequent operations):
   graph = load_tree_file(session_dir/<buffer_id>.tree)   # ids restored from disk
   graph = mutate(graph, ...)                              # in-memory only
   write_tree_file(session_dir/<buffer_id>.tree, graph)   # after EVERY change
   git commit "<op>: ..."                                    # undo/redo via session git
   # Native format is NOT written here. Exporter is NOT called here.

3. EXPORT (explicit **write** / `write_all` only — NOT send, NOT mutate):
   native_bytes = Exporter.render(graph)
   validate -> write native session file (<buffer_id>.<ext> in session dir)
   modified=False
   # Project/CA upload is a separate **send** step.
```

Invariants:
- stable_id assigned **once** at first ingest indexing; stored in tree file body.
- Tree file is **source of truth** for editing after first ingest; native file
  is read once, written only on export.
- Every tree or node-data mutation → `write_tree_file` + git commit (unchanged
  count → skip both).
- Undo/redo: git branch `buf/<buffer_id>` + redo_stack; restores tree file
  snapshot from commit, not re-parse from native source.
- Native source never contains stable_id markers (no `# @node-id`, no embedded
  UUID blocks in `.py`, `.json`, etc.).

Tree file format (all formatters, unified protocol):
```
TREE_V1 fmt=<formatter_name> sha256=<native_sha_at_last_export_or_ingest> tree_sha256=<body>
<JSON or format-specific serialisation of DocumentGraph including stable_id per node>
```
Python may use `.cst` extension and `CST_TREE_V1` header variant; same semantics.

Session `.buf` file (if retained): holds **last exported native snapshot** for
CA diff/display only, OR is removed in favour of tree-only session storage —
implementation choice in T-002/T-008. Editing mutations do **not** require
re-exporting native content to `.buf`.

### Structural insert protocol (base class, all formats)

Uniform address model: `stable_id` (UUID4). Insert target: parent stable_id +
position token:

```
position:
  "first"              — first child
  "last"               — last child (default)
  "before:<stable_id>" — immediately before sibling
  "after:<stable_id>"  — immediately after sibling
  <0-based integer>    — explicit sibling index

content: raw block source; base calls Reader.node_from_source(content),
         Classifier tags kind, base links under parent at position.
```

Same position vocabulary for `paste_fragment`. `replace_node` preserves the
target node's stable_id; only body/subtree content changes via Exporter/Reader
block conversion.

### stable_id — static identity in tree file (base class)

**Invariant:** stable_id is assigned once at first ingest indexing and never
reassigned. IDs are persisted **in the tree file on disk** and in-memory
DocumentNode. They do **not** appear in native source on disk.

Persistence model (primary):
```
ingest  -> assign_stable_ids -> write_tree_file (ids in tree body)
mutate  -> update graph      -> write_tree_file (same ids preserved where identity preserved)
export  -> Exporter.render   -> native bytes WITHOUT id markers
```

Survival through in-memory mutation (secondary, CST and similar):

When a backend must re-parse a **temporary** native string inside one operation
(e.g. libcst string round-trip), **StableIdTransfer** (C-079) may embed ids into
that transient string, mutate, then reconcile back into the graph before
`write_tree_file`. This is an in-memory implementation aid only:
```
(a) embed:  read stable_id from graph -> inject into transient parse string
(b) mutate: backend operates on transient string
(c) extract: reconcile ids into graph; transient string discarded
```
Transient Python markers: `# @node-id: <uuid4>`. Never written to tree file as
source text substitution; never written to native export. Tree file stores ids
in its serialised node map directly.

Object-identity reuse (when parser returns same object references without
re-parse string): snapshot metadata_map -> mutate -> re-index -> inherit stable_id.

Structural delete removes node and descendants from graph and tree file map.
Insert creates new nodes with new UUID4 only. Move/reparent preserves stable_id.
replace_node preserves target stable_id; only subtree content changes.

### Design intent

Every supported format is a **typed node graph**, not a format-specific second
document model. Python CST is one **node_kind vocabulary** among several; libcst
is the parse/render backend for `.py`, not a separate structural paradigm.

AbstractFormatter owns exactly one in-memory **DocumentGraph** (C-074) whose nodes
are **DocumentNode** (C-070). Subclasses implement **Reader** (C-076), **Classifier**
(C-073), and **Exporter** (C-078) hooks; they populate DocumentNode trees with
format-specific `node_kind` values from **FormatterClassifier** registry.

### DocumentNode

Single node type for all formats. Replaces the split where generic buffers used
`TreeNode` while Python buffers loaded `CSTTree`.

```
DocumentNode:
  stable_id     str UUID4          — address for mutations and drilldown (base-assigned)
  node_ref      str                — stable navigation key exposed in preview (UUID or path slug)
  node_kind     str                — format-registered kind (see FormatNodeKindRegistry)
  type          str                — coarse class: module | mapping | sequence | scalar | block | line | ...
  start_line    int 1-based inclusive
  end_line      int 1-based inclusive
  display_text  str                — one-line summary for blocks list
  metadata      dict               — format-specific attrs (name, key, docstring, json_pointer, ...)
  children      list[DocumentNode] — eager or lazy-loaded; same type recursively
  source_span   optional byte/line span for render round-trip
```

Invariants (base class enforced):
- Every node has unique `stable_id`; assigned once at ingest, persisted in tree file.
- `node_ref` stable across `replace_node`; delete drops ids from tree file map.
- Subclasses never assign stable_id or perform structural ops.
- Edit mutations persist tree file + git commit; Exporter not invoked.
- Native source never contains stable_id markers.

### FormatterClassifier (node_kind registry)

Per-format catalog of allowed `node_kind` values and parent-child rules (Part 2).

```
Python (.py):  Module, FunctionDef, ClassDef, If, For, While, Try, With,
               SimpleStatementLine, Import, Assign, AnnAssign, ... (libcst type names)
JSON (.json):  root, object, objectProp, array, primitive
YAML (.yaml):  mapping, sequence, scalar, mappingItem (key+value pair node)
Text (.txt):   document, paragraph, line
Markdown (.md): document, heading, paragraph, code_block, list, list_item, ...
```

JSON **objectProp** is mandatory: each object key is a node whose children are
key scalar + value subtree (not key embedded only in metadata).

Sidecar / tree file serialisation stores full DocumentGraph including stable_id
map. CST `.cst` path is Python extension variant of the same tree-file protocol.

`ingest` / buffer open: Reader.parse → assign_stable_ids once → write_tree_file.
Forbidden: open empty stub tree then fork parallel CSTTree on first mutate.
Forbidden: call Exporter on every mutation (native re-export is export-only).

### PreviewEnvelope (replaces string-only model API preview)

Model-facing preview is a structured envelope aligned 1:1 with code-analysis-server
`universal_file_preview` semantics (focus + blocks + drilldown). Internal
`render_skeleton(...) -> str` may remain as a debug/legacy helper but **must not**
be the sole preview returned by buffer/session commands.

```
PreviewEnvelope:
  focus:
    text          str    — annotated source for the current view (line UUIDs, JSON pointer
                           prefixes, or MD slug markers as appropriate)
    node_ref      str | null — ref of the focused node; null at file root
    start_line    int
    end_line      int
    total_lines   int
  blocks:
    - node_ref    str
      node_kind   str
      display_text str
      start_line  int
      end_line    int
      child_count int | null
  navigation:
    drilldown_param   str   — parameter name accepted by preview command ("node_ref")
    collapsed         bool  — true when children omitted due to size policy
    total_blocks      int
  format_meta:
    formatter_name    str
    format_group      str
```

**PreviewNavigator** (C-072) implements collapse policy and drilldown:
- Small file: full annotated `focus.text` + complete `blocks` list.
- Large file at root: `focus.text` may be omitted or truncated; `blocks` carries
  top-level summaries only; model drills via `node_ref`.
- Drilldown request with `node_ref` returns a new PreviewEnvelope scoped to that
  subtree (same shape, narrower focus).
- NQ-008 (no-self-content-child): when focus node has children, `blocks` lists
  children only; scalar leaf returns `total_blocks=0`, `blocks=[]`.

Parity target: for the same file bytes and `node_ref`, ai_editor PreviewEnvelope
field semantics match code-analysis `universal_file_preview` (C-075 CAPreviewParity).
Live cross-check reference: `code_analysis` project
`docs/plans/ai_editor/viewer_features.yaml` sections `/feature_gaps`, `/preview_envelope`.

Per-format preview behaviour (binding):
- **Python**: line-annotated `focus.text` with `[uuid]` prefixes; top-level
  `FunctionDef`/`ClassDef` in `blocks`; drilldown by stable UUID.
- **JSON**: JSON Pointer prefixes `[/path]` in text; large root may expose full
  text; drilldown e.g. `/server` returns annotated subtree.
- **YAML**: large root returns `blocks` summaries only; drilldown yields annotated
  subtree; small files may return full annotated text.
- **Markdown**: small files — annotated lines + block list; large files — section
  slug tree; `node_ref` is uuid5 or slug path.
- **Text / InvalidOnOpen**: `windowed_preview(offset, limit)` unchanged; PreviewEnvelope
  wraps sliding window in `focus.text` with line numbers.

### AbstractFormatter preview contract (updated)

```
build_preview(document, node_ref=None, options=None) -> PreviewEnvelope
get_unit(document, address) -> FormatterUnit   # address = stable_id; unchanged
```

`build_preview` replaces `render_skeleton` as the command-layer entry point.
`BufferState.preview`, `file_open` return value, and `buf_get_state.preview` field
carry PreviewEnvelope (serialised dict), not a bare string.

`ingest` / buffer load: load tree file → in-memory DocumentGraph. On first open
from native: Reader.parse → assign_stable_ids once → write_tree_file.
Forbidden: parallel CSTTree fork. Native export on **write** only; send is relay.

### Buffer command semantics (write / send / close / mutate)

G-009 defines authoritative semantics for the tree-era buffer model. Supersedes
G-005 buffer lifecycle steps where they conflate mutation, export, and relay.

**Session artifacts per open buffer:**

```
  <buffer_id>.tree        — DocumentGraph + stable_ids (authoritative for edit)
  <buffer_id>.<ext>            — native session copy (after approved write)
  <buffer_id>.<ext>.pending    — temp export awaiting model approve/reject
  <buffer_id>.baseline.<ext>   — diff baseline
  git branch buf/<buffer_id> — undo/redo snapshots of tree file commits
```

**modified flag:**

```
False — after ingest (tree written, no edits yet) OR after write/export (native file current)
True  — after any tree mutation; native session file stale or absent
```

**Four command classes:**

| Command class | API examples | Operates on | Persists | modified |
|---------------|--------------|-------------|----------|----------|
| **Tree mutate** | buf_mutate_batch, copy, cut, paste, undo, redo | in-memory tree | tree file + git commit | → True |
| **Write (export)** | file_write, buf_write_all | tree → native | diff gate + confirm; skip if identical | → False |
| **Export diff** | file_export_diff, buf_export_diff | tree vs baseline | preview only; no write | unchanged |
| **Send (relay)** | file_send | native session file only | CA upload | unchanged |
| **Close** | file_close | session artifacts | deletes tree + native | n/a |

**Send never touches the tree.** Send never exports. Preconditions for send:
`modified=False` (write/export must have run first). Send uploads the native
session file to CA by `file_id` (project resolved from file_id). Optional
`unlock=True` releases CA lock after successful upload.

**Close** deletes `<buffer_id>.tree`, `<buffer_id>.<ext>`, git branch, buffer
entry. If buffer is CA-locked → `session_close_file` (unlock). Close after
edit without send is allowed with `force=True` or when `modified=False`; with
`modified=True` and `force=False` → `FILE_HAS_UNSENT_CHANGES`.

#### Existing file in project (remote open)

```
 1. file_open(lock=True|False):
      lock=True  → session_open_file + download; locked=True, readonly=False
      lock=False → download only; locked=False, readonly=True (no lock ⇒ RO)
 2. ingest: Reader.parse → assign_stable_ids ONCE
 3. write_tree_file; git commit "open: …"; modified=False
 4. [edit loop — allowed in RO and RW]
    4a. tree mutate (write_tree_file + git commit; modified=True)
 5. file_write(approve=None): diff + .pending temp if has_changes
    file_write(approve=True): promote .pending → native; modified=False
    file_write(approve=False): delete .pending; nothing else changes
 6. file_send: relay native file — **RW only**
 7. file_close: delete tree + native; unlock if locked
```

RO open (`lock=False`): steps 5–6 forbidden. Step 4 and 7 allowed. Close freely even if modified.

#### New file (not yet in project)

```
 1. file_create / buf_new: tree from initial_content; modified=True (no native yet)
 2. file_write: export tree → native session file; modified=False
 3. file_send(project_id, relative_path, file_id after create?, lock?=flag):
      upload to CA; optionally session_open_file (lock)
    - if lock requested: buffer stays open, locked=True
    - if lock NOT requested: file_close immediately (delete tree + native; no unlock needed)
```

Send for new files uses `project_id` + project-relative `file_path`. CA returns
`file_id` stored on buffer for subsequent send/close/unlock.

#### Close without send (edited remote file)

```
file_close(force=False): modified=True → FILE_HAS_UNSENT_CHANGES
file_close(force=True):  delete tree + native session file; session_close_file if locked
```

Readonly buffers: close freely; no lock; tree + native removed.

### Export diff before write (binding)

Any **write/export** and the standalone diff command share one comparison:

```
baseline_native  — bytes at file_open ingest (CA download) or after last confirmed write
candidate_native — Exporter.render(current tree)

ExportDiffResult:
  identical          bool   — true when baseline == candidate (no write needed)
  has_changes        bool
  unified_diff       str    — unified diff text for model display
  hunks              list   — structured [{op, start_line, end_line, lines_added, lines_removed, preview}]
  baseline_sha256    str
  candidate_sha256   str
  baseline_line_count int
  candidate_line_count int
```

Rules:
- **identical** → no `.pending` created; return OK; `modified=False`.
- **preview** (`approve=None`, has_changes) → write `.pending` temp; return diff.
- **approve=True** → promote `.pending` to native file; update baseline; delete temp.
- **approve=False** (model rejected) → **delete `.pending` temp**; baseline, tree,
  `modified`, native session file unchanged; return `success=True, cancelled`.
- **file_export_diff** — in-memory diff only; never creates `.pending`.
- Diff callable in RO mode (preview only; cannot approve).
- `write_all` applies same gate per buffer (batch `approve` param).

Ingest stores baseline: copy downloaded bytes to `<buffer_id>.baseline.<ext>` at open.
New buffer: baseline empty or equals `initial_content` until first write updates it.

### Migration constraints

- Refactor in place under `ai_editor/formatters/`; no new parallel `cst/` document
  class hierarchy alongside DocumentGraph.
- Existing stable_id sidecar JSON remains valid; loader migrates records to
  DocumentNode without changing UUIDs.
- Command schemas updated: `preview` property type becomes object (PreviewEnvelope),
  not string; metadata documents drilldown worked example per format.
- G-008 extended formatters (Markdown, XML, HTML) consume DocumentNode kinds when
  implemented; G-009 does not implement G-008 backends but defines the node model
  they must use.

### viewer_features.yaml (ai_editor plan)

Project-local tracker for preview parity gaps and CA cross-checks. Updated as
G-009 implementation progresses. Binding for G-009 coverage; references CA live
file for upstream gaps (elif/else drilldown, etc.).

---

## Error model

All typed error codes for `ErrorCode` enum:

```
# Session
SESSION_NOT_FOUND, SESSION_LOCK_CONFLICT, SESSION_HAS_UNSAVED_BUFFERS,
SESSION_READONLY, SESSION_HAS_UNSENT_FILES

# Buffer
BUFFER_NOT_FOUND, BUFFER_ALREADY_OPEN, BUFFER_HAS_UNSAVED_CHANGES,
BUFFER_STALE, BUFFER_INVALID, BUFFER_LOCKED, BUFFER_READONLY

# File
FILE_HAS_UNSENT_CHANGES

# Formatter
FORMATTER_NOT_FOUND, FORMATTER_UNSUPPORTED,
FORMATTER_COMMAND_DISCOVERY_FAILED, FORMATTER_COMMAND_SCHEMA_INVALID,
FORMATTER_COMMAND_UNSUPPORTED, FORMAT_VALIDATION_FAILED,
FORMAT_INVALID_ON_OPEN

# Address / path
PATH_PARSE_FAILED, PATH_NOT_FOUND, PATH_NOT_UNIQUE,
TARGET_TYPE_MISMATCH, ADDRESS_INVALID, ADDRESS_NOT_FOUND, ADDRESS_NOT_UNIQUE

# Search
SEARCH_QUERY_INVALID, SEARCH_NO_MATCH, SEARCH_NOT_UNIQUE,
SEARCH_SCOPE_INVALID, FORMATTER_SEARCH_UNSUPPORTED

# Clipboard
CLIPBOARD_EMPTY, CLIPBOARD_ITEM_NOT_FOUND, CLIPBOARD_FORMAT_MISMATCH,
CLIPBOARD_SOURCE_STALE, CLIPBOARD_INVALID_MODE

# YAML
YAML_PARSE_FAILED, SCHEMA_VALIDATION_FAILED, SEMANTIC_VALIDATION_FAILED,
RENDER_NOT_DETERMINISTIC, CHANGED_PATH_MISMATCH

# CST
CST_PARSE_FAILED

# Validation
VALIDATION_FAILED

# Mutation
MUTATION_ROLLBACK, PRE_WRITE_VALIDATION_FAILED

# Write
WRITE_FAILED, BACKUP_FAILED, SAVE_TARGET_EXISTS, SAVE_TARGET_MISSING

# History
UNDO_AT_BEGINNING, REDO_AT_END, HISTORY_UNAVAILABLE,
GIT_COMMIT_FAILED, GIT_NOT_AVAILABLE
```
## Code Analysis Server — Known Quirks and Feature Gaps

This section is **non-binding** (does not produce concepts or GS coverage).
It exists as a reference for implementors to avoid repeating known issues
when working with the code-analysis-server API.

**Live reference file** (regularly updated, always check before implementing
a new interaction with the server API):

```
project:   code_analysis
project_id: 8772a086-688d-4198-a0c4-f03817cc0e6c
file_path:  docs/plans/ai_editor/viewer_features.yaml
sections:   /bugs, /yaml_write_quirks, /feature_gaps
```

### Sidecar (.py files) — known issues (all fixed as of 2026-05-21)

- **sidecar_replace_elif_wrong_node** — `replace` with an `elif`-body
  `stable_id` landed on the statement *before* the `If` block.
  Root cause: `embed_stable_ids_into_tree` inserted `@node-id` markers
  without rebuilding the position index; shifted line numbers caused
  `find_node` to promote nested hits to `module.body`.
  Fix: `_logical_to_module_line_map` + `_iter_compound_statement_branches`
  in `tree_modifier_ops_find.py`.

- **sidecar_code_lines_double_newline** — `insert` with `code_lines`
  produced a blank line after every statement.
  Root cause: `code_lines` elements already contain a trailing `\n`;
  `'\n'.join()` produced double newlines.
  Fix: `join_code_lines()` in `tree_modifier_ops_parse.py` strips
  trailing `\n` before joining.

- **replace_else_branch_cst_error** — `replace` of a `SimpleStatementLine`
  inside an `else`-body raised `'Else' object is not iterable`.
  Root cause: `_iter_compound_statement_branches` did not handle
  `If.orelse` when it contained a plain `else` (`cst.Else` node,
  not another `If`).
  Fix: `isinstance` check for `cst.Else` added.

### universal_file_open — initial_content quirks (fixed 2026-05-21)

- `.json` and generic (`else`) branches ignored `initial_content` on
  `create=True` and always wrote the default.
  Fix: uniform `initial_content` handling applied to all branches
  in `open_command.py`.

### YAML write quirks (tree-temp format)

`universal_file_open create=True` writes `initial_content` as-is before
YAML parsing. Two classes of content cause a parse failure and a
silent fallback to text mode:

- **Unquoted colon in value** — `key: value containing: colon` is
  interpreted as a nested mapping. Plain scalars containing `': '`
  are illegal in block mappings (PyYAML scanner error).
  Workaround: quote string values that contain `': '`.

- **Inline comment on bare value** — a `# comment` appended to a
  bare scalar causes a parse error.
  Workaround: do not include inline comments in `initial_content`.

Fix applied: `_fix_yaml_string_values()` called before write in
`open_command.py` (branch `elif suffix in ('.yaml', '.yml')`).

### Feature gaps (open)

- **elif_else_drilldown** (task: `fix-preview-drilldown-elif-else-branches`)
  — `node_view` for an `If` node exposes only the `if`-branch body.
  `elif` / `else` / `except` / `finally` clauses are not addressable
  as separate drill-down nodes; their body `stable_id`s cannot be
  obtained via preview.
  **Impact on ai_editor**: when implementing sidecar edits targeting
  `elif`/`else`/`except`/`finally` bodies, do not assume the stable_id
  is directly available from a standard preview call. Use
  `_iter_compound_statement_branches` workaround or wait for the
  server-side fix.

<!-- /non-binding -->
