Нужен **структурный YAML-интерфейс**, не диапазоны строк. Диапазоны строк оставить только как аварийный низкоуровневый режим.

## Минимальный хороший интерфейс

```text
yaml_load
yaml_validate
yaml_get
yaml_set
yaml_replace_block
yaml_append
yaml_delete
yaml_move
yaml_write_checked
```

## Главный принцип

Редактировать не строки, а **пути в YAML-дереве**:

```text
commands[0].metadata.best_practices
commands[name=buf_diff].read_model.sees_live_tmpfs_worktree
verification
```

Пример:

```json
{
  "file_path": "docs/plans/.../A-001-buf-diff.md",
  "path": "commands[name=buf_diff].metadata.best_practices",
  "value": [
    "Use buf_diff to review a flushed buf/<uuid> branch before merge/discard.",
    "buf_diff reads git refs only; it does not show unstaged worktree changes."
  ]
}
```

## Нужные команды

### 1. `yaml_load`

Читает YAML и возвращает дерево + краткую сводку.

```json
{
  "file_path": ".../A-001-buf-diff.md"
}
```

Ответ:

```json
{
  "format": "plan_task_v1",
  "node_id": "G-001/T-008/A-001",
  "commands": ["buf_diff", "buf_compact"],
  "top_level_keys": ["format", "node_id", "title", "commands", "verification", "status"],
  "valid_yaml": true
}
```

### 2. `yaml_get`

Достаёт блок по YAML path.

```json
{
  "file_path": ".../A-001-buf-diff.md",
  "path": "commands[name=buf_diff].metadata"
}
```

Это лучше, чем строки: модель получает ровно нужный блок.

### 3. `yaml_set`

Заменяет значение по path.

```json
{
  "file_path": ".../A-001-buf-diff.md",
  "path": "commands[name=buf_diff].read_model.sees_uncommitted_worktree_edits",
  "value": false
}
```

### 4. `yaml_replace_block`

Для замены целого объекта/списка.

```json
{
  "file_path": ".../A-001-buf-diff.md",
  "path": "commands[name=buf_diff].metadata.error_cases",
  "value": {
    "PLAN_NOT_FOUND": {
      "description": "plan_id does not exist or has no .git directory.",
      "message": "Plan not found: {plan_id}",
      "solution": "Call plan_list."
    },
    "INVALID_REF": {
      "description": "from_ref or to_ref is not a valid git ref.",
      "message": "Invalid ref: {ref}",
      "solution": "Use HEAD, HEAD~N, SHA, or flushed buf/<uuid> branch."
    }
  }
}
```

### 5. `yaml_append`

Добавляет элемент в список.

```json
{
  "file_path": ".../A-001-buf-diff.md",
  "path": "verification",
  "value": "buf_diff does not show uncommitted tmpfs worktree edits."
}
```

С опцией защиты от дублей:

```json
{
  "dedupe": true
}
```

### 6. `yaml_delete`

Удаляет поле или элемент списка.

```json
{
  "file_path": ".../A-001-buf-diff.md",
  "path": "commands[name=buf_diff].metadata.best_practices[1]"
}
```

### 7. `yaml_move`

Для перестановки элементов списков.

```json
{
  "file_path": ".../A-001-buf-diff.md",
  "from_path": "commands[name=buf_compact]",
  "to_index": 0
}
```

## Проверка перед записью

Нужна не отдельная рекомендация, а обязательный режим:

```text
read -> parse -> patch in memory -> validate -> render -> validate rendered YAML -> write
```

Команда должна быть атомарной:

### `yaml_write_checked`

```json
{
  "file_path": ".../A-001-buf-diff.md",
  "operations": [
    {
      "op": "set",
      "path": "commands[name=buf_diff].read_model.sees_live_tmpfs_worktree",
      "value": false
    },
    {
      "op": "append",
      "path": "verification",
      "value": "buf_diff does not show uncommitted tmpfs worktree edits.",
      "dedupe": true
    }
  ],
  "validate_schema": "plan_task_v1",
  "dry_run": false
}
```

Перед реальной записью можно вызвать:

```json
{
  "dry_run": true
}
```

Ответ dry-run:

```json
{
  "success": true,
  "would_change": true,
  "changed_paths": [
    "commands[name=buf_diff].read_model.sees_live_tmpfs_worktree",
    "verification"
  ],
  "validation": {
    "yaml_parse": true,
    "schema": true,
    "semantic": true
  },
  "render_preview": {
    "old_hash": "abc",
    "new_hash": "def"
  }
}
```

## Валидация `plan_task_v1`

Минимум проверок:

```text
- YAML парсится.
- format == plan_task_v1.
- node_id соответствует уровню файла.
- kind in [spec, global, tactical, atomic].
- depends_on — список строк.
- commands — список объектов.
- commands[].name уникальны.
- commands[].schema.required ссылается только на существующие properties.
- read_model.sees_live_tmpfs_worktree=false для read-only plan_* disk commands.
- buf_flush semantics не противоречат root README:
  commits to buf/<uuid>, no merge, lock retained.
- verification — непустой список.
- status in [draft, ready_for_review, ready_for_implementation, blocked].
```

## Нужен ли доступ к диапазонам строк?

Да, но только как fallback:

```text
yaml_read_lines
yaml_write_lines_unsafe
```

И название должно прямо пугать: `unsafe`.

Для обычной работы модели нужны не строки, а:

```text
- top-level key
- command by name
- metadata block
- schema block
- verification list
```

## Лучший интерфейс для модели

Самый удобный:

```text
yaml_get_command(file_path, command_name)
yaml_update_command(file_path, command_name, patch)
yaml_get_verification(file_path)
yaml_append_verification(file_path, item, dedupe=true)
yaml_validate_plan_task(file_path)
```

Пример:

```json
{
  "file_path": ".../A-001-buf-diff.md",
  "command_name": "buf_diff",
  "patch": {
    "read_model": {
      "sees_uncommitted_worktree_edits": false
    },
    "metadata": {
      "best_practices": [
        "Use buf_diff to review a flushed buf/<uuid> branch before merge/discard.",
        "buf_diff reads git refs only; it does not show unstaged worktree changes."
      ]
    }
  },
  "dry_run": true
}
```

## Главное требование

Никакая команда записи не должна менять файл, если после patch:

```text
- YAML не парсится;
- schema validation failed;
- semantic validation failed;
- render не детерминирован;
- changed path не совпадает с ожидаемым.
```

И ответ должен возвращать:

```text
backup_uuid
old_hash
new_hash
changed_paths
validation_result
```

Такой интерфейс почти полностью уберёт “качели”.


Рекомендация по библиотекам для pip install:ruamel.yaml (обязательно для сохранения форматирования).jsonpath-ng (для реализации поиска по атрибутам типа [name=...]).jsonschema (для реализации yaml_validate).Нужно ли показать пример кода для сложного фильтра commands[name=...], чтобы он корректно находил индекс элемента в списке?

## Архитектурное уточнение: редактор отдельно от YAML
## Архитектурное уточнение: editor core отдельно от YAML

Нужен не набор YAML-команд, а общий редактор документов. YAML — только первый структурный форматтер. Text — первый простой форматтер.

Старая группа `yaml_*` смешивала три разных слоя:

```text
1. File/buffer lifecycle: open/read/save/save_as/close.
2. Editing: copy/cut/paste/replace/append/delete/move.
3. Search/query: get/find/list/select.
```

Новая архитектура должна явно разделять эти слои:

```text
Editor Core
  ├─ AbstractBuffer / file-backed document lifecycle
  ├─ AbstractFormatter / format-specific editing semantics
  └─ AbstractSearch / universal search over formatter units
```

На первом этапе обязательны только форматтеры:

```text
text
yaml
```

Будущие форматтеры должны добавляться без изменения editor core:

```text
json
markdown
```

## AbstractBuffer: файл и буфер

Файл/буфер — не дело форматтера. Буфер отвечает за связь документа с файлом, состояние изменённости и безопасную запись.

```text
AbstractBuffer
  open(file_path, formatter=auto) -> buffer_id
  new(formatter, display_name=New file) -> buffer_id
  save(buffer_id)
  save_as(buffer_id, file_path, overwrite=false)
  close(buffer_id, save=false | true | error_if_dirty)
  reload(buffer_id)
  get_state(buffer_id)
  get_formatter(buffer_id)
```

Один буфер — один открытый документ. Буфер жёстко связан с файлом либо является новым несохранённым документом.

```text
file-backed buffer:
  buffer_id
  file_path
  formatter
  document
  original_hash
  current_hash
  dirty
  revision
  status

unsaved buffer:
  buffer_id
  file_path: null
  display_name: New file / Untitled-N
  formatter
  document
  original_hash: null
  current_hash
  dirty: true
  revision
  status
```

Правила буфера:

```text
- один file_path не должен иметь два открытых буфера;
- повторный open уже открытого файла возвращает существующий buffer_id;
- formatter хранится в buffer и определяет смысл address, editing и validation;
- dirty показывает, отличается ли текущий document от последнего сохранённого состояния;
- save/save_as — единственные операции, которые пишут файл;
- save/save_as выполняют formatter.validate -> formatter.render -> stale check -> backup -> atomic write;
- copy/cut/paste не читают и не пишут файлы напрямую.
```

## AbstractFormatter: редактирование документа

Форматтер отвечает за смысл адресов, фрагментов и операций редактирования. Он не открывает и не сохраняет файлы.

```text
AbstractFormatter
  parse(raw_content) -> document
  render(document) -> raw_content
  validate(document) -> validation_result
  normalize_address(address) -> normalized_address
  copy_fragment(document, source_address) -> fragment
  cut_fragment(document, source_address) -> document, fragment, changed_addresses
  paste_fragment(document, target_address, fragment, mode) -> document, changed_addresses
  get_unit(document, address) -> unit
  iter_units(document, scope) -> units
  diagnostics(document) -> diagnostics
```

Для YAML:

```text
formatter = yaml
document = YAML tree
address = structural YAML path
unit = YAML node / scalar / mapping / sequence item
```

Для text:

```text
formatter = text
document = array of lines
address = line range / insertion point / whole document
unit = line / line range / text block
```

Editor core не должен знать YAML path details или text line range details. Он передаёт `address` в formatter как opaque value.

## AbstractSearch: поиск отдельно от редактирования

Поиск — отдельный универсальный слой, а не часть YAML formatter и не часть buffer lifecycle.

```text
AbstractSearch
  find(buffer_id, query, scope=null) -> matches
  find_one(buffer_id, query, scope=null) -> match | error
  list_units(buffer_id, scope=null) -> units
  select(buffer_id, query, policy) -> address | addresses | error
```

Search работает через formatter API:

```text
formatter.iter_units(document, scope)
formatter.get_unit(document, address)
formatter.match_unit(unit, query)
formatter.compare_units(left_unit, right_unit, options)
```

Форматтер обязан предоставить универсальное сравнение юнитов:

```text
Formatter.compare_units(unit_a, unit_b, options) -> ComparisonResult
```

Для YAML сравнение может учитывать:

```text
- node type;
- key;
- scalar value;
- normalized scalar value;
- mapping fields;
- list item identity;
- semantic name field, например name=buf_diff.
```

Для text сравнение может учитывать:

```text
- exact line text;
- normalized text;
- substring;
- regex;
- line number;
- line range overlap.
```

## Единая адресация команд copy/cut/paste

Смысл адреса зависит от formatter, но адрес источника и адрес приёмника обязательны в командах.

Нельзя использовать YAML-специфичное имя `path` на уровне editor core. На уровне editor core используется `address`.

> YAML formatter может трактовать address как YAML path. Text formatter может трактовать address как line range или insertion point.

```text
BufferAddress:
  buffer_id
  address
```

Команды:

```text
copy(source: BufferAddress)
cut(source: BufferAddress)
paste(target: BufferAddress, mode, clipboard_item_id=last)
```

Примеры:

```json
{
  "source": {
    "buffer_id": "buf-yaml-1",
    "address": "commands[name=buf_diff].metadata"
  }
}
```

```json
{
  "source": {
    "buffer_id": "buf-text-1",
    "address": {
      "start_line": 10,
      "end_line": 18
    }
  }
}
```

```json
{
  "target": {
    "buffer_id": "buf-yaml-2",
    "address": "verification"
  },
  "mode": "append"
}
```

```json
{
  "target": {
    "buffer_id": "buf-text-2",
    "address": {
      "line": 25,
      "position": "after"
    }
  },
  "mode": "insert"
}
```

Правила:

```text
copy не меняет буфер.
cut вызывает formatter.cut_fragment и выставляет source buffer dirty=true.
paste вызывает formatter.paste_fragment и выставляет target buffer dirty=true.
paste не пишет файл; запись выполняется только save/save_as.
move внутри одного буфера выражается как cut + paste.
replace/append/delete являются formatter-specific modes или helper operations, а не отдельным базовым editor core API.
```

## Format-aware clipboard

Буфер обмена должен понимать, для какого formatter предназначено содержимое.

Clipboard item хранит:

```text
clipboard_item:
  item_id
  source_buffer_id
  source_formatter
  source_address
  source_revision
  payload_kind
  payload
```

Paste command хранит:

```text
paste_request:
  target_buffer_id
  target_formatter
  target_address
  mode
  clipboard_item_id
```

Правила совместимости:

```text
- text -> text paste разрешён;
- yaml -> yaml paste разрешён;
- yaml -> text paste разрешён только как rendered text, если mode явно это просит;
- text -> yaml paste запрещён по умолчанию, кроме явного parse_as_yaml режима;
- несовместимая вставка возвращает CLIPBOARD_FORMAT_MISMATCH;
- если source buffer изменился после copy/cut, paste должен либо использовать snapshot, либо вернуть CLIPBOARD_SOURCE_STALE согласно выбранной политике.
```

## Старые YAML-команды как совместимость

Старые команды не должны определять архитектуру. Они раскладываются по слоям:

```text
yaml_load            -> buffer.open + yaml_formatter.parse
yaml_write_checked   -> buffer.save / buffer.save_as
yaml_validate        -> yaml_formatter.validate
yaml_get             -> search.find_one or formatter.get_unit
yaml_get_command     -> search.find_one with YAML query
yaml_set             -> formatter.paste_fragment(mode=set)
yaml_replace_block   -> formatter.paste_fragment(mode=replace_block)
yaml_append          -> formatter.paste_fragment(mode=append)
yaml_delete          -> formatter.cut_fragment + discard fragment
yaml_move            -> formatter.cut_fragment + formatter.paste_fragment
yaml_clipboard_*     -> editor copy/cut/paste + clipboard internals
```

Новый нормальный model-facing API:

```text
open
save
save_as
close
copy
cut
paste
find
find_one
list_units
validate
```

## Ошибки editor core / formatter / search

```text
BUFFER_NOT_FOUND
BUFFER_ALREADY_OPEN
BUFFER_HAS_UNSAVED_CHANGES
BUFFER_STALE
BUFFER_INVALID
validate
validate_file
```

## validate_file: проверка формата файла или буфера

Нужна отдельная API-команда:

```text
validate_file
```

Назначение: проверить файл или уже открытый буфер на предмет ошибок формата. Это не поиск, не редактирование и не сохранение. Это форматная проверка документа.

Команда нужна менеджеру проектов, чтобы по имени файла проверять узлы плана реализации и другие документы без ручного выбора форматтера.

Семантика:

```text
validate_file(file_path, formatter=auto, buffer_id=null, schema=null, options=null) -> validation_result
```

Правила:

```text
- если указан buffer_id, проверяется document из буфера в памяти;
- если указан file_path и buffer_id не указан, файл читается как raw_content;
- formatter=auto выбирает форматтер по расширению файла;
- выбранный formatter выполняет проверку формата через базовый интерфейс;
- validate_file не меняет buffer dirty state;
- validate_file не пишет файл;
- validate_file должен возвращать diagnostics, errors, warnings и formatter_name.
```

Выбор форматтера по расширению:

```text
.yaml, .yml -> yaml formatter
.txt, .text, unknown plain text mode -> text formatter
future: .json -> json formatter
future: .md, .markdown -> markdown formatter
```

Для менеджера проектов важен сценарий:

```json
{
  "command": "validate_file",
  "file_path": "docs/plans/G-009-editor-core-buffer-registry/README.yaml"
}
```

Ожидаемое поведение:

```text
1. API определяет formatter по имени файла.
2. Formatter получает raw_content или buffer.document.
3. Formatter проверяет формат.
4. API возвращает единый validation_result.
```

## Formatter validation interface

Базовый класс форматтера обязан иметь отдельные методы форматной проверки:

```text
AbstractFormatter
  validate_content(raw_content, *, file_path=null, schema=null, options=null) -> validation_result
  validate_document(document, *, schema=null, options=null) -> validation_result
```

Где:

```text
validate_content проверяет raw file content без необходимости открывать buffer.
validate_document проверяет уже распарсенный document из буфера.
```

Форматтер может внутри использовать parse/render/semantic checks, но контракт наружу должен быть единым.

Для YAML formatter:

```text
validate_content: YAML parse + optional schema + semantic checks + diagnostics
validate_document: semantic checks + deterministic render checks where required
```

Для text formatter:

```text
validate_content: basic text constraints and encoding/line diagnostics
validate_document: array-of-lines structure checks
```

## ForeignFormatter

Нужен класс:

```text
ForeignFormatter
```

Назначение: подключать внешний форматтер, который реализует стандарт `AbstractFormatter`, но фактически выполняет сложные операции на внешнем сервере.

Это нужно для сложных вещей вроде CST, AST, специализированных валидаторов и форматтеров, которые не должны жить внутри базового пакета.

ForeignFormatter должен работать через OpenAPI-вызов сервера на базе `mcp-proxy-adapter`.

Минимальная модель:

```text
ForeignFormatter(AbstractFormatter)
  formatter_name
  openapi_endpoint
  mcp_server_id
  command_mapping
  validate_content(...)
  validate_document(...)
  normalize_address(...)
  copy_fragment(...)
  cut_fragment(...)
  paste_fragment(...)
  iter_units(...)
  match_unit(...)
  compare_units(...)
```

Правила:

```text
- ForeignFormatter обязан соблюдать тот же контракт, что локальные text/yaml formatters;
- API не должен знать, локальный formatter или foreign formatter используется;
- ошибки внешнего сервера должны маппиться в единый error_model;
- nested success=false от внешнего сервера не должен превращаться в success=true;
- mcp-proxy-adapter completion не считается успехом, пока inner result.success=false;
- ForeignFormatter не должен открывать/сохранять файлы сам, если операция является buffer lifecycle;
- ForeignFormatter может выполнять format-specific validation, CST/AST address handling, search units и edit fragments.
```

Пример использования:

```text
.py -> ForeignFormatter backed by CST server
.ts -> ForeignFormatter backed by TypeScript AST/CST server
.md -> future Markdown formatter, local or foreign
```

## Ошибки editor core / formatter / search

```text
BUFFER_NOT_FOUND
BUFFER_ALREADY_OPEN
BUFFER_HAS_UNSAVED_CHANGES
BUFFER_STALE
BUFFER_INVALID
FORMATTER_NOT_FOUND
FORMATTER_UNSUPPORTED
FOREIGN_FORMATTER_FAILED
FOREIGN_FORMATTER_TIMEOUT
FOREIGN_FORMATTER_CONTRACT_VIOLATION
FORMAT_VALIDATION_FAILED
ADDRESS_INVALID
ADDRESS_NOT_FOUND
ADDRESS_NOT_UNIQUE
SEARCH_QUERY_INVALID
SEARCH_NO_MATCH
SEARCH_NOT_UNIQUE
CLIPBOARD_EMPTY
CLIPBOARD_FORMAT_MISMATCH
CLIPBOARD_SOURCE_STALE
SAVE_TARGET_EXISTS
SAVE_TARGET_MISSING
```

Главный принцип обновляется так:

```text
open/new -> validate_file or search/select addresses -> copy/cut/paste in buffers -> formatter.validate_document -> formatter.render -> checked save/save_as
```

## Formatter command discovery

Форматтер может поддерживать не только стандартный `AbstractFormatter` contract, но и собственные специфические команды.

Примеры:

```text
CST formatter:
  xpath-like tree search
  save extracted CST tree to a separate file
  return node parents/children/siblings
  run language-specific normalization

Markdown formatter:
  find heading
  extract section
  move section

JSON formatter:
  json pointer lookup
  json schema focused validation
```

Поэтому у форматтера должен быть статический capability discovery метод:

```text
AbstractFormatter
  list_commands() -> FormatterCommandCatalog
```

Для класса также допустим статический вариант:

```text
@staticmethod
list_commands() -> FormatterCommandCatalog
```

Каталог команд должен включать стандартные и formatter-specific команды:

```text
FormatterCommandCatalog:
  formatter_name
  formatter_version
  standard_commands
  specific_commands
  openapi_schemas
  diagnostics
```

Каждая команда должна иметь метаданные:

```text
FormatterCommandMetadata:
  name
  kind: standard | formatter_specific
  description
  input_schema
  output_schema
  openapi_operation
  side_effects
  writes_files
  requires_buffer
  requires_file_path
  examples
```

Правила:

```text
- standard_commands должны покрывать AbstractFormatter methods;
- specific_commands могут быть любыми, но обязаны иметь OpenAPI-compatible schema;
- команда, которая пишет отдельный файл, должна явно иметь writes_files=true;
- команда, которая сохраняет производный артефакт форматтера, не должна маскироваться под editor save/save_as;
- editor core не должен знать смысл formatter-specific commands;
- public API может предоставить formatter_commands(formatter|buffer_id|file_path) для discovery;
- менеджер проектов может получить список команд после open или через file_path/extension без открытия буфера;
- foreign formatter должен возвращать OpenAPI schema внешнего сервиса или нормализованную схему из неё.
```

Для внешнего сервиса это по сути OpenAPI схема:

```text
ForeignFormatter.list_commands()
  -> calls external OpenAPI/MCP-proxy-adapter command discovery
  -> normalizes result into FormatterCommandCatalog
```

Ошибки:

```text
FORMATTER_COMMAND_DISCOVERY_FAILED
FORMATTER_COMMAND_SCHEMA_INVALID
FORMATTER_COMMAND_UNSUPPORTED
```