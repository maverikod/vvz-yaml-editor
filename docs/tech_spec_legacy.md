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
  └─ owns: binding of one file to one formatter, modified flag, lock_session_id
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
  No advisory lock. On `file_close` without `file_send` + `modified=True` + `force=False` → `FILE_HAS_UNSENT_CHANGES`.
  On `force=True` → delete artifacts, no unlock.
- `relative_path!=None` → **remote**: downloaded via `file_open`, or became remote after `file_send`.
  Has advisory lock (`lock_session_id`). On `file_close` without `file_send` + `modified=True` + `force=False` → `FILE_HAS_UNSENT_CHANGES`.
  On `force=True` → `advisory_unlock` + delete artifacts.
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
- **SessionKey** — type alias: `str` (UUID4)
- **SessionDescriptor** — `session_key`, `open_buffers (list[BufferDescriptor])`, `diagnostics`
- **BufferDescriptor** — `buffer_id`, `session_key`, `filename`, `relative_path`, `formatter`, `project_id`, `modified (bool)`, `readonly (bool)`, `buf_file_path`

Rules:
- All subsystems import contracts only from `ai_editor/contracts/`.
- No subsystem edits another subsystem’s owned paths.
- No subsystem patches `.venv`, `venv`, `site-packages`.
- CLI entry point `ai-editor = ai_editor.interfaces.cli:main` is declared here in `pyproject.toml` but implemented in G-009.

---

## Code analysis server connection

All file access goes through the code analysis server API.
`ai_editor` never reads or writes project files directly from disk.

### Config section in `config.json`

```json
{
  "code_analysis_server": {
    "host": "172.18.0.1",
    "port": 15000,
    "protocol": "https",
    "servername": "code-analysis-server",
    "check_hostname": false,
    "ssl": {
      "cert": "mtls_certificates/mtls_certificates/client/code-analysis.crt",
      "key":  "mtls_certificates/mtls_certificates/client/code-analysis.key",
      "ca":   "mtls_certificates/mtls_certificates/ca/ca.crt",
      "crl":  null
    },
    "auth": {
      "use_token": false,
      "token_env": null
    }
  }
}
```

**Варианты аутентификации:**
- **mTLS** (текущий) — клиентский сертификат + CA. `use_token: false`.
- **HTTPS + токен** — `use_token: true`, токен в переменной окружения `token_env`.
  Передаётся в заголовке `X-API-Key: <token>`.

Пароли и токены **никогда** не хранятся в `config.json` — только ссылки на переменные окружения.

### File API — ключевые команды

| Операция | Команда | Обязательные параметры |
|---|---|---|
| Получить файл чанками | `project_file_transfer_download_begin` | `project_id` + `file_path`, `compression` |
| История версий файла | `list_backup_versions` | `project_id`, `file_path` |
| История + файл за раз | `project_file_transfer_download_begin` | + `include_backup_history=true` |
| Загрузить новый контент | `transfer_upload_begin` → PUT chunks → `transfer_upload_complete` → `project_file_transfer_upload_save` | `project_id` + `file_path` + `transfer_id` |
| Восстановить версию | `restore_backup_file` | `project_id`, `file_path`, `backup_uuid?` |
| Список файлов проекта | `list_project_files` | `project_id` |

### Download flow (получить файл)

```
1. project_file_transfer_download_begin(
     project_id  = "<uuid>",
     file_path   = "docs/tech_spec.md",   # project-relative, no wildcards
     compression = "identity",
     include_backup_history = true          # опционально, default true
   )
   → { transfer_id, size_bytes, checksum_value (SHA-256), backup_history[] }

2. GET https://<host>:<port>/api/transfer/downloads/{transfer_id}/chunks
     ?offset=0&limit=1048576
   (те же mTLS/токен-заголовки что и для JSON-RPC)
   → raw bytes чанк

3. Повторять GET со смещением пока offset < size_bytes.
4. Проверить SHA-256 суммарного контента = checksum_value.
```

### Upload flow (сохранить файл)

```
1. transfer_upload_begin(
     filename       = "tech_spec.md",
     size_bytes     = <len(content)>,
     checksum_value = <sha256_hex(content)>,
     compression    = "identity"
   )
   → { transfer_id, chunk_path_template }

2. PUT https://<host>:<port>/api/transfer/uploads/{transfer_id}/chunks
     body = raw bytes
   (повторять по чанкам)

3. transfer_upload_complete(transfer_id)
   → подтверждение контрольной суммы

4. project_file_transfer_upload_save(
     project_id     = "<uuid>",
     file_path      = "docs/tech_spec.md",
     transfer_id    = "<id from step 3>",
     backup         = true,               # default, создаёт backup перед записью
     commit_message = "ai_editor: save docs/tech_spec.md"
   )
   → файл сохранён, backup создан, git commit выполнен
```

### `project_id` в буфере

Каждый буфер хранит `project_id` и `file_path` (relative) — этой пары достаточно
для всех операций с API сервера анализа. `file_id` (UUID из таблицы `files`)
хранится когда известен (возвращается `list_project_files` для проиндексированных файлов),
но не является обязательным — все команды поддерживают режим `project_id + file_path`.

### Сессии переживают перезагрузку

После рестарта `ai_editor` сессии восстанавливаются по директории на диске.
Проверка живости блокировки — **только по наличию непустого `editing_session_key`**:

```
GC / startup_sweep:
  for session_dir in sessions_base_dir:
    key = read ses_settings.json -> session_key
    if check_session_lock_exists(session_key).exists:
      # сессия держит блокировки — это живая или зависшая сессия
      release_all_locks_for_session(db, session_key)
    delete session directory if expired
```

Проверка по `editing_pid` (os.kill) не используется для межпроцессной очистки —
только `check_session_lock_exists` через API сервера анализа.
---



## G-002 — Editor core and buffer registry

Owns: `ai_editor/editor_core/`, `ai_editor/config/`, `ai_editor/writer.py`, `tests/editor_core/`.

### Buffer model

One buffer = one open document. Buffer is bound to a file and a formatter at open time.
Both never change for the lifetime of the buffer.

```
buffer fields:
  buffer_id          UUID4, stable for the lifetime of the buffer
  project_id         UUID4 of the code_analysis project this file belongs to
  file_id            UUID from files table (null if not yet indexed)
  filename           bare filename, e.g. README.yaml
  relative_path      path relative to project root (null for local buffers never sent)
  formatter          formatter name, set at open, never changes
  modified           bool — True if buffer has unsent changes (mutations since last file_send)
  readonly           bool — set at open, never changes
  lock_mode          'full' | 'none'  — 'full' for writable remote, 'none' for readonly or local
  lock_session_id    str | null — CA server lock id; null for local buffers and readonly
```

`modified` is set to `True` after every mutation.
`modified` is reset to `False` after a successful `file_send`.

**local vs remote:** `relative_path=None` → local (never sent to CA server).
`relative_path != None` → remote (downloaded from CA server, or sent there via `file_send`).
After `file_send`, local buffer gets `relative_path` set and becomes remote.

### AbstractBuffer public contract

```
file_open(session_key, project_id, file_path, formatter=auto,
  open_as_text=False, readonly=False) -> buffer_id
file_create(session_key, filename, content='', formatter=auto) -> buffer_id
file_send(session_key, buffer_id) -> OperationResult
file_close(session_key, buffer_id, force=False) -> OperationResult
reload(session_key, buffer_id) -> OperationResult
get_state(session_key, buffer_id) -> BufferState
get_formatter(session_key, buffer_id) -> AbstractFormatter
validate(session_key, buffer_id) -> ValidationResult
write_all(session_key) -> WriteAllResult
```
### BufferState

`get_state()` returns a `BufferState` — a snapshot of what is currently in the buffer:
```
BufferState:
  buffer_id      str
  formatter      str        — formatter name
  preview        str        — short text preview of the buffer contents (formatter-rendered)
  modified       bool
  readonly       bool
  file_path      str | None
  relative_path  str | None
```

The `preview` is produced by the formatter and gives a human-readable summary of the document.
For CST: declarative skeleton. For YAML: top-level keys. For text: first N lines.

### FormatterRegistry

The formatter registry maps file extensions and formatter names to formatter classes.

```
FormatterRegistry:
  register(formatter_name, extensions, formatter_class)
  get_by_extension(ext) -> formatter_class | None
  get_by_name(name) -> formatter_class | None
  list_formatters() -> list[formatter_name]
```

Rules:
- Each formatter registers itself with its name and supported extensions.
- One extension maps to exactly one formatter (last registered wins).
- `formatter=auto` at open time calls `get_by_extension(ext)`.
- Designed for future lazy loading: formatter class is not instantiated until needed.
- Owned by G-002. Formatters register themselves at import time or at startup.

### Open rules
- On open: acquire CA server advisory lock via `ca_client.download_file(lock_mode='full')`.
  Returns `lock_session_id` stored in buf_meta. If another live session holds the lock → `BUFFER_LOCKED`.
  `readonly=True` buffers use `lock_mode='none'` — no lock acquired, no `lock_session_id`.

### Advisory lock (CA server)

File locking is managed entirely via the CA server API. No direct database access.

**Acquire (on file_open):**
```
ca_client.download_file(project_id, relative_path, lock_mode='full', session_key=session_key)
→ {content_bytes, file_id, lock_session_id}
BUFFER_LOCKED if lock already held by another session.
```

**Release on file_send (save):**
```
ca_client.upload_file(..., unlock_after_write=True)  → releases lock automatically
```

**Release on file_close without file_send:**
```
ca_client.advisory_unlock(lock_session_id, project_id, relative_path)
Local buffers (relative_path=None): no unlock call — no lock was acquired.
```

**Release on startup_sweep (recovery):**
```
ca_client.advisory_unlock(lock_session_id, project_id, relative_path,
  allow_foreign_session=True)  # best-effort, ignore errors
```

**Rules:**
- `readonly=True` buffers: no lock, no unlock, close freely.
- `lock_session_id` stored in `ses_settings.json` per buffer for recovery after restart.

`file_send` is the only operation that writes the project file to the CA server.

```
file_send pipeline:
1. formatter.validate_document(document)  → abort on failure
2. raw_content = formatter.render(document)
3. ca_client.upload_file(project_id, relative_path, raw_content.encode(),
   commit_message, unlock_after_write=True)
4. buffer.modified = False
5. If buffer was local (relative_path=None): set relative_path → buffer is now remote.
```

`validate(buffer_id)` calls `formatter.validate_document` without writing. Called explicitly and as the first stage of `file_send`.

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
- `write_result(content, path)` — backup before write + atomic write + read-back verification. Used for **local derived artifacts only** (e.g. CST sidecar). NOT used for project files — those are sent via `ca_client.upload_file`.

Default `AbstractFormatter.write(content, path)` delegates to `write_result`.
Formatters may override `write` to persist additional local artifacts (e.g. CST sidecar).

### Config

Config читается из `config.json` адаптера, секция `ai_editor` и `code_analysis_server`.
Отдельный файл конфига `ai_editor` **не создаёт**.

#### Секция `ai_editor` в `config.json`

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

#### Паттерн: генератор конфига

`AiEditorConfigGenerator` наследует `SimpleConfigGenerator` из адаптера.
Метод `generate()` **сначала вызывает `super().generate(...)`**, затем дописывает
секции `ai_editor` и `code_analysis_server` в итоговый dict и сохраняет файл.

```python
class AiEditorConfigGenerator(SimpleConfigGenerator):
    def generate(self, protocol, out_path="config.json", **kwargs) -> str:
        # 1. Генерируем базовый конфиг адаптера (server, client, registration, ...)
        super().generate(protocol=protocol, out_path=out_path, **kwargs)

        # 2. Дочитываем сгенерированный файл
        import json
        from pathlib import Path
        data = json.loads(Path(out_path).read_text())

        # 3. Добавляем секцию ai_editor
        data["ai_editor"] = {
            "formatter": {
                "small_file_threshold": kwargs.get("small_file_threshold", "1k"),
                "small_file_formatter": kwargs.get("small_file_formatter", "text"),
            },
            "sessions": {
                "base_dir": kwargs.get("sessions_base_dir", ".ai_editor_sessions"),
            },
        }

        # 4. Добавляем секцию code_analysis_server
        data["code_analysis_server"] = {
            "host": kwargs.get("ca_host", "172.18.0.1"),
            "port": kwargs.get("ca_port", 15000),
            "protocol": kwargs.get("ca_protocol", "https"),
            "servername": kwargs.get("ca_servername", "code-analysis-server"),
            "check_hostname": kwargs.get("ca_check_hostname", False),
            "ssl": {
                "cert": kwargs.get("ca_ssl_cert", "mtls_certificates/client/code-analysis.crt"),
                "key":  kwargs.get("ca_ssl_key",  "mtls_certificates/client/code-analysis.key"),
                "ca":   kwargs.get("ca_ssl_ca",   "mtls_certificates/ca/ca.crt"),
                "crl":  kwargs.get("ca_ssl_crl",  None),
            },
            "auth": {
                "use_token": kwargs.get("ca_use_token", False),
                "token_env": kwargs.get("ca_token_env", None),
            },
        }

        # 5. Сохраняем обратно
        Path(out_path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return out_path
```

#### Паттерн: валидатор конфига

`AiEditorConfigValidator` наследует `BaseValidator` из адаптера.
Метод `validate()` **сначала вызывает валидаторы адаптера** (`SimpleConfigValidator`),
затем добавляет проверку секций `ai_editor` и `code_analysis_server`.

```python
class AiEditorConfigValidator(BaseValidator):
    def __init__(self, config_path=None):
        super().__init__(config_path)
        # Переиспользуем все секционные валидаторы адаптера
        from mcp_proxy_adapter.core.config.simple_config_validator import SimpleConfigValidator
        self._adapter_validator = SimpleConfigValidator(config_path)
        from mcp_proxy_adapter.core.config.validators.ssl_validator import SSLValidator
        self._ssl_validator = SSLValidator(config_path)

    def validate(self, model) -> list:
        errors = []

        # 1. Сначала — все проверки адаптера (server, client, registration, auth, ...)
        errors.extend(self._adapter_validator.validate(model))

        # 2. Потом — секция ai_editor
        errors.extend(self._validate_ai_editor(model))

        # 3. Потом — секция code_analysis_server
        errors.extend(self._validate_code_analysis_server(model))

        return errors

    def _validate_ai_editor(self, model) -> list:
        errors = []
        cfg = getattr(model, "ai_editor", None)
        if cfg is None:
            return errors  # секция опциональна, defaults используются
        # Проверка small_file_threshold: bare int, k/m suffix, или 0
        try:
            parse_threshold(cfg.formatter.small_file_threshold)
        except ValueError as e:
            errors.append(ValidationError(f"ai_editor.formatter.small_file_threshold: {e}"))
        # Проверка small_file_formatter: должен быть известным именем форматтера
        if cfg.formatter.small_file_formatter not in ("text", "yaml", "cst"):
            errors.append(ValidationError(
                f"ai_editor.formatter.small_file_formatter must be one of: text, yaml, cst"
            ))
    def _validate_code_analysis_server(self, model) -> list:
        errors = []
        cfg = getattr(model, "code_analysis_server", None)
        if cfg is None:
            return errors  # секция опциональна — валидируется только если присутствует

        # protocol
        if cfg.protocol not in ("https", "mtls"):
            errors.append(ValidationError(
                "code_analysis_server.protocol must be one of: https, mtls"
            ))

        # mTLS: ssl-секция обязательна, cert/key/ca обязательны
        if cfg.protocol == "mtls" and cfg.ssl is None:
            errors.append(ValidationError("code_analysis_server.ssl is required for mtls"))

        # Проверка наличия/читаемости/формата SSL-файлов — полностью на совести ssl_validator адаптера.
        # SSLValidator.validate_ssl_files() проверяет существование, права доступа,
        # формат (PEM/DER) для cert, key, ca, crl через _resolve_path() из BaseValidator.
        if cfg.ssl is not None:
            errors.extend(
                self._ssl_validator.validate_ssl_files(cfg.ssl, "code_analysis_server", enabled=True)
            )

        # auth: use_token=True требует непустой token_env
        if getattr(cfg, "auth", None) and cfg.auth.use_token:
            if not cfg.auth.token_env:
                errors.append(ValidationError(
                    "code_analysis_server.auth.token_env must be set when use_token=True"
                ))
        return errors
                errors.append(ValidationError(
                    "code_analysis_server.auth.token_env must be set when use_token=True"
                ))
        return errors
```

#### Паттерн: читалка (`SimpleConfig.load`)

Читалка уже есть в адаптере — `SimpleConfig.load()`. `ai_editor` **не реализует свою**.
Секции `ai_editor` и `code_analysis_server` добавляются в `SimpleConfigModel`
как поля с `default_factory`, по тому же паттерну что `client`, `auth`, `queue_manager`:

```python
# В SimpleConfigModel добавляются поля (через расширение или monkey-patch):
ai_editor: AiEditorConfig = field(default_factory=AiEditorConfig)
code_analysis_server: CodeAnalysisServerConfig = field(default_factory=CodeAnalysisServerConfig)
```

Парсинг в `load()` следует тому же паттерну что для `client` (конвертация `ssl` dict → `SSLConfig`,
обработка отсутствующей секции через `.get()`, отсутствующие ключи используют defaults).

#### Dataclasses новых секций

```python
@dataclass
class AiEditorFormatterConfig:
    small_file_threshold: str = "1k"
    small_file_formatter: str = "text"

@dataclass
class AiEditorSessionsConfig:
    base_dir: str = ".ai_editor_sessions"

@dataclass
class AiEditorConfig:
    formatter: AiEditorFormatterConfig = field(default_factory=AiEditorFormatterConfig)
    sessions: AiEditorSessionsConfig = field(default_factory=AiEditorSessionsConfig)

@dataclass
class CodeAnalysisServerAuthConfig:
    use_token: bool = False
    token_env: Optional[str] = None  # имя env-переменной, не сам токен

@dataclass
class CodeAnalysisServerConfig:
    host: str = "172.18.0.1"
    port: int = 15000
    protocol: str = "https"
    servername: str = "code-analysis-server"
    check_hostname: bool = False
    ssl: Optional[SSLConfig] = None  # SSLConfig из адаптера
    auth: CodeAnalysisServerAuthConfig = field(default_factory=CodeAnalysisServerAuthConfig)
```
Пути SSL-сертификатов резолвятся через `self._resolve_path()` из `BaseValidator` адаптера —
поддерживаются и абсолютные, и относительные пути (относительно директории `config.json`).

#### Правила валидации SSL

`SSLValidator` из пакета адаптера (`mcp_proxy_adapter.core.config.validators.ssl_validator`)
отвечает за **все** SSL-проверки: существование файлов, права на чтение, формат (PEM/DER).
`AiEditorConfigValidator` **не дублирует** эту логику — только вызывает `ssl_validator.validate_ssl_files()`.

Собственные проверки `AiEditorConfigValidator` для `code_analysis_server`:
- `protocol` must be `https` or `mtls`
- `mtls` → `ssl` секция обязательна (остальное — на совести `ssl_validator`)
- `auth.use_token=True` → `auth.token_env` должен быть непустым

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

Search is an interface layer on top of the formatter.
It does not open or write files.
It takes an expression as input and returns formatter blocks — each with a formatter-specific address and a preview.

### AbstractSearch contract

```
find(session_key, buffer_id, query, scope=None) -> list[SearchMatch]
find_one(session_key, buffer_id, query, scope=None) -> SearchMatch | error
list_units(session_key, buffer_id, scope=None) -> list[SearchMatch]
select(session_key, buffer_id, query, policy) -> address | list[address] | error
```

Search calls:
```
formatter.iter_units(document, scope)
formatter.match_unit(unit, query)
formatter.compare_units(unit_a, unit_b, options)
```

### SearchMatch

Every match carries a formatter-specific address and a preview.
The address is opaque to search — interpreted only by the formatter.

```
SearchMatch:
  buffer_id     str
  formatter     str
  address       Any    — formatter-specific address for this block
  preview       str    — human-readable text snippet of the matched block
  unit_kind     str
  metadata      dict
```

Address format by formatter:
```
cst:    stable_id (UUID4)              e.g. 'a3f1c8d2-...'
yaml:   structural path string         e.g. 'commands[name=buf_open]'
text:   'start_line:end_line'          e.g. '42:47'
```

The `preview` is a short text rendering of the matched block.
For CST: declarative signature line. For YAML: rendered node. For text: the matched lines.

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

examples — cst:
  {kind: xpath, value: "//FunctionDef[@name='foo']"}
  {kind: stable_id, value: "a3f1c8d2-..."}
```

`find` returns zero or more matches.
`find_one` returns exactly one or a typed error: `SEARCH_NO_MATCH` | `SEARCH_NOT_UNIQUE`.

---

## G-005 — ForeignFormatter

**Not in scope for the current implementation.** Deferred to a future G-step.

The error codes `FOREIGN_FORMATTER_FAILED`, `FOREIGN_FORMATTER_TIMEOUT`,
`FOREIGN_FORMATTER_CONTRACT_VIOLATION` are reserved in the error model for future use.

---

## G-007 — Refactoring / Project-wide rename

**Not in scope.** Removed from the base implementation.
All in-memory artifacts (job results, rename previews) would be in-memory only with no persistence.


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

### DocstringMeta

Structured docstring stored in `TreeNodeMetadata.docstring`. Migrates with the node via `stable_id`.
Fields: `summary`, `args` (dict), `returns`, `attributes` (dict), `docstring_body` (legacy raw).
Recognises Google-style sections (Args:, Returns:, Attributes:); falls back to `docstring_body`.
Applied to the LibCST node automatically on `save`/`save_as`. Never needs to be embedded by hand in `new_code`.
Serialised to sidecar JSON via `to_dict()` / `from_dict()`.

### CSTFormatter implementation notes (from cst-code analysis)

These notes are binding constraints for the G-006 implementation.

**What to take from cst-code (adapt, not copy):**
- `CSTTree` model: tree_id, module, node_map, metadata_map, parent_map, node_id_aliases, root_node_id, SHA snapshots.
- `TreeNodeMetadata`: frozen dataclass; public API uses only `stable_id`.
- `_build_tree_index`: recursive descent via `MetadataWrapper` + `PositionProvider`. stable_id priority: (1) previous_metadata_map, (2) generate new UUID4. `node_id_aliases` built from `previous_obj_to_id` to survive mutations.
- `modify_tree` with two execution paths:
  - **Sequential path**: one operation at a time, index rebuilt after each.
  - **Mutable batch path** (`mutable_cst` layer): used when replace > 1 OR insert > 1 OR any delete present, AND no REPLACE_RANGE/MOVE. Fine-grained node types (Param, Name) always use sequential path.
- Operation sort before apply: DELETE and REPLACE bottom-to-top by position, INSERT bottom-to-top by parent position. Prevents position shift from invalidating references.
- `_replace_node_header`: replaces only ClassDef/FunctionDef header (name, params/bases), preserves body. Used automatically when REPLACE targets ClassDef/FunctionDef.
- `_find_parent_for_node`: walks parent_id chain to find nearest insertable container (Module, IndentedBlock, ClassDef, FunctionDef). Callers can pass any node_id for INSERT.
- `rollback_tree_to_code`: restores in-memory tree to given source on failed save. Clears SHA snapshots.
- `tree_sidecar.py`: sidecar format `CST_TREE_V1 sha256=<hex>\n<JSON>`. Atomic write via tempfile + `os.replace`. `sidecar_matches_built_tree` verifies path→node_id layout matches after rebuild.
- `skeleton.py` (`build_declarative_overview`): `VISIBLE_KINDS = {module, import, class, function, method}`. Signature prefixed with `[stable_id]`. Body placeholder: `# Implementation hidden; request node by stable_id`. Docstring extracted via `ast.get_docstring`.
- `cst_query/` XPath engine (Lark LALR): descendant (space), child (`>`), `//` recursive, predicates `[attr op value]`, `@`-prefix optional, `:first`, `:last`, `:nth(N)`, `:not(selector)`. Type wildcard `:*` (e.g. `Def:*` → FunctionDef + ClassDef). Operators: `=`, `!=`, `~=`, `^=`, `$=`, `>`, `<`, `>=`, `<=`. Attributes: name, qualname, type, kind, start_line, end_line, children_count.
- `_apply_libcst_codegen_compat()`: patches `SimpleStatementLine._codegen_impl` for libcst ≥ 1.8. Copy as-is.

**What NOT to take from cst-code:**
- Global `_trees` dict and TTL cleanup loop — tree lifecycle is owned by session layer, not tree_builder.
- `node_id_markers.py` (`append_persisted_node_ids`, `render_marker_block`) — storing identifiers in source file is forbidden. Only `strip_persisted_node_ids` and `strip_inline_node_id_lines_from_source` are needed for cleaning legacy files on open.
- `node_stable_id.py` `set_stable_id` / `ensure_stable_id` — embedding `# @node-id:` in `leading_lines` is forbidden. Only `get_stable_id` (for reading legacy) and `strip_inline_node_id_lines_from_source` (for cleanup on load) are taken.
- `commands/` as-is — rewrite under ai_editor command architecture.
- `core/database*`, `core/database_client/` — RPC client to external analysis server, irrelevant.

**Legacy cleanup on open (mandatory):**
When opening any `.py` file, before `cst.parse_module`:
1. `strip_persisted_node_ids(raw)` — removes trailing `# cst-node-ids: begin...end` block.
2. `strip_inline_node_id_lines_from_source(logical)` — removes standalone `# @node-id: <uuid>` lines.
If logical source differs from raw, overwrite the file atomically (strip legacy before indexing).



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
open_buffers   list of buffer descriptors
```

### Buffer lifecycle inside a session

**Step 1 — Session create (if not exists)**

Create session directory. Write `ses_settings.json`. Initialize session git repo at `<session_dir>/git/`.

**Step 2 — file_open (download from CA server)**

```
Input: session_id, project_id, file_path, formatter=auto, readonly=False

1. Determine formatter by file extension (formatter registry).
2. ca_client.download_file(project_id, relative_path,
   lock_mode='full' if not readonly else 'none')
   → {content_bytes, file_id, lock_session_id}
   If lock already held by another session → return BUFFER_LOCKED.
3. formatter.parse(content) → document.
4. write_buf(content, buf_file_path).
5. Git commit on branch buf/<buffer_id>: message "open: <relative_path>".
6. Update ses_settings.json:
   relative_path=relative_path, lock_session_id=lock_session_id,
   modified=False, readonly=readonly.
7. Return buffer_id and formatter.render_skeleton(document).
```

**Step 2a — file_create (new local buffer, no CA server)**

```
Input: session_id, filename, content='', formatter=auto

1. Determine formatter by file extension.
2. formatter.parse(content) → document.
3. write_buf(content, buf_file_path).
4. Git commit: "new: <filename>".
5. Update ses_settings.json:
   relative_path=None, lock_session_id=None,
   modified=False, readonly=False.
6. Return buffer_id and formatter.render_skeleton(document).
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

**Step 8 — file_send (upload to CA server)**

```
1. formatter.validate_document(document)  → abort on failure.
2. raw_content = formatter.render(document).
3. ca_client.upload_file(project_id, relative_path, raw_content.encode(),
   commit_message='ai_editor: save <relative_path>',
   unlock_after_write=True)  → releases advisory lock.
4. buffer.modified = False.
5. If buffer was local (relative_path was None): set relative_path from upload response.
   Buffer is now remote.
```

**Step 9 — file_close**

```
Close rules:
  If buffer.modified=True AND not buffer.readonly AND force=False:
    return FILE_HAS_UNSENT_CHANGES.
  Readonly buffers: close freely regardless of modified.

On close:
1. formatter.delete(buf_file_path) — removes buf file, CST sidecar, any derived files.
2. If relative_path is not None (remote buffer) AND lock_session_id:
     ca_client.advisory_unlock(lock_session_id, project_id, relative_path)  # release lock
3. Delete branch buf/<buffer_id> from session git.
4. Remove buffer from ses_settings.json open_buffers.
   Local buffers (relative_path=None): nothing to unlock, just delete artifacts.
```

**Step 10 — close_session**

```
Without force=True:
  Check all non-readonly buffers:
    If any has modified=True → return SESSION_HAS_UNSENT_FILES.
  If all clean:
    Release advisory locks for all remote buffers (those with lock_session_id).
    Delete session directory (git, buf files, clipboard.json, ses_settings.json).

With force=True:
  Release all advisory locks best-effort (per-buffer project_id and lock_session_id).
  Delete session directory unconditionally.

Readonly buffers are excluded from the modified check.
```

### Undo / redo

```
undo(session_id, buffer_id, steps=1)
  → git checkout HEAD~steps on buf/<buffer_id> branch
  → reload buffer document from that commit
  → formatter.write(content, buf_file_path)  — update buf file
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

For each open buffer where readonly=False and modified=True:
  formatter.validate_document(document)  → on failure: add to failed_buffers, continue
  ca_client.upload_file(project_id, relative_path, content,
    unlock_after_write=False)            → on failure: add to failed_buffers
  on success: add to written_buffers, modified=False
  Buffers with relative_path=None (local, never sent): add to skipped_buffers silently
  Advisory lock is NOT released (unlock_after_write=False).

Result: success=True only if all eligible buffers succeeded.
Session remains open on partial failure.
```

### Session public API

```
connect(readonly=False) -> SessionDescriptor
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

# File
FILE_HAS_UNSENT_CHANGES
SESSION_HAS_UNSENT_FILES

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

GIT_NOT_AVAILABLE
```

---

## G-010 — mcp_proxy_adapter integration

Owns: `ai_editor/hooks_register.py`, `ai_editor/main.py`, `ai_editor/config/`,
`scripts/aiedmgr`, `config.json` (runtime, not committed).

### Principle: the adapter generates the API

`mcp_proxy_adapter` automatically generates JSON-RPC, OpenAPI, and MCP tool surface
from `get_schema()` and `metadata()` of each registered command.
**ai_editor never implements HTTP routes, API handlers, or JSON-RPC manually.**
The adapter owns the entire external interface.

### Command structure (per metadatastd.md)

Every command is three files:
```
ai_editor/commands/<cmd>_command.py   — Command subclass
ai_editor/commands/<cmd>_schema.py    — get_schema() → JSON Schema (machine-readable)
ai_editor/commands/<cmd>_metadata.py  — metadata() → dict (AI/docs-readable)
```

Command class shape:
```python
class BufOpenCommand(Command):  # Command from mcp_proxy_adapter.commands.base
    name = "buf_open"
    version = "1.0.0"
    descr = "Open a file buffer"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> dict:
        return get_buf_open_schema()  # from <cmd>_schema.py

    def validate_params(self, params):
        params = super().validate_params(params)  # super() FIRST
        # then semantic validation
        return params

    async def execute(self, ...) -> dict:
        ...

    @classmethod
    def metadata(cls) -> dict:
        return get_buf_open_metadata(cls)  # from <cmd>_metadata.py
```

Rules:
- `get_schema()` and `metadata()` are SEPARATE layers. Never mix them.
- Destructive commands must include `dry_run` parameter.
- `validate_params()` always calls `super()` first.
- Required `metadata()` fields: name, version, description, category, author, email,
  detailed_description, parameters, return_value, usage_examples, error_cases, best_practices.

### Command registration (hooks)

```python
# ai_editor/hooks_register.py
from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook

def _register(registry):
    from ai_editor.commands.buf_open_command import BufOpenCommand
    from ai_editor.commands.buf_close_command import BufCloseCommand
    from ai_editor.commands.buf_save_command import BufSaveCommand
    # ... all commands
    registry.register(BufOpenCommand, "custom")
    registry.register(BufCloseCommand, "custom")
    registry.register(BufSaveCommand, "custom")

register_custom_commands_hook(_register)

def register_ai_editor_commands(registry):
    _register(registry)
```

For commands that use the job queue (`use_queue=True`), also register with:
```python
from mcp_proxy_adapter.commands.hooks import register_auto_import_module
register_auto_import_module("ai_editor.commands.some_queue_command")
```

### Config

Config is JSON only. `ai_editor` does NOT write its own `config.json`.
It uses a dedicated section inside the adapter's `config.json`:

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

The `registration` section enables automatic registration on the proxy at startup.
The adapter reads config via `SimpleConfig(config_path).load()` — **ai_editor does not implement its own config reader**.

### Config components owned by ai_editor

**Reader** — not implemented. Uses `SimpleConfig.load()` from the adapter directly.

**`AiEditorConfig`** (`ai_editor/config/config_section.py`)
— dataclass for the `ai_editor` section. Provides `from_dict()` and `from_config_json()` class methods.

**`AiEditorConfigValidator`** (`ai_editor/config/config_validator.py`)
— inherits `BaseValidator` from adapter.
— validates the `ai_editor` section (threshold syntax, allowed formatter names, etc.).
— called inside the adapter's own config validation pipeline.

**`AiEditorConfigGenerator`** (`ai_editor/config/config_generator.py`)
— inherits `SimpleConfigGenerator` from adapter.
— adds generation of the `ai_editor` section.
— calls the adapter's generator internally, then extends the output.

### Startup sequence (main.py)

```python
# ai_editor/main.py
from mcp_proxy_adapter.api.app import create_app
from mcp_proxy_adapter.core.server_adapter import UnifiedServerRunner
from mcp_proxy_adapter.core.config.simple_config import SimpleConfig

# 1. Load config via adapter reader
model = SimpleConfig(config_path).load()

# 2. Validate ai_editor section
from ai_editor.config.config_validator import AiEditorConfigValidator
errors = AiEditorConfigValidator().validate(model.raw)
# abort if errors

# 3. Load ai_editor config section
from ai_editor.config.config_section import AiEditorConfig
ai_cfg = AiEditorConfig.from_config_json(config_path)

# 4. Create ASGI app
app = create_app(app_config=model.raw, config_path=config_path)

# 5. Register commands
from ai_editor.hooks_register import register_ai_editor_commands
from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook
register_custom_commands_hook(register_ai_editor_commands)

# 6. Run with hypercorn via UnifiedServerRunner
runner = UnifiedServerRunner()  # default engine: hypercorn
runner.run_server(app, server_config)
```

### Proxy auto-registration

Registration is controlled by the `registration` section in `config.json`.
When `registration.auto_on_startup = true`:
- At startup the adapter calls `RegistrationManager.register_with_proxy()` automatically.
- Heartbeat is started at `registration.heartbeat_interval` seconds.
- On shutdown (`auto_on_shutdown = true`) the server unregisters from the proxy.
- `instance_uuid` (UUID4) uniquely identifies this server instance on the proxy.
- Retry logic: up to 5 attempts with exponential backoff before giving up.
- If proxy is unreachable — server still starts; API is available without proxy.

The embedding-service (running as `embedding-service` on the proxy) demonstrates
the working pattern with `auto_on_startup: true`, `auto_on_shutdown: true`,
and `instance_uuid` set in `config.json`.

### Service manager (aiedmgr)

Owns: `scripts/aiedmgr`.

Installed as a console script in the virtualenv:
```
aiedmgr start    — start ai_editor server in background, write PID file
aiedmgr stop     — stop by PID, wait for clean shutdown
aiedmgr status   — show running/stopped state, PID, port
aiedmgr restart  — stop + start
```

Requirements:
- Runs inside the project `.venv` (script uses the venv Python).
- PID file location configurable, default: `<project_root>/ai_editor.pid`.
- Log file: `logs/ai_editor.log`.
- Reads `config.json` path from `--config` argument or env `AI_EDITOR_CONFIG`.
- On `start`: validates config before launching (calls `AiEditorConfigValidator`).
- On `stop`: sends SIGTERM, waits for graceful shutdown (timeout 30s), then SIGKILL.
- `status` checks PID liveness via `os.kill(pid, 0)`.

---

## Dependencies

### Runtime dependencies (`pyproject.toml`)

```toml
dependencies = [
  # --- Adapter (framework, config, SSL validation, command base) ---
  "mcp-proxy-adapter",          # SimpleConfig, SimpleConfigGenerator, BaseValidator,
                                 # SSLValidator, Command, register_custom_commands_hook,
                                 # UnifiedServerRunner, create_app

  # --- YAML formatter (G-003) ---
  "ruamel.yaml>=0.18.0",        # round-trip parse/render, preserves comments and order
  "jsonpath-ng>=1.6.0",         # path filters: commands[name=buf_diff]
  "jsonschema>=4.0.0",          # plan_task_v1 + JSON schema validation

  # --- JSON formatter (G-003) ---
  # parse/render: stdlib json. schema: jsonschema already listed above.

  # --- Text formatter (G-003) ---
  # document model: list[str]. No extra deps, stdlib only.

  # --- CST formatter / .py files (G-006) ---
  "libcst>=1.1.0",              # Python CST parse/render/mutate
                                 # _apply_libcst_codegen_compat patched for libcst>=1.8
  "lark>=1.1.0",                # XPath LALR query engine for CSTFormatter (G-003/T-011)
]
```

### Formatter dependency summary

| Formatter | Extra deps | Notes |
|---|---|---|
| **text** | none | `list[str]`, stdlib only |
| **json** | `jsonschema` | parse/render = stdlib `json` |
| **yaml** | `ruamel.yaml`, `jsonpath-ng`, `jsonschema` | round-trip, path filters, schema |
| **cst** | `libcst`, `lark` | Python CST + XPath query engine, adapted from `cst-code/` |

### What comes from `mcp_proxy_adapter` (installed package)

| Import | Used for |
|---|---|
| `...core.config.simple_config` | `SimpleConfig`, `SimpleConfigModel`, `SSLConfig` |
| `...core.config.simple_config_generator` | `SimpleConfigGenerator` (base for generator) |
| `...core.config.simple_config_validator` | `SimpleConfigValidator` (called first in validator) |
| `...core.config.validators.base_validator` | `BaseValidator`, `ValidationError`, `_resolve_path()` |
| `...core.config.validators.ssl_validator` | `SSLValidator.validate_ssl_files()` -- all SSL checks |
| `...commands.base` | `Command` base class |
| `...commands.hooks` | `register_custom_commands_hook`, `register_auto_import_module` |
| `...api.app` | `create_app` |
| `...core.server_adapter` | `UnifiedServerRunner` |

### What comes from `cst-code/` (adapt, NOT import directly)

`cst-code/` is a source snapshot in the `ai_editor` repo.
Adapted into `ai_editor/formatters/cst/` -- not imported as a package.

| Module | Take | Skip |
|---|---|---|
| `cst_tree/tree_builder.py` | `_build_tree_index`, stable_id, `node_id_aliases` | -- |
| `cst_tree/tree_modifier.py` | sequential + batch paths, operation sort | -- |
| `cst_tree/tree_modifier_ops*.py` | INSERT/DELETE/REPLACE, `_replace_node_header` | -- |
| `cst_tree/tree_sidecar.py` | `CST_TREE_V1` format, atomic write, checksum | -- |
| `cst_tree/skeleton.py` | `build_declarative_overview`, VISIBLE_KINDS | -- |
| `cst_tree/models.py` | `CSTTree`, `TreeNodeMetadata` dataclasses | -- |
| `cst_tree/node_stable_id.py` | `get_stable_id`, `strip_inline_node_id_lines_from_source` | `set_stable_id`, `ensure_stable_id` |
| `cst_tree/node_id_markers.py` | `strip_persisted_node_ids` | `append_persisted_node_ids`, `render_marker_block` |
| `cst_tree/tree_range_finder.py` | range lookup | -- |
| `cst_query/` | XPath Lark LALR engine (parser, executor, index_builder) | -- |
| `core/mutable_cst/` | batch mutation layer | -- |
| `core/database*/` | -- | entire block (RPC to server, not needed) |
| `commands/` | -- | entire block (rewrite under ai_editor arch) |