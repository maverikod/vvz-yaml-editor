# Engine Mechanics Analysis — preview / edit / stable_id

> Source of truth for re-implementing the universal edit engine from scratch in `ai_editor`.
> Extracted from CA-server engine: `cst-code/code_analysis/core/cst_tree/*`,
> `cst-code/code_analysis/core/mutable_cst/*`, and the MCP command wrappers in
> `ai_editor/ported/universal_file_edit/*`.
> NOT a port. This captures the *behaviour to reproduce* on this project's own terms.

---

## 0. Three format groups

| group     | extensions              | node_ref kind            | engine backing                     |
|-----------|-------------------------|--------------------------|------------------------------------|
| text      | .md .txt .rst .adoc     | 0-based line index       | none — raw line list               |
| tree-temp | .json .yaml .yml        | RFC6901 JSON Pointer     | TreeNode roots, in-memory mutate   |
| sidecar   | .py                     | stable UUID              | CST tree, full rebuild per op      |

The two non-trivial engines are **tree-temp** and **sidecar**. They handle
identity (stable_id) in fundamentally different ways. This is the core of the analysis.

---

## 1. stable_id — the durable handle (universal principle)

From `cst_tree/models.py` and `node_id_markers.py`:

- **stable_id**: a UUID assigned **once at node creation**. NEVER changes across
  any rebuild caused by insert/delete/replace. This is the durable, user-facing handle.
- **node_id**: a *positional / span-based* identifier (e.g. `start:end` span key).
  MAY be reassigned after every index rebuild. Internal only.
- Persistence rule: when writing markers/sidecar to disk, the engine persists
  **stable_id, not node_id**, so that after any rebuild the persisted value is
  always the original UUID assigned at node creation.

**Implication for re-implementation:** every node carries two identities.
The public API (preview output, edit op addressing) speaks **stable_id**.
The internal mutation layer speaks **node_id / position**. A resolve step
maps stable_id -> current node_id before each mutation.

---

## 2. sidecar (.py) — full-rebuild-per-op model

Reference: `ported/universal_file_edit/sidecar_cst_apply.py` (the wrapper logic),
backed by `cst_tree/tree_builder.py`, `tree_metadata.py`, `tree_modifier.py`.

### 2.1 Batch lifecycle (`run_sidecar_cst_edit_batch`)

1. **Snapshot before batch** for rollback:
   - `batch_original_code = tree.module.code`
   - `batch_original_tree_id`
   - `batch_original_metadata = dict(tree.metadata_map)`
2. If session has no live tree -> `load_file_to_tree(abs_path)` rebuilds it.
3. **Per operation, sequentially** (NOT as one combined batch):
   a. `_resolve_stable_to_span(op, tree)` — resolve stable_id -> span node_id
      against the **current** tree. Miss -> `StaleNodeIdError` -> STALE_NODE_ID.
   b. `_normalized_cst_modify_operation(op)` — normalize op keys.
   c. `build_tree_operations(tree, [normalized_op])` -> built ops.
   d. `tree = modify_tree(tree.tree_id, built)` — **returns a NEW tree with a
      NEW tree_id**. The tree is fully rebuilt every operation.
   e. `session.tree_id = tree.tree_id` — update the live handle.
   f. `write_sidecar_atomic(abs_path, tree)` — persist sidecar.
4. **Any failure** -> `_rollback_and_fail`: `rollback_tree_to_code(tree_id, code,
   index_metadata_for_code=metadata_snapshot)`, restore `session.tree_id`,
   re-write sidecar from the restored tree.

### 2.2 stable_id resolution (`_resolve_stable_to_span`)

For fields `node_id`, `parent_node_id`, `target_node_id`:
- value contains `:` -> already a span node_id, pass through `_resolve_node_id`.
- value == ROOT_NODE_ID_SENTINEL -> pass through unchanged.
- otherwise -> it's a stable_id -> `tree.find_by_stable_id(raw)`:
  - found -> take `meta.node_id`, then `_resolve_node_id(tree, node_id)`.
  - not found -> `StaleNodeIdError(field, stable_id)`.

### 2.3 When is the tree rebuilt? (sidecar)

**Every single operation.** `modify_tree` produces a brand-new tree object +
new tree_id. After rebuild, `_build_tree_index` re-assigns node_id by position;
stable_id is carried over by matching exact position keys for unchanged nodes
(node_id is preserved for unchanged nodes via exact position key). Changed
nodes get fresh node_id but keep their original stable_id via the marker layer.

**Consequence the API must surface:** after each sidecar edit, all positional
node_ids may shift, so the client MUST call preview again to refresh node_refs
before the next op. This is exactly the STALE_NODE_ID hint text. Because each op
rebuilds, a multi-op batch resolves each op against the freshly-rebuilt tree
from the previous op.

### 2.4 NESTED_BATCH_FORBIDDEN

`validate_sidecar_nested_batch(operations, tree_id)`:
- sidecar only. Checks **every pair** of node_ids in the batch.
- `_is_ancestor(tree, ancestor_sid, descendant_sid)` walks the parent chain via
  `find_by_stable_id`.
- if any node in the batch is an ancestor of another node in the same batch ->
  reject the **entire** batch with NESTED_BATCH_FORBIDDEN (before applying anything).
- Rationale: editing an ancestor invalidates the descendant's resolution mid-batch.

### 2.5 insert semantics (`_normalized_cst_modify_operation`, action=insert)

Mutually exclusive addressing — exactly one of:
- `target_node_id` + `position` in {before, after} -> sibling-relative insert.
- `parent_node_id` + `position` in {first, last} or `{after: N}` -> child insert.
Providing both target_node_id and parent_node_id -> ValueError.
`position: first|last` without parent_node_id -> error.
`position: before|after` without target_node_id -> error.

---

## 3. tree-temp (.json/.yaml) — in-place mutate, reindex-per-op model

Reference: `ported/universal_file_edit/tree_temp_edit_nodes.py`.
This is the **primary format for this project** (plans are YAML).

### 3.1 Entry point

`apply_single_tree_temp_mutation(roots, handler_id, mop)`:
```
idx_map = _stable_index(roots)        # rebuilt fresh on EVERY call
_apply_one_mutation(roots, handler_id, mop, idx_map)
```
Unlike sidecar, the tree (roots) is **mutated in place** — no new tree object.
But the **stable index is rebuilt before every mutation** (`_stable_index`).

### 3.2 _stable_index — the positional index

`_stable_index(roots)` walks all roots via `walk(node, holder, idx)` and builds
`Dict[stable_id, Tuple[holder_list, index]]` — i.e. for each stable_id, which
parent list contains it and at what index. This is how delete/replace locate
the live slot after prior mutations shifted indices.

### 3.3 _apply_one_mutation — the three actions

**replace:**
- requires `value`.
- `target = _resolve_target_node(roots, mop, idx_map)` (by stable_id or json_pointer).
- `new_node = _value_to_single_node(handler_id, value)`.
- `_merge_payload_keep_identity(target, new_node)` — **mutates target's payload
  in place, KEEPS target's stable_id**. The node identity survives a replace.

**delete:**
- stable target present -> `idx_map[sid]` -> `(holder, idx)` -> `del holder[idx]`.
- else json_pointer -> `_parent_holder_and_last_seg` -> `del holder[idx]`.

**insert:** delegates to `_apply_insert` (see 3.4).

### 3.4 insert positioning (`_apply_insert`, `_resolve_insert_parent`)

Parent resolution:
- `parent_json_pointer` (RFC6901). Special sentinel `/-` suffix (e.g.
  `/concepts/-`) -> array parent, append mode, no explicit index needed.
- `parent_node_id` -> opaque stable UUID of parent.

Positioning **within arrays**:
- `before_node_id` / `after_node_id` -> sibling-relative by stable UUID.
- `index` -> explicit 0-based int.
- `position: 'last'` or nothing -> append.

Positioning **within objects**:
- `before_key` / `after_key` -> sibling-relative by key name.
- `position: 'last'` or nothing -> append to end.

NOTE (learned in prior session): `after_node_id`/`before_node_id` require an
**opaque UUID**, NOT a json_pointer. Passing a pointer -> sibling stable_id not
found. For neighbour insert, append via `/-` is simpler; dict order is not
critical for the MRS.

### 3.5 _regenerate_stable_ids

`_regenerate_stable_ids(node)` (line 175) — recursively assigns FRESH stable_ids
to a subtree. Used for **inserted** content: a newly-inserted node and its
descendants get brand-new UUIDs (they didn't exist before, so they can't carry
an old identity). Existing nodes are untouched -> their stable_ids persist.

### 3.6 When is the index rebuilt? (tree-temp)

`_stable_index` is rebuilt at the **start of every single mutation**
(`apply_single_tree_temp_mutation`). The roots themselves are mutated in place
(never replaced wholesale). So:
- replace: keeps identity (merge payload).
- delete: removes slot, other stable_ids unaffected, index rebuilt next op.
- insert: new nodes get fresh stable_ids via `_regenerate_stable_ids`, index
  rebuilt next op.

This means tree-temp node_refs (the JSON Pointers) DO shift after structural
edits (insert/delete change array indices and pointer paths), but the underlying
**stable_id of an untouched node never changes**. The pointer is positional; the
stable_id is durable. Preview returns pointers for human/LLM addressing, but the
engine can also address by stable_id internally.

### 3.7 scalar value gotchas

- `_json_scalar_tree_node(value)`: bare integer strings like `"7"` are
  mis-parsed by `parse_json_source` (exponent grammar). So int/float payloads
  are built directly as scalar TreeNodes, not round-tripped through tolerant JSON.
- `_value_to_single_node` vs `_value_to_tree_roots`: YAML top-level sequences
  parse to N scalar roots; replace/insert need exactly ONE node, so
  `_value_to_single_node` wraps multi-root YAML in a single array TreeNode
  (consistent with JSON behaviour).

---

## 4. text (.md/.txt) — line-based, no identity

Reference: `edit_command._apply_text`, `text_draft_apply.py`.

- node_ref = 0-based line index; edit op uses 1-based inclusive `start_line`/`end_line`
  (start_line = int(node_ref) + 1).
- operations sorted **bottom-up** (descending start_line) before applying, so that
  edits above don't shift the line numbers of edits below within one batch.
- no stable_id, no tree — pure line list manipulation.
- append: `position: last`.
- NOTE: the ported text path imported logic from `universal_file_replace_command`
  (NOT in scope) — that replace logic must be re-implemented inline.

---

## 5. preview command — what it returns per group

- **text**: line blocks with 0-based index as node_ref.
- **tree-temp**: node tree; node_ref = RFC6901 json_pointer; `full_text` available
  for scalars; markdown/structural nodes summarised by key_count/key_names.
- **sidecar**: node tree; node_ref = stable UUID; resolve by `find_by_stable_id`.
- Universal rule surfaced to client: **after every edit, re-preview to refresh
  node_refs** — because positional refs (line index, json_pointer, span node_id)
  shift after structural mutations. Only stable_id is durable.

---

## 6. write / commit (two-phase)

- tree-temp: explicit `write_mode` — `preview` returns unified diff vs disk
  (no side effects); `commit` does backup -> atomic source write (+ optional
  sidecar) -> git hook. Restore-on-failure via BackupManager.
- sidecar/text: two-phase PID lockfile protocol (write_mode ignored).
  First call: generate code, diff, write PID lockfile. Second call (lockfile
  matches current pid+session): backup -> atomic temp-file replace -> delete lockfile.
- atomic write pattern: write to NamedTemporaryFile in same dir, then `os.replace`.
- backup before mutate, `bm.restore_file(rel)` on any failure.

---

## 7. Re-implementation checklist (mapping to this project's concepts)

What to reproduce, restated in ai_editor (Session/Buffer/Formatter) terms:

1. **Node identity model**: every structured node has (stable_id: durable UUID,
   node_ref: positional address). Formatter owns the mapping. — covers section 1.
2. **Resolve-before-mutate**: stable_id -> current positional ref, against the
   live tree, per op. Miss -> STALE_NODE_ID with re-preview hint. — 2.2, 3.2.
3. **tree-temp Formatter**: in-place mutate roots; rebuild stable index per op;
   replace keeps identity; insert regenerates stable_ids for new subtree;
   delete by (holder, index). — section 3.
4. **sidecar Formatter** (deferred / Python): full rebuild per op via modify_tree;
   stable_id carried by position-key match; NESTED_BATCH_FORBIDDEN precheck. — section 2.
5. **text Formatter**: bottom-up line ops; inline replace logic (no external cmd). — section 4.
6. **preview contract**: per-group node_ref; always re-preview after edit. — section 5.
7. **write contract**: tree-temp preview/commit diff; sidecar/text two-phase;
   atomic temp+replace; backup+restore. — section 6.
8. **scalar handling** for tree-temp: int/float built directly; YAML multi-root
   wrapped to single node. — 3.7.

---

## 8. Open items still to read (next deep-dive)

- `cst_tree/tree_builder.py` `_build_tree_index` exact position-key algorithm
  (how node_id is derived from span; how unchanged nodes keep node_id).
- `cst_tree/node_id_markers.py` marker block format (how stable_id persists in .py).
- `mutable_cst/*` — a newer/cleaner mutate layer (build.py aligns node_ids to
  existing index; edits.py: replace/delete by node_id, insert by parent+position).
  Relevant only to sidecar/Python (G-003). Compare before choosing the model to
  reproduce for the Python Formatter.
- tree-temp `parse_json_source` / `parse_yaml_source` / serializers — the
  round-trip-preserving parse/serialize contract (comment/format preservation).
