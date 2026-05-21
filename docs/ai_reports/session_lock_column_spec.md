# Technical Specification: session_key column in files table + session existence API

**Project:** code_analysis (server)  
**Requested by:** ai_editor project  
**Author:** Claude / Vasiliy Zdanovskiy  
**Status:** draft

---

## Background

The `files` table already has an `editing_pid INTEGER DEFAULT NULL` column used as a
write-lock by the CST editor, `universal_file_replace`, and background workers.
Locking is currently PID-based: `editing_lock_holder_is_alive(pid)` uses `os.kill(pid, 0)`
to check liveness.

The `ai_editor` service opens files in editor sessions (UUID4 `session_key`). A session
has a lifecycle independent of any single OS process — it can survive process restarts
if the session directory is still on disk. The current lock has two problems:

1. When an `ai_editor` session is **closed or expired**, there is no way for the
   `code_analysis` GC/worker to know whether the lock is stale without calling back
   into `ai_editor`. The only signal it has now is PID liveness, which is process-level,
   not session-level.
2. When `ai_editor` opens the same file in two different sessions (which is forbidden),
   the error message only reports a PID, not a session identity — making diagnosis hard.

---

## What needs to be done

### 1. Add `editing_session_key VARCHAR(36) DEFAULT NULL` column to `files` table

This column stores the UUID4 session key of the `ai_editor` session that holds the
write lock on a file. It is set atomically together with `editing_pid` on open and
cleared together on close.

The column must be nullable. When no lock is held, both `editing_pid` and
`editing_session_key` are NULL. When a lock is held, both are non-NULL.

**Schema change:**
```sql
ALTER TABLE files ADD COLUMN editing_session_key VARCHAR(36) DEFAULT NULL;
```

**Index** (partial, for GC queries):
```sql
CREATE INDEX IF NOT EXISTS idx_files_editing_session_key
    ON files(editing_session_key)
    WHERE editing_session_key IS NOT NULL;
```

### 2. Add migration in all three migration paths

Migration must be idempotent — safe to run on an existing DB or a fresh one.

#### a) `code_analysis/core/database/schema_creation_create.py` — `run_create_schema()`

Add `editing_session_key` to the `files` table DDL immediately after `editing_pid`:

```python
# In the CREATE TABLE IF NOT EXISTS files (...) statement:
"editing_pid INTEGER DEFAULT NULL,"
"editing_session_key VARCHAR(36) DEFAULT NULL,"  # <-- add this line
```

#### b) `code_analysis/core/database/schema_creation_migrate.py` — `run_migrate_schema()`

At the end of the function, after the existing `editing_pid` block, add:

```python
# File-level edit lock: session identity (ai_editor session_key).
if "editing_session_key" not in files_columns_editing:
    try:
        logger.info("Migrating files table: adding editing_session_key column")
        db._execute(
            "ALTER TABLE files ADD COLUMN editing_session_key VARCHAR(36) DEFAULT NULL"
        )
        db._commit()
    except Exception as e:
        logger.warning(f"Could not add editing_session_key column to files: {e}")
# Partial index for GC sweeps.
try:
    db._execute(
        "CREATE INDEX IF NOT EXISTS idx_files_editing_session_key "
        "ON files(editing_session_key) WHERE editing_session_key IS NOT NULL"
    )
    db._commit()
except Exception as e:
    logger.debug(f"idx_files_editing_session_key index: {e}")
```

#### c) `code_analysis/core/database_driver_pkg/drivers/postgres_migrations.py` — `ensure_postgres_schema()`

Immediately after the existing `editing_pid` block, add:

```python
_ensure_missing_column(
    conn,
    table_name="files",
    column_name="editing_session_key",
    add_sql="ALTER TABLE files ADD COLUMN editing_session_key VARCHAR(36) DEFAULT NULL",
)
# Partial index.
try:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_editing_session_key "
            "ON files(editing_session_key) "
            "WHERE editing_session_key IS NOT NULL"
        )
    conn.commit()
except Exception as exc:
    logger.debug("idx_files_editing_session_key index skipped: %s", exc)
    try:
        conn.rollback()
    except Exception:
        pass
```

#### d) `code_analysis/core/database_driver_pkg/drivers/sqlite_migrations.py` — `ensure_files_table_migrations()`

After the `editing_pid` block inside `ensure_files_table_migrations()`:

```python
if "editing_session_key" not in columns:
    logger.info("Migrating files table: adding editing_session_key column (driver)")
    conn.execute(
        "ALTER TABLE files ADD COLUMN editing_session_key VARCHAR(36) DEFAULT NULL"
    )
    conn.commit()
try:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_files_editing_session_key "
        "ON files(editing_session_key) WHERE editing_session_key IS NOT NULL"
    )
    conn.commit()
except Exception as e:
    logger.debug("idx_files_editing_session_key: %s", e)
```

### 3. Update `code_analysis/core/database/schema_definition_tables_core.py`

Add `editing_session_key` to the `files` columns list (after `editing_pid`):

```python
{
    "name": "editing_session_key",
    "type": "TEXT",   # VARCHAR(36) maps to TEXT in the definition layer
    "not_null": False,
},
```

### 4. Update `file_edit_lock.py` to write/clear `editing_session_key`

File: `code_analysis/core/database/file_edit_lock.py`

All three public functions must be updated.

#### 4a. `try_acquire_file_edit_lock(database, file_id, *, session_key=None, transaction_id=None)`

Add `session_key: Optional[str] = None` parameter.

In the acquire UPDATE, include `editing_session_key`:

```python
sql = (
    "UPDATE files SET editing_pid = ?, editing_session_key = ? "
    "WHERE id = ? AND (editing_pid IS NULL OR editing_pid = ?)"
)
result = _execute_with_optional_tid(
    database, sql, (pid, session_key, file_id, pid),
    transaction_id=transaction_id,
)
```

In the stale lock clear UPDATE, also clear `editing_session_key`:

```python
_execute_with_optional_tid(
    database,
    "UPDATE files SET editing_pid = NULL, editing_session_key = NULL "
    "WHERE id = ? AND editing_pid = ?",
    (file_id, hid),
    transaction_id=transaction_id,
)
```

Acquire re-entrant check: same PID **and** same session_key (if provided) to prevent
a process from re-acquiring a lock that belongs to a different session:

```python
if hid is not None and hid == pid:
    # re-entrant: same PID — check session_key if provided
    if session_key is not None:
        held_sk = _select_scalar_editing_session_key(database, file_id,
                                                      transaction_id=transaction_id)
        if held_sk is not None and held_sk != session_key:
            return False  # different session holds the lock via same PID
    return True  # already held by this process+session
```

Add a helper to read `editing_session_key`:

```python
def _select_scalar_editing_session_key(
    database: Any,
    file_id: Any,
    *,
    transaction_id: Optional[str] = None,
) -> Optional[str]:
    """Read editing_session_key for a file row."""
    if hasattr(database, "execute"):
        result = _execute_with_optional_tid(
            database,
            "SELECT editing_session_key FROM files WHERE id = ?",
            (file_id,),
            transaction_id=transaction_id,
        )
        if isinstance(result, dict):
            rows = result.get("data") or []
            if rows and isinstance(rows[0], dict):
                return rows[0].get("editing_session_key")
    return None
```

#### 4b. `release_file_edit_lock(database, file_id, *, session_key=None, transaction_id=None)`

Add `session_key: Optional[str] = None` parameter.

When `session_key` is provided, release only if both match (prevents accidental
cross-session release):

```python
def release_file_edit_lock(
    database: Any,
    file_id: Any,
    *,
    session_key: Optional[str] = None,
    transaction_id: Optional[str] = None,
) -> None:
    """Clear editing_pid and editing_session_key for the file row."""
    pid = os.getpid()
    if session_key is not None:
        sql = (
            "UPDATE files SET editing_pid = NULL, editing_session_key = NULL "
            "WHERE id = ? AND editing_pid = ? AND editing_session_key = ?"
        )
        _execute_with_optional_tid(
            database, sql, (file_id, pid, session_key),
            transaction_id=transaction_id,
        )
    else:
        sql = (
            "UPDATE files SET editing_pid = NULL, editing_session_key = NULL "
            "WHERE id = ? AND editing_pid = ?"
        )
        _execute_with_optional_tid(
            database, sql, (file_id, pid),
            transaction_id=transaction_id,
        )
```

#### 4c. New public function: `release_all_locks_for_session(database, session_key)`

Called by `ai_editor` session layer (and by the GC) to release all locks held by a
given session in one operation. No PID check — session close is authoritative.

```python
def release_all_locks_for_session(
    database: Any,
    session_key: str,
    *,
    transaction_id: Optional[str] = None,
) -> int:
    """
    Release all file edit locks held by the given session_key.

    Used by the session layer on disconnect/expiry and by the GC cleanup sweep.
    Returns the number of rows updated.

    Args:
        database: Database driver instance.
        session_key: UUID4 session key to release locks for.

    Returns:
        Number of file rows where locks were cleared.
    """
    sql = (
        "UPDATE files SET editing_pid = NULL, editing_session_key = NULL "
        "WHERE editing_session_key = ?"
    )
    result = _execute_with_optional_tid(
        database, sql, (session_key,),
        transaction_id=transaction_id,
    )
    return _dml_affected_rows(result)
```

---

## 5. New API command: `check_session_lock_exists`

The `ai_editor` GC (startup sweep and session close) needs to ask the code_analysis
server: "Does session `X` still hold any file locks?" This lets the GC safely determine
whether it should release locks for an expired session.

This command should be added to the existing command infrastructure of `code_analysis`.

### Command: `check_session_lock_exists`

**Purpose:** Return whether any file in the database has `editing_session_key = <session_key>`.

**Input:**
```json
{
  "session_key": "<uuid4>"  // required
}
```

**Output:**
```json
{
  "success": true,
  "session_key": "<uuid4>",
  "locked_files_count": 3,       // number of files locked by this session
  "exists": true,                 // true if count > 0
  "locked_file_paths": [          // list of locked file paths (max 50 for diagnostics)
    "/home/.../foo.py",
    "/home/.../bar.py"
  ]
}
```

**Implementation:**

```python
def check_session_lock_exists(database, session_key: str) -> dict:
    """
    Return locked file count for a given session_key.
    Used by ai_editor GC to check for stale session locks.
    """
    # Count query
    count_result = database.execute(
        "SELECT COUNT(*) as cnt FROM files WHERE editing_session_key = ?",
        (session_key,)
    )
    count = 0
    rows = (count_result or {}).get("data") or []
    if rows and isinstance(rows[0], dict):
        count = int(rows[0].get("cnt", 0) or 0)

    # Sample paths for diagnostics
    paths_result = database.execute(
        "SELECT path FROM files WHERE editing_session_key = ? LIMIT 50",
        (session_key,)
    )
    paths_rows = (paths_result or {}).get("data") or []
    paths = [r["path"] for r in paths_rows if isinstance(r, dict) and "path" in r]

    return {
        "success": True,
        "session_key": session_key,
        "locked_files_count": count,
        "exists": count > 0,
        "locked_file_paths": paths,
    }
```

**Registered as MCP command** following the same pattern as other commands
(`_command.py` / `_schema.py` / `_metadata.py`). Command name: `check_session_lock_exists`.

---

## 6. GC integration (context for `ai_editor` developers)

This section describes how `ai_editor` uses the new API. Code_analysis server does
not implement this — it only provides the primitives above.

### Startup sweep

When `ai_editor` starts, it scans `sessions_base_dir` for session directories.
For each expired or missing session:

1. Call `release_all_locks_for_session(db, session_key)` — clears all file locks
   held by that session in one query.
2. Delete the session directory.

### Session disconnect / close

On explicit `disconnect` or `close_session`:

1. Call `release_all_locks_for_session(db, session_key)` before deleting session dir.

### `check_session_lock_exists` usage

The command is called by `ai_editor` GC to verify state before release, and can also
be used for diagnostic tooling:

```
GC detects stale session directory
  ↓
call check_session_lock_exists(session_key)
  ↓
if exists=true → call release_all_locks_for_session(session_key)
  ↓
delete session directory
```

---

## 7. Worker behaviour (existing workers, no changes needed)

The existing `file_watcher`, `indexer`, and `vectorizer` already check
`editing_lock_holder_is_alive(row.editing_pid)` and skip locked files. This behaviour
is unchanged. The new `editing_session_key` column is additive.

If a worker encounters a file where `editing_pid` is NULL but `editing_session_key`
is NOT NULL (inconsistent state), it should treat it as unlocked (PID is authoritative
for liveness; session_key without PID means lock was partially released).

---

## 8. Files to change (summary)

| File | Change |
|------|--------|
| `code_analysis/core/database/schema_creation_create.py` | Add `editing_session_key` to `files` DDL |
| `code_analysis/core/database/schema_creation_migrate.py` | Add migration + index for `editing_session_key` |
| `code_analysis/core/database_driver_pkg/drivers/postgres_migrations.py` | Add `_ensure_missing_column` for `editing_session_key` + index |
| `code_analysis/core/database_driver_pkg/drivers/sqlite_migrations.py` | Add migration for `editing_session_key` + index |
| `code_analysis/core/database/schema_definition_tables_core.py` | Add column to `files` definition |
| `code_analysis/core/database/file_edit_lock.py` | Add `session_key` param to `try_acquire` / `release`; add `release_all_locks_for_session`; add `_select_scalar_editing_session_key` |
| `code_analysis/commands/check_session_lock_exists_command.py` | New command (create) |
| `code_analysis/commands/check_session_lock_exists_schema.py` | New schema (create) |
| `code_analysis/commands/check_session_lock_exists_metadata.py` | New metadata (create) |
| `code_analysis/hooks_register.py` (or equivalent) | Register new command |

---

## 9. Backwards compatibility

- All changes are **additive** — new nullable column, new function parameters are
  optional with `None` default.
- Existing callers of `try_acquire_file_edit_lock` and `release_file_edit_lock`
  that do not pass `session_key` continue to work unchanged.
- `editing_session_key = NULL` in old rows means "lock is PID-only" — workers skip
  session check and use only PID liveness as before.
- Migration is idempotent — safe to deploy on a running DB without downtime.

---

## 10. Tests

- `test_try_acquire_sets_session_key` — verify `editing_session_key` is written on acquire.
- `test_release_clears_session_key` — verify both columns are NULL after release.
- `test_release_all_locks_for_session` — verify bulk release clears all rows for session.
- `test_release_does_not_clear_other_session` — verify release_all does not affect
  rows with a different `editing_session_key`.
- `test_check_session_lock_exists_returns_count` — verify API returns correct count.
- `test_check_session_lock_exists_returns_false_when_no_locks` — empty result.
- `test_reentrant_different_session_same_pid` — same PID, different session_key → BUFFER_LOCKED.
- Migration idempotency: run migration twice on same DB, no errors.
