# AI Editor — Technical Specification

Product: **ai_editor** — a universal document editor for AI models and MCP servers.
Editing operates on structural paths and formatter units, not raw line ranges.
Line ranges are an emergency fallback only.

---

## Architecture: three independent layers

```
Session
  └─ owns: session directory, session git, buf files, clipboard, session attributes
       │
Buffer
  └─ owns: binding of one file to one formatter, modified flag, write-lock
       │
Formatter
  └─ owns: parse, render, validate, write, open, close, delete,
            copy, cut, paste, search, replace, and format-specific commands
```

Formatters do not know about sessions or buffers.
Buffers do not know about other buffers or sessions.
Sessions coordinate buffers and own session git history and clipboard.

### Two git repositories

The system maintains two completely separate git repositories:

**Session git** (`<session_dir>/git/`):
- Created when a session is created.
- One branch per open buffer: `buf/<buffer_id>`.
- A commit is made on every operation that mutates the buffer.
- This is the undo/redo mechanism — any buffer state can be recovered as long as the session exists.
- Clipboard operations (`copy`, `cut`) also produce commits in session git.
- Deleted together with the session directory when the session is closed.

**Project git** (the project's own repository):
- Used only on explicit `save` / `save_as` — i.e. after content is transferred from buffer to the real project file.
- Records stable, intentional checkpoints of the project source.
- Never touched during buffer mutations, clipboard operations, or session lifecycle operations.

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
- **SessionKey** — type alias: `str` (UUID4)
- **SessionDescriptor** — `session_key`, `open_buffers (list[BufferDescriptor])`, `diagnostics`
- **BufferDescriptor** — `buffer_id`, `session_key`, `filename`, `relative_path`, `formatter`, `modified (bool)`, `readonly (bool)`, `buf_file_path`

Rules:
- All subsystems import contracts only from `ai_editor/contracts/`.
- No subsystem edits another subsystem’s owned paths.
- No subsystem patches `.venv`, `venv`, `site-packages`.
- CLI entry point `ai-editor = ai_editor.interfaces.cli:main` is declared here in `pyproject.toml` but implemented in G-009.

---

## G-002 — Editor core and buffer registry

Owns: `ai_editor/editor_core/`, `ai_editor/config/`, `ai_editor/writer.py`, `tests/editor_core/`.

### Buffer model

One buffer = one open document. Buffer is bound to a file and a formatter at open time.
Both never change for the lifetime of the buffer.

```
buffer fields:
  buffer_id          UUID4, stable for the lifetime of the buffer
  file_path          absolute path to the real project file (null for unsaved)
  filename           bare filename, e.g. README.yaml
  relative_path      path relative to project root (null for unsaved)
  formatter          formatter name, set at open, never changes
  modified           bool — True if buffer diverges from real file on disk
  readonly           bool — set at open, never changes
```

`modified` is set to `True` after every mutation.
`modified` is reset to `False` after a successful `save` or `save_as`.

### AbstractBuffer public contract

```
open(session_key, file_path, formatter=auto, open_as_text=False, readonly=False) -> buffer_id
new(session_key, formatter, display_name) -> buffer_id
save(session_key, buffer_id) -> OperationResult
save_as(session_key, buffer_id, file_path, overwrite=False) -> OperationResult
close(session_key, buffer_id, save=False|True|error_if_dirty)
reload(session_key, buffer_id)
get_state(session_key, buffer_id) -> BufferState
get_formatter(session_key, buffer_id) -> AbstractFormatter
validate(session_key, buffer_id) -> ValidationResult
write_all(session_key, force=False) -> WriteAllResult
```

### Open rules

- One `file_path` cannot have two open buffers in the same session.
- Repeated `open` of an already-open file returns the existing `buffer_id`.
- `formatter=auto`: resolve by file extension via formatter registry.
- `open_as_text=True`: always use text formatter regardless of extension or size.
- If `len(raw_content) < small_file_threshold` (config): use text formatter, `buffer_status=small_file`.
- If structural formatter raises on parse: fall back to text formatter, `buffer_status=format_fallback`.
- Precedence: `open_as_text` > `small_file_threshold` > `parse_error_fallback` > extension auto-detect.
- On open: acquire file edit lock (`files.editing_pid`, `files.session_key`). Return `BUFFER_LOCKED` if another live process holds it.

### Save pipeline

`save` and `save_as` are the only operations that write the real project file.

```
1. formatter.validate_document(document)  → abort on failure
2. formatter.render(document)             → raw_content string
3. stale check: verify editing_pid = os.getpid()
4. formatter.write(raw_content, file_path)  → backup + atomic write + read-back
5. modified = False
6. update current_hash
```

`validate(buffer_id)` calls `formatter.validate_document` without writing anything.
It is called explicitly and as the first stage of `save`/`save_as`.

### BufferAddress

```
BufferAddress:
  buffer_id   str
  address     Any  — opaque to editor core, interpreted only by formatter
```

`copy` and `cut` require `source: BufferAddress`.
`paste` requires `target: BufferAddress` and `mode`.
Editor core never parses or interprets address content.

### writer.py

Two write paths used by editor core and session layer:

- `write_buf(content, path)` — atomic write, no backup, no read-back. Used for `.buf` session files after every mutation.
- `write_result(content, path)` — backup before write + atomic write + read-back verification. Used for real project files on `save`/`save_as`.

Default `AbstractFormatter.write(content, path)` delegates to `write_result`.
Formatters may override `write` to persist additional artifacts (e.g. CST sidecar).

### Config

Read from `mcp_proxy_adapter` `config.json`, section `ai_editor`.

```json
{
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

Threshold units: bare integer = chars, `k` = thousands, `m` = millions, `0` = disabled.

---

## G-003 — AbstractFormatter and text/YAML formatter backends

Owns: `ai_editor/formatters/base.py`, `ai_editor/formatters/registry.py`,
`ai_editor/formatters/text/`, `ai_editor/formatters/yaml/`,
`ai_editor/schemas/`, `ai_editor/models.py`, `tests/formatters/`.

### AbstractFormatter required contract

Every formatter must implement all of the following:

```
# Document lifecycle
parse(raw_content) -> document
render(document) -> raw_content
write(content, path) -> None          # default: delegates to writer.write_result; override for extra artifacts

# Validation (same three-level chain as write)
validate_content(raw_content, *, file_path=None, schema=None, options=None) -> ValidationResult
validate_document(document, *, schema=None, options=None) -> ValidationResult
validate(document) -> ValidationResult   # alias for validate_document

# Mutation
mutate_set(document, address, value) -> document
mutate_replace_block(document, address, value) -> document
mutate_append(document, address, value, *, dedupe=False) -> document
mutate_delete(document, address) -> document
mutate_move(document, address, target_address) -> document

# Fragment operations (copy / cut / paste)
copy_fragment(document, source_address) -> fragment
cut_fragment(document, source_address) -> (document, fragment, changed_addresses)
paste_fragment(document, target_address, fragment, mode) -> (document, changed_addresses)

# Search
normalize_address(address) -> normalized_address
get_unit(document, address) -> unit
iter_units(document, scope) -> Iterator[unit]
match_unit(unit, query) -> bool | score
compare_units(unit_a, unit_b, options) -> ComparisonResult
diagnostics(document) -> list[Diagnostic]

# Discovery
list_commands() -> FormatterCommandCatalog
```

Required class attributes:

```
formatter_name          str
supported_payload_kinds list[str]
supported_address_kinds list[str]
supported_paste_modes   list[str]
can_render_to_text      bool
can_parse_from_text     bool
```

Forbidden in formatters:
- Open, save, or close files for buffer lifecycle.
- Own buffer registry or stale disk checks.
- Perform git operations.
- Know about `session_key`, `.buf` files, or session directory.

### Validation is a three-level chain

The same chain applies to validate and to write:

```
Formatter level:  formatter.validate_content(raw)  or  formatter.validate_document(doc)
Buffer level:     buffer.validate(buffer_id)        → calls formatter.validate_document
Session level:    session.write_all()               → calls buffer.validate per buffer
```

Validation always precedes write. Write is rejected on any validation failure.

### FormatterCommandCatalog

```
FormatterCommandCatalog:
  formatter_name     str
  formatter_version  str
  standard_commands  list[FormatterCommandMetadata]
  specific_commands  list[FormatterCommandMetadata]
  openapi_schemas    dict
  diagnostics        list

FormatterCommandMetadata:
  name             str
  kind             'standard' | 'formatter_specific'
  description      str
  input_schema     dict  (OpenAPI-compatible)
  output_schema    dict
  openapi_operation str
  side_effects     list[str]
  writes_files     bool
  requires_buffer  bool
  requires_file_path bool
  examples         list
```

`standard_commands` covers all `AbstractFormatter` methods.
`specific_commands` are formatter-defined; must have OpenAPI-compatible schemas.
Commands that write derived artifacts (e.g. CST sidecar export) must set `writes_files=true`.

### FormatterUnit

Minimum fields for all formatters:

```
address       Any   — opaque; matches BufferAddress.address semantics
unit_kind     str
display_text  str
metadata      dict
```

Formatter-specific subclasses may add fields.

### Text formatter

```
document model:  list[str]  (array of lines)
address model:   int (line index) | tuple[int,int] (inclusive range) | None (whole doc)
unit model:      line | line range | text block
payload kinds:   text_lines, text_block
paste modes:     insert, replace_range, append, prepend
```

`validate_content` and `validate_document` always return `success=True`.

`compare_units` semantics: exact text, normalized text, substring, regex, line number, range overlap.

Registered extensions: `.txt`, `.md`, `.log`, `.rst`, `.ini`, `.cfg`, `.toml`, `.json` (fallback).

### YAML formatter

```
document model:  ruamel.yaml CommentedMap / CommentedSeq (round-trip)
address model:   structural YAML path
unit model:      yaml_node | scalar | mapping | sequence_item
payload kinds:   yaml_node, yaml_block, rendered_text
paste modes:     set, replace_block, append, insert_before, insert_after
```

YAML address syntax:

```
top_level_key
dotted.path.to.key
list[0]
commands[name=buf_diff]
commands[name=buf_diff].metadata.best_practices
commands[name=buf_diff].metadata.best_practices[1]
```

Address rules:
- Empty path allowed only for `mutate_replace_block` (whole-document replace).
- Non-existent path → `PATH_NOT_FOUND`.
- Non-unique list filter match → `PATH_NOT_UNIQUE`.
- Mapping order and comments preserved where `ruamel.yaml` allows.
- `render(parse(render(doc))) == render(doc)` (deterministic).
- Mutation returns `changed_paths` list matching normalized addresses.

`validate_content`: YAML parse + optional JSON schema + `plan_task_v1` semantic checks + render determinism check.
`validate_document`: same checks on in-memory document.
Write rejected if any check fails.

`compare_units` semantics: node type, key, scalar value, normalized scalar value, mapping fields, list item identity, semantic name field (e.g. `name=buf_diff`).

### plan_task_v1 semantic validation

```
- format == plan_task_v1
- node_id matches file level conventions
- kind in [spec, global, tactical, atomic]
- depends_on is a list of strings
- commands is a list of objects
- commands[].name values are unique
- commands[].schema.required references only existing properties
- read_model.sees_live_tmpfs_worktree = false for read-only disk commands
- verification is a non-empty list
- status in [draft, ready_for_review, ready_for_implementation, blocked]
```

### Clipboard compatibility

```
text  → text   allowed
yaml  → yaml   allowed
yaml  → text   allowed only when mode explicitly requests rendered_text
text  → yaml   rejected by default; allowed only with explicit parse_as_yaml mode
other → CLIPBOARD_FORMAT_MISMATCH
```

If source buffer changed after `copy`/`cut`:
- default policy: `snapshot` (use payload from copy time)
- alternative: `reject_if_source_revision_changed` → `CLIPBOARD_SOURCE_STALE`

### Emergency fallback

```
yaml_read_lines           read by line range (diagnostic use only)
yaml_write_lines_unsafe   write by line range (emergency repair only)
```

Names are intentionally alarming. Not part of normal workflows.

### YAML compatibility wrappers (legacy names → new architecture)

```
yaml_load          → buffer.open + formatter.parse
yaml_write_checked → buffer.save / buffer.save_as
yaml_validate      → buffer.validate (calls formatter.validate_document)
yaml_get           → search.find_one or formatter.get_unit
yaml_get_command   → search.find_one with YAML name query
yaml_set           → formatter.paste_fragment(mode=set)
yaml_replace_block → formatter.paste_fragment(mode=replace_block)
yaml_append        → formatter.paste_fragment(mode=append)
yaml_delete        → formatter.cut_fragment + discard
yaml_move          → formatter.cut_fragment + formatter.paste_fragment
yaml_clipboard_*   → editor copy/cut/paste + clipboard internals
```

Compatibility wrappers do not define the architecture. They are thin adapters.

---

## G-004 — Universal search (AbstractSearch)

Owns: `ai_editor/search/`, `tests/search/`.

Search is a separate layer. It does not open or write files.
It asks the buffer for its document and formatter, then uses formatter unit APIs.

### AbstractSearch contract

```
find(session_key, buffer_id, query, scope=None) -> list[match]
find_one(session_key, buffer_id, query, scope=None) -> match | error
list_units(session_key, buffer_id, scope=None) -> list[unit]
select(session_key, buffer_id, query, policy) -> address | list[address] | error
```

Search calls:
```
formatter.iter_units(document, scope)
formatter.match_unit(unit, query)
formatter.compare_units(unit_a, unit_b, options)
```

Returned addresses are suitable for direct use in `BufferAddress` for copy/cut/paste.

### Query model

```
base fields:  kind, value, options
formatter-specific queries allowed

examples — text:
  {kind: contains_text, value: "buf_diff"}
  {kind: regex, value: "^## "}

examples — yaml:
  {kind: field_equals, field: name, value: buf_diff}
  {kind: node_type, value: mapping}
```

### Match result

```
buffer_id, formatter, address, unit_kind, display_text, metadata
```

`find` returns zero or more matches.
`find_one` returns exactly one or a typed error: `SEARCH_NO_MATCH` | `SEARCH_NOT_UNIQUE`.

---

## G-005 — ForeignFormatter

Owns: `ai_editor/formatters/foreign.py`, `tests/formatters/foreign/`.

`ForeignFormatter` implements `AbstractFormatter` but delegates all operations
to an external server via OpenAPI calls through `mcp-proxy-adapter`.

Required configuration:
```
formatter_name, openapi_endpoint, mcp_server_id,
command_mapping, timeout_policy, error_mapping
```

Strict rules:
- Transport-level success is NOT formatter success.
- Nested `result.success=false` must map to local failure.
- Missing nested `result.success` → `FOREIGN_FORMATTER_CONTRACT_VIOLATION`.
- Timeout → `FOREIGN_FORMATTER_TIMEOUT`.
- Transport exception → `FOREIGN_FORMATTER_FAILED`.
- `ForeignFormatter` does not open, save, or close files.
- `ForeignFormatter.write()` uses default `writer.write_result`.
- `list_commands()` calls external OpenAPI discovery and normalizes to `FormatterCommandCatalog`.


Example uses:
```
.ts  → ForeignFormatter backed by TypeScript AST server
.go  → ForeignFormatter backed by language-specific server
```

---

## G-006 — CST formatter (.py files)

Owns: `ai_editor/formatters/cst/`, `tests/formatters/cst/`.
CST is a built-in formatter, not a ForeignFormatter.
Source: adapted from `cst-code/` — only tree operations and XPath queries are carried over.
Storing identifiers inside source file code is forbidden and must not be used.

Registered for extension `.py`, formatter name `cst`.

### Document model: CSTTree

```
tree_id       runtime UUID
module        libcst.Module
metadata_map  node_id -> TreeNodeMetadata (carries stable_id)
node_map      node_id -> libcst.CSTNode
root_node_id  stable_id of module root
```

Public address for callers: `stable_id` (UUID4). `node_id` is internal.

### stable_id contract

- Assigned once per node at first `_build_tree_index`. Value = UUID4. Never reassigned.
- Stored in `TreeNodeMetadata.stable_id` and in sidecar `metadata_map`.
- Survives mutations via `previous_metadata_map` snapshot + `previous_obj_to_id` mapping.
- Never written into `.py` source in any form. Never visible in `render()` output.

### Sidecar

Two locations:
```
Session-side:  <session_dir>/<buffer_id>.cst   — written after every mutation
Project-side:  <py_dir>/.cst/<py_stem>.tree    — written on save/save_as
```

Format:
```
Line 1: CST_TREE_V1 sha256=<source_sha256> tree_sha256=<tree_body_sha256>
Line 2+: JSON body
```

Two checksums validated on load. Either mismatch → rebuild from scratch.

### write() override

CSTFormatter overrides `AbstractFormatter.write()` to write:
1. `.py` source file (via `writer.write_result`)
2. project-side sidecar `.cst/<stem>.tree`

### Default read format: declarative (skeleton)

When buffer opens a `.py` file, the view returned is the declarative skeleton, not full source.

Skeleton shows (all prefixed with `[stable_id]`):
```
file docstring
import statements
class definition headers + docstrings + properties
method signatures + docstrings
function signatures + docstrings
```

Method and function bodies show: `# Implementation hidden; request node by stable_id`

Full source of any node: `get_unit(document, stable_id)`

### Mutation operations

```
insert(parent_stable_id, position, code)   position: first|last|after:<stable_id>
delete(node_stable_id)
move(node_stable_id, parent_stable_id, position)
replace(node_stable_id, code)
replace_docstring(node_stable_id, text)
```

### iter_units

Iterates over all nodes in the CST tree by recursive descent.
Every subtree node is yielded, including nested classes, methods, and functions.
Returns nodes as `FormatterUnit` with `stable_id` as address.

### match_unit

Current implementation: comparison by `stable_id` only.
Two units match if and only if their `stable_id` values are equal.

### compare_units

Structural comparison:
- Node type must match.
- Node data must match.
- Children are compared recursively.
- If any child does not match → the nodes are not equal.

### Clipboard serialization

Fragment serialization uses the static method:
```
CSTFormatter.to_string(fragment) -> str
```
The resulting string is stored as `body` in `clipboard.json`.
On paste, `body` is deserialized back to a CST fragment before insertion.

### Specific commands (CST formatter only)

```
cst_query(selector) — XPath-like queries over the CST tree
  Queries operate on tree structure only.
  Examples:
    //FunctionDef[@name='foo']
    class > method:first
    Def:*[start_line>=100]
    function[@name^='_']:not([name^='__'])
  Returns: list of nodes in declarative format.
  Full body of any node: get_unit(stable_id)

cst_get_skeleton()      — declarative overview with stable_id prefixes
cst_get_unit(stable_id) — full source of one node including body
cst_list_units()        — flat list: stable_id, type, kind, name, qualname, start_line, end_line
```

### validate_document

Compiles `tree.module.code` via Python `compile()` built-in.
Returns syntax diagnostics. Does not write files.


---

## G-008 — Session layer

Owns: `ai_editor/sessions/`, `tests/sessions/`.

### Session: general principles

A session is a directory on disk. It exists as long as its directory exists.
There is no TTL and no auto-deletion. If the `session_id` is known, the session is accessible.

The session directory is the editor's working space:

```
<sessions_base_dir>/<session_id>/
  ses_settings.json       — session attributes and list of open buffers
  git/                    — bare git repository (one per session)
    buf/<buffer_id>       — one branch per open buffer
  <buffer_id>.<ext>       — buffer file (copy of the project file at open time)
  clipboard.json          — current clipboard state
```

Session attributes (`ses_settings.json`):

```
session_id     UUID4, assigned once at connect, never reused
created_at     ISO-8601 datetime
readonly       bool (default false) — all buffers in this session are readonly
save_always    bool (default false) — see save_always mode below
open_buffers   list of buffer descriptors
```

### Buffer lifecycle inside a session

**Step 1 — Session create (if not exists)**

Create session directory. Write `ses_settings.json`. Initialize bare git repo at `<session_dir>/git/`.

**Step 2 — open**

```
Input: session_id, file_path

1. Determine formatter by file extension (formatter registry).
2. Copy project file to session directory as <buffer_id>.<ext>.
3. Call formatter.open(buf_file_path):
   - Reads buf file content.
   - Returns initial document view (text: raw content; CST: skeleton; YAML: tree summary).
4. Write buf file to disk immediately (formatter.write).
5. Git commit on branch buf/<buffer_id>: message "open: <file_path>".
6. Update ses_settings.json.
7. Return buffer_id and initial document view to caller.
```

**Step 3 — client requests an action**

Any action on the buffer routes through the session to the formatter.

**Step 4 — readonly check (for mutating actions)**

```
If session.readonly=True  → return BUFFER_READONLY
If buffer.readonly=True   → return BUFFER_READONLY
```

**Step 5 — execute formatter command**

Call the corresponding formatter method (mutate_set, paste_fragment, cut_fragment, etc.).

**Step 6 — if document did not mutate**

Return result directly. No write, no commit.

**Step 7 — if document mutated**

```
1. formatter.write(rendered_content, buf_file_path)  — write buf file immediately
2. buffer.modified = True
3. Git commit on buf/<buffer_id>: message "<command>: <params_summary>"
   — one commit per command, even if command touched multiple fragments
   — if gitpython fails: attach HISTORY_UNAVAILABLE diagnostic, continue
```

**Step 8 — save_always mode**

If `session.save_always=True`:

```
1. formatter.validate_document(document)  → abort and return error on failure
2. formatter.write(rendered_content, real_file_path)  — write to project file immediately
3. buffer.modified = False
```

In `save_always` mode the project file is always in sync with the buffer.
No explicit `save` command is needed. Validation failure blocks the write and the command is still considered failed.

**Step 9 — explicit save command (when save_always=False)**

```
1. formatter.validate_document(document)  → abort on failure
2. formatter.render(document)             → raw_content
3. formatter.write(raw_content, real_file_path)  — backup + atomic write + read-back
4. buffer.modified = False
5. Git commit in project git repo: "<formatter_name>: save <relative_path>" (best-effort)
```

**Step 10 — close**

```
1. If buffer.modified=True and close called without save=True → return error
   Unless close_unsaved=True is explicitly passed.
2. Call formatter.delete(buf_file_path) — formatter removes its session artifacts
   (buf file, CST sidecar, any derived files).
3. session.clear_buf(buffer_id):
   - Delete branch buf/<buffer_id> from session git.
   - If the branch’s commits are the last remaining reference to those objects:
     git gc or pack-refs to reclaim space.
4. Remove buffer from ses_settings.json open_buffers.
```

**Step 11 — close session**

Delete session directory entirely including git repo, all buf files, clipboard.json.

### Undo / redo

```
undo(session_id, buffer_id, steps=1)
  → git checkout HEAD~steps on buf/<buffer_id> branch
  → reload buffer document from that commit
  → formatter.write(content, buf_file_path)  — update buf file
  → if save_always=True: also write real file
  Returns UNDO_AT_BEGINNING if already at first commit.

redo(session_id, buffer_id, steps=1)
  → move HEAD forward by steps commits
  Returns REDO_AT_END if already at latest commit.
```

Any new mutation after undo creates a new commit and permanently discards the redo future.
This is identical to standard git branch behavior.

### Clipboard

Clipboard is a separate object, session-scoped. Stored in `<session_dir>/clipboard.json`.

Clipboard item attributes:
```
formatter   name of the formatter that produced the payload
body        serialized string representation of the copied/cut fragment
```

**copy / cut:**
- The selected fragment is serialized to a string by the source formatter.
- The result is written to `clipboard.json` as `{formatter, body}`.
- Every `copy` or `cut` produces a commit in session git:
  ```
  git commit: "clipboard: copy <address>"
  git commit: "clipboard: cut <address>"
  ```
- Because every clipboard state is a session git commit, any previous clipboard
  content can be recovered from session git history for the lifetime of the session.

**paste:**
- Content is read from `clipboard.json`.
- If `clipboard.formatter` ≠ formatter of the target buffer → operation is rejected
  with `CLIPBOARD_FORMAT_MISMATCH`. No partial paste occurs.
- If formatters match → `body` is deserialized and inserted at the target address.

Clipboard is deleted when the session directory is deleted (session close).
Cross-session paste is not supported.

### write_all

```
write_all(session_id, force=False) -> WriteAllResult

For each open buffer where readonly=False:
  if force=False and modified=False: add to skipped_buffers, continue
  formatter.validate_document(document)  → on failure: add to failed_buffers, continue
  formatter.write(content, real_file_path)  → on failure: add to failed_buffers
  on success: add to written_buffers, git commit in project repo
  Unsaved buffers (file_path=None): add to skipped_buffers silently

Result: success=True only if all eligible buffers succeeded.
Session remains open on partial failure.
```

### Session public API

```
connect(readonly=False, save_always=False) -> SessionDescriptor
reconnect(session_id) -> SessionDescriptor
close_session(session_id) -> void
session_status(session_id) -> SessionDescriptor
```

Note: no TTL. No `idle_timeout_seconds`. No `startup_sweep` that deletes sessions.
Stale file locks from crashed processes are released on next `open` via `editing_lock_holder_is_alive` check.

---

## G-009 — Command layer and public interfaces

Owns: `ai_editor/commands/`, `ai_editor/hooks_register.py`,
`ai_editor/api.py`, `ai_editor/interfaces/cli.py`, `tests/commands/`, `tests/interfaces/`.

### Command registration

All commands follow `docs/metadatastd.md`:

```
ai_editor/commands/<name>_command.py    — Command subclass
ai_editor/commands/<name>_schema.py    — get_schema() -> dict (JSON Schema)
ai_editor/commands/<name>_metadata.py  — metadata() -> dict
```

Registered in `hooks_register.py`:
```python
from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook

def _register(registry):
    registry.register(OpenCommand, 'custom')
    registry.register(SaveCommand, 'custom')
    # ... all commands

register_custom_commands_hook(_register)
```

`mcp-proxy-adapter` auto-generates JSON-RPC, OpenAPI, and MCP tool surface from `get_schema()` and `metadata()`.
Do not implement HTTP routes or API handlers manually.

### Standard editor commands (all formatters)

Session commands:
```
connect, reconnect, close_session, session_status
```

Buffer commands:
```
open, new, close, save, save_as, reload, get_state, write_all
```

History commands:
```
undo, redo
```

Edit commands (use BufferAddress):
```
copy, cut, paste
```

Search commands:
```
find, find_one, list_units
```

Validation commands:
```
validate          — validate in-memory buffer (calls formatter.validate_document)
validate_file     — validate file by path or buffer_id without writing
formatter_commands — return FormatterCommandCatalog for a formatter or buffer
```

### validate_file

```
validate_file(file_path=None, buffer_id=None, formatter=auto, schema=None) -> ValidationResult

Rules:
- If buffer_id given: call formatter.validate_document on in-memory document
- If file_path given (no buffer_id): read raw content, call formatter.validate_content
- formatter=auto: resolve by file extension
- Does not write files, does not change buffer modified state
- Returns: diagnostics, errors, warnings, formatter_name, file_path, buffer_id
```

Formatter resolution by extension:
```
.yaml, .yml     → yaml formatter
.py             → cst formatter
.txt, .md, etc. → text formatter
future: .json   → json formatter
```

### YAML-specific commands

```
yaml_get_command(buffer_id, command_name)
  → find_one with YAML query {kind: field_equals, field: name, value: command_name}

yaml_update_command(buffer_id, command_name, patch)
  → open + find + mutate_set per patch field + write buf

yaml_get_verification(buffer_id)
yaml_append_verification(buffer_id, item, dedupe=True)
yaml_validate_plan_task(buffer_id | file_path)
```

### CLI

Thin diagnostic wrapper over `api.py`. Console script target: `ai_editor.interfaces.cli:main`.

Supports: `connect`, `disconnect`, `open`, `find`, `copy`, `paste`, `save`, `undo`, `redo`, `validate-file`.

---

## Error model

All typed error codes for `ErrorCode` enum (G-001/T-004):

```
# Session
SESSION_NOT_FOUND
SESSION_LOCK_CONFLICT
SESSION_HAS_UNSAVED_BUFFERS
SESSION_READONLY

# Buffer
BUFFER_NOT_FOUND
BUFFER_ALREADY_OPEN
BUFFER_HAS_UNSAVED_CHANGES
BUFFER_STALE
BUFFER_INVALID
BUFFER_LOCKED
BUFFER_READONLY

# Formatter
FORMATTER_NOT_FOUND
FORMATTER_UNSUPPORTED
FORMATTER_COMMAND_DISCOVERY_FAILED
FORMATTER_COMMAND_SCHEMA_INVALID
FORMATTER_COMMAND_UNSUPPORTED
FORMAT_VALIDATION_FAILED

# Foreign formatter
FOREIGN_FORMATTER_FAILED
FOREIGN_FORMATTER_TIMEOUT
FOREIGN_FORMATTER_CONTRACT_VIOLATION

# Address / path
PATH_PARSE_FAILED
PATH_NOT_FOUND
PATH_NOT_UNIQUE
TARGET_TYPE_MISMATCH
ADDRESS_INVALID
ADDRESS_NOT_FOUND
ADDRESS_NOT_UNIQUE

# Search
SEARCH_QUERY_INVALID
SEARCH_NO_MATCH
SEARCH_NOT_UNIQUE
SEARCH_SCOPE_INVALID
FORMATTER_SEARCH_UNSUPPORTED

# Clipboard
CLIPBOARD_EMPTY
CLIPBOARD_ITEM_NOT_FOUND
CLIPBOARD_FORMAT_MISMATCH
CLIPBOARD_SOURCE_STALE
CLIPBOARD_INVALID_MODE

# YAML-specific
YAML_PARSE_FAILED
SCHEMA_VALIDATION_FAILED
SEMANTIC_VALIDATION_FAILED
RENDER_NOT_DETERMINISTIC
CHANGED_PATH_MISMATCH

# CST-specific
CST_PARSE_FAILED

# Validation
VALIDATION_FAILED

# Write
WRITE_FAILED
BACKUP_FAILED
SAVE_TARGET_EXISTS
SAVE_TARGET_MISSING

# History
UNDO_AT_BEGINNING
REDO_AT_END
HISTORY_UNAVAILABLE
GIT_COMMIT_FAILED

# Rename (G-007)
RENAME_TARGET_NOT_FOUND
RENAME_INVALID_IDENTIFIER
RENAME_GIT_CHECKPOINT_FAILED
RENAME_ROLLBACK_FAILED
GIT_NOT_AVAILABLE
```