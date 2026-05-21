<!-- source_spec.md — Level 1 Source Specification (ai_editor plan) -->
<!-- Renamed from tech_spec.md. Standard: plan_standard_machine.yaml v1.0 -->
<!--
  PLAN STANDARD NOTES:
  - Canonical session identifier: session_key (UUID4). Do NOT use session_id.
  - G-step numbering in this file follows plan file structure (G-001..G-007, G-008).
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

### Session git (single repository)

The system uses **one git repository per session**, located at `<session_dir>/git/`.
There is no project git. The CA server manages its own versioning (backup + commit on upload).

**Session git:**
- Created when a session is created (non-bare repository).
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
  Has a file lock under `ca_session_id`. On `file_close` without `file_send` + `modified=True` + `force=False` → `FILE_HAS_UNSENT_CHANGES`.
  On `force=True` → `session_close_file` + delete artifacts.
- `readonly=True`: close freely regardless of `modified`. Not counted in unsent-files check.
- `modified` is set `True` after every mutation; reset to `False` only after `file_send`.

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
  modified           bool — True after any mutation; False after file_send
  readonly           bool — set at open, never changes
  readonly           bool
  buf_file_path      str — session-space path to .buf file
  saved              bool — True after upload_save
  redo_stack         list[str] — SHA list for redo
```

### AbstractBuffer public contract

```
open(session_key, project_id, file_path, formatter=auto,
  open_as_text=False, readonly=False) -> buffer_id
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

- On open: `ca_client.lock_file(ca_session_id, project_id, file_id)` + `download_content(...)`
  → `{content_bytes, file_id}`. `BUFFER_LOCKED` if held by another CA session.
- `readonly=True` → no lock acquired, buffer not counted in isolation checks.
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

**Acquiring a lock — on remote buffer open:**

- Pre-check existing locks via `session_list_file_locks`. If the file is held by a different
  CA session → `BUFFER_LOCKED`, no content is fetched.
- Otherwise `session_open_file(ca_session_id, project_id, file_id)` acquires the lock (idempotent;
  `acquired=false` if this same session already holds it), then transfer-download fetches content.
- `file_id` is resolved via `list_project_files`; required for `session_open_file`.
- `readonly=True` → no lock acquired; the buffer is not counted in isolation checks.

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
open(readonly=False)  → session_open_file(ca_session_id, file_id)   → file locked, buffer.locked=True
open(readonly=True)   → no lock
save(close=False)     → transfer_upload_save                       → content written, lock kept
save(close=True)      → transfer_upload_save → session_close_file   → content written, lock released, buffer removed
write_all()           → transfer_upload_save                       → lock kept, buffer stays open
close()               → session_close_file(ca_session_id, file_id) → lock released, local copy + branch removed
session.close()       → session_close_file for ALL locked files     → then delete entire session dir (git + artifacts)
startup_sweep         → session_close_file for orphaned ses_settings locks → then delete session dir
```

CA session itself (`session_delete`) is **never** touched — it outlives the editor.

`ca_session_id` (session-level) and `buffer.locked` (per buffer) are stored in `ses_settings.json`
and survive process restart, enabling lock release on startup_sweep even if the editor process that
acquired the lock has crashed.


### save pipeline

```
1. formatter.validate_document(document) → abort on failure
2. raw_content = formatter.render(document)
3. ca_client.upload_file(project_id, relative_path, raw_content.encode(),
   commit_message)  → content written; lock kept (unlock is a separate step)
4. buffer.modified = False, buffer.saved = True
5. If buffer was local (relative_path=None): set relative_path from response → now remote.
6. If close=True: ca_client.unlock_file(ca_session_id, project_id, file_id)
   → remove buffer from ses_settings.json. Otherwise buffer stays open with lock held.
```

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

- `write_buf(content, path)` — atomic write, no backup. For `.buf` session files only.
- `write_result(content, path)` — backup + atomic write + read-back verification.
  For local derived artifacts only (e.g. CST sidecar). NOT for project files.

Project files: written only via `ca_client.upload_file`. Never via write_result.

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
  # position: first | last | <0-based index among siblings>
  # content is raw block source; base calls node_from_source() to build the node,
  # then inserts the returned node under parent_address at position.
delete(tree, address) -> tree
move(tree, address, target_parent_address, position) -> tree
replace_node(tree, address, content) -> tree
  # edits node content in place: base calls node_from_source(content),
  # swaps the node body, and PRESERVES the existing stable_id of that node.
mutate_batch(tree, operations) -> tree    # atomic ordered list of structural ops
multiple_replace(tree, [(address, content), ...]) -> tree   # many replace_node in one call

# Fragments / clipboard (structure handled by base; body via subclass converters)
copy_fragment(tree, source_address) -> fragment
cut_fragment(tree, source_address) -> (tree, fragment, changed_addresses)
paste_fragment(tree, target_parent_address, position, fragment) -> (tree, changed_addresses)

# Identity (owned entirely by the base class)
#  - stable_id is assigned by the base class to every node.
#  - editing a node's content via replace_node preserves its stable_id.
#  - structural ops (insert/delete/move) maintain stable_id integrity.
#  - subclasses never assign, read, or depend on stable_ids.

# Write orchestration (base class; uniform for all formats)
write(tree, path) -> WriteResult
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

### Unified tree model and sidecar for every format

The parsed document of EVERY format is a tree of nodes. A sidecar tree file is
built next to the source file (the same way it was originally done only for
`.py`/CST). Preview and navigation work identically for all formats over this
tree. The format-specific part is only the conversion between tree nodes and
the concrete source (the subclass converters above).

```
TreeNode:
  stable_id      UUID assigned by the base class
  node_kind      str   — format-defined node category
  start_line     int   — line range in source (1-based, inclusive)
  end_line       int
  display_text   str    — representation shown in skeleton/preview
  metadata       dict
  children       list[TreeNode]
```

Sidecar locations (generalised from CST to all formats):

```
Session-side:  <session_dir>/<buffer_id>.tree    — written after every mutation
Project-side:  <dir>/.tree/<stem>.tree           — written on save, next to source

TREE_V1 fmt=<formatter_name> sha256=<source_sha256> tree_sha256=<tree_body_sha256>
<JSON body: serialised node map {stable_id -> {node_kind, start_line, end_line,
            display_text, metadata, children}}>
```

The `source_sha256` in the header is the freshness check of the tree against
the source file. stable_id identity survives mutations via the base-class
protocol: snapshot previous node map -> apply mutation -> reindex -> match new
nodes to old by object identity, so ids do not drift.

### Source of truth and auto-create

- **At open time** the source of truth is the **source file**.
- **After open, once editing begins** the source of truth is the **tree file**.
- The necessary condition for the tree file to become the source of truth is
  the buffer's **`modified` flag being set** (set on the first mutation).
- This rule previously applied only to CST; it now applies to **every format**.

Auto-create of the tree:

- If the **preview command does not find a tree file**, it first creates the
  tree automatically, then works with the tree.
- The same happens **immediately after a file is fetched from the analysis
  server**: the tree is built right away.

### Display-quirk reference (analysis server)

Format display and preview behaviour has known quirks that are discovered
during real use of the analysis-server project. The reference list is the live
file below; it is updated regularly and MUST be consulted when implementing or
changing any format's parse/render/skeleton behaviour, especially display:

```
project:    code_analysis
project_id: 8772a086-688d-4198-a0c4-f03817cc0e6c
file_path:  docs/plans/ai_editor/viewer_features.yaml
sections:   /bugs, /yaml_write_quirks, /feature_gaps
```

See also the non-binding "Code Analysis Server — Known Quirks and Feature Gaps"
section at the end of this document.

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
Text is a tree, not a flat line list. Two node levels only:

```
tree model:
  root
   └─ paragraph        — block of lines separated from neighbours by blank line(s)
        └─ line         — a single line node inside a paragraph

rule: paragraphs are split by blank line(s) between blocks.
      if there are NO blank lines between blocks, the whole file is ONE paragraph.

node_kind:      paragraph | line
address:        node stable_id (uniform with all formats)
converters (subclass):
  parse(raw)            -> paragraph/line tree
  render(tree)          -> text (paragraphs rejoined with blank lines, lines with newlines)
  node_from_source(raw) -> paragraph node (or line node) from raw block text
  node_to_source(node)  -> raw block text of the paragraph/line
linters:        none (plain text always valid)
Registered extensions: .txt .log .rst .ini .cfg .toml
```
### YAML formatter
Tree of mapping/sequence/scalar nodes with round-trip preservation (comments,
key order, formatting via ruamel). Structure, navigation, mutation, and
identity are owned by the base class (uniform with all formats). The subclass
provides only the converters.

```
node_kind:      mapping | sequence | scalar
address:        node stable_id (uniform with all formats)
converters (subclass):
  parse(raw)            -> tree (ruamel round-trip load; CommentedMap/Seq -> nodes)
  render(tree)          -> YAML text; round-trip: render(parse(x)) preserves x
                           (comments, key order, formatting)
  node_from_source(raw) -> node/subtree from a raw YAML fragment
  node_to_source(node)  -> raw YAML fragment of the node
linters:        YAML parse; optional jsonschema; plan_task_v1 semantic checks
                (format==plan_task_v1; kind in [spec,global,tactical,atomic];
                 depends_on is list[str]; commands[].name unique;
                 commands[].schema.required references existing properties;
                 verification non-empty; status in
                 [draft,ready_for_review,ready_for_implementation,blocked])
Write quirks (initial_content before parse): unquoted ': ' in a value and an
  inline comment on a bare value break parsing — see Display-quirk reference
  and viewer_features.yaml /yaml_write_quirks. Quote such values.
Registered extensions: .yaml .yml
```
### JSON formatter
Tree of mapping/sequence/scalar nodes. Structure, navigation, mutation, and
identity are owned by the base class (uniform with all formats). The subclass
provides only the converters.

```
node_kind:      mapping | sequence | scalar
address:        node stable_id (uniform with all formats)
converters (subclass):
  parse(raw)            -> tree (stdlib json; dict/list/scalar -> nodes)
  render(tree)          -> json.dumps(indent=2, ensure_ascii=False)
  node_from_source(raw) -> node/subtree from a raw JSON fragment
  node_to_source(node)  -> raw JSON fragment of the node
linters:        JSON parse (+ optional jsonschema)
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
No TTL. No auto-deletion.

Session directory layout:
```
<sessions_base_dir>/<session_key>/
  ses_settings.json       — session attributes and open buffer list
  git/                    — non-bare git repository
    buf/<buffer_id>       — one branch per open buffer
  <buffer_id>.<ext>       — buf file (full source, not skeleton)
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
2. ca_client.lock_file(ca_session_id, project_id, file_id); content_bytes, file_id = ca_client.download_content(
     project_id, relative_path, readonly=False, ca_session_id=ca_session_id)
   readonly=True: no lock acquired (no session_open_file).
3. formatter.parse(content) -> document.
4. write_buf(source_content, buf_file_path).
5. Git commit on buf/<buffer_id>: "open: <relative_path>".
6. add_buffer_to_settings: file_type='remote', locked=True, redo_stack=[].
7. Return buffer_id and render_skeleton(document).
```

**new (unsaved buffer):**
```
1. FormatterRegistry.get_by_name(formatter_name).
2. No CA download. No file lock.
3. formatter.parse(initial_content) -> document.
4. write_buf(source_content, buf_file_path).
5. Git commit: "new: <display_name>".
6. add_buffer_to_settings: relative_path=None, file_type='local',
   readonly=False, modified=True, redo_stack=[].
7. Return buffer_id and render_skeleton(document).
```

**mutation (MANDATORY write+commit after every change):**
```
1. Readonly check: session.readonly or buffer.readonly -> BUFFER_READONLY.
2. Execute formatter method.
3. If unchanged: return, no write, no commit.
4. write_buf(source_content, buf_file_path).
5. modified=True, redo_stack=[] written atomically to ses_settings.
6. Git commit: "<command>: <params_summary>".
   gitpython failure -> HISTORY_UNAVAILABLE diagnostic, continue.
   Upload to CA server does NOT happen here.
```

**save (always explicit — no auto-save):**
```
1. formatter.validate_document(document) -> abort on failure.
2. raw_content = formatter.render(document).
3. ca_client.upload_content(...) -> content written; lock kept (no auto-unlock).
4. modified=False, saved=True in ses_settings.
5. If close=True: ca_client.unlock_file(ca_session_id, project_id, file_id),
   then remove buffer from ses_settings.json. Otherwise buffer stays open with lock held.
```

**reload (remote buffers only):**
```
1. Validate file_type='remote'. Local -> BUFFER_INVALID.
2. ca_client.download_content(..., readonly=True). No lock (no session_open_file).
3. formatter.parse(content). Error -> BUFFER_INVALID.
4. write_buf. Git commit: "reload: <relative_path>".
5. modified=False, redo_stack=[] in ses_settings.
6. Return render_skeleton(document).
```

**close:**
```
1. modified=True without force -> error.
2. formatter.delete(buf_file_path).  # removes buf file + derived artifacts
3. if locked and not saved: ca_client.unlock_file(ca_session_id, project_id, file_id).
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
  branch.set_commit(target). write_buf. Persist redo_stack.
  UNDO_AT_BEGINNING if no parents.

redo(session_key, buffer_id, steps=1):
  Pop SHA from redo_stack (LIFO). REDO_AT_END if empty.
  branch.set_commit(target). write_buf. Persist redo_stack.
  redo_stack survives restart (lives in ses_settings.json).

New mutation clears redo_stack atomically.
```

### Clipboard

Session-scoped. Stored in `<session_dir>/clipboard.json` as `{formatter, body}`.

```
copy: copy_fragment -> to_string -> clipboard.json -> git commit.
     Does NOT mutate document. Does NOT set modified=True.
cut:  cut_fragment -> to_string -> clipboard.json -> write_buf -> commit.
     Sets modified=True and redo_stack=[] atomically.
paste: read clipboard -> check formatter match -> from_string -> paste_fragment -> write_buf -> commit.
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
For each open buffer where readonly=False:
  if not modified: skipped.
  validate_document -> failure: failed_buffers.
  transfer_upload_save(unlock_after_write=False) -> failure: failed_buffers.
  success: written_buffers, modified=False.
  relative_path=None (local, unsaved): skipped silently.
  File lock NOT released (session_close_file is a separate close step).
Result: success=True only if all eligible buffers succeeded.
```

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
File:       file_open, file_close, file_get, file_send, file_create
Buffer:     buf_new, buf_save_as, buf_reload, buf_get_state, buf_write_all, buf_mutate_batch
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
FORMATTER_COMMAND_UNSUPPORTED, FORMAT_VALIDATION_FAILED

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

# Write
WRITE_FAILED, BACKUP_FAILED, SAVE_TARGET_EXISTS, SAVE_TARGET_MISSING

# History
UNDO_AT_BEGINNING, REDO_AT_END, HISTORY_UNAVAILABLE,
GIT_COMMIT_FAILED, GIT_NOT_AVAILABLE
```
<!-- non-binding -->

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
