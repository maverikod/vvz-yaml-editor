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

Нужен не только набор YAML-команд, а общий объект редактора, отделённый от конкретного формата документа.

YAML должен быть первым структурным форматтером, но модель редактора не должна быть YAML-специфичной. В дальнейшем туда естественно добавятся:

```text
text
yaml
json
markdown
```

На первом этапе обязательны только:

```text
text
yaml
```

## Реестр буферов

Редактор должен иметь динамически изменяемый реестр буферов:

```text
buffer_registry
  buffer_id -> buffer
```

Один буфер — это один открытый документ. Буфер жёстко связан с файлом либо является новым несохранённым документом.

```text
file-backed buffer:
  buffer_id
  file_path
  formatter
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
  original_hash: null
  current_hash
  dirty: true
  revision
  status
```

Правила:

```text
- один file_path не должен иметь два открытых буфера;
- повторный open уже открытого файла возвращает существующий buffer_id;
- buffer содержит formatter/backend, который определяет parse/render/validate/path/copy/paste semantics;
- dirty показывает, отличается ли текущий документ буфера от последнего сохранённого состояния;
- save/save_as — единственные операции, которые пишут файл;
- copy/cut/paste работают только между буферами и не читают/пишут файлы напрямую.
```

## Минимальный интерфейс редактора

Снаружи интерфейс должен быть привычным, а не техническим:

```text
open
save
save_as
close
copy
cut
paste
```

Семантика:

```text
open(file_path, formatter=auto) -> buffer_id
save(buffer_id)
save_as(buffer_id, file_path, overwrite=false)
close(buffer_id, save=false | true | error_if_dirty)
copy(source_buffer_id, source_path)
cut(source_buffer_id, source_path)
paste(target_buffer_id, target_path, mode)
```

Правила записи:

```text
copy не меняет буфер.
cut меняет source buffer и выставляет dirty=true.
paste меняет target buffer и выставляет dirty=true.
save проверяет formatter.validate/render и пишет связанный file_path атомарно.
save_as связывает unsaved buffer с file_path и пишет его атомарно.
close dirty buffer без save должен либо явно discard-ить изменения, либо вернуть BUFFER_HAS_UNSAVED_CHANGES.
```

## Форматтер в буфере

Каждый буфер обязан содержать formatter:

```text
formatter: text | yaml
```

На первом этапе:

```text
text formatter: документ представлен как массив строк; операции работают с диапазонами/строковыми блоками.
yaml formatter: документ представлен как YAML-дерево; операции работают со структурными YAML path.
```

Formatter отвечает за:

```text
parse
render
validate
normalize_path
copy_fragment
cut_fragment
paste_fragment
changed_paths
diagnostics
```

Editor core не должен знать YAML path details. Он вызывает formatter API.

## Format-aware clipboard

Буфер обмена должен понимать, для какого formatter предназначено содержимое.

Clipboard item должен хранить минимум:

```text
clipboard_item:
  item_id
  source_buffer_id
  source_formatter
  payload_kind
  payload
  source_path
  source_revision
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

## Ошибки редактора

Нужны отдельные ошибки уровня editor core:

```text
BUFFER_NOT_FOUND
BUFFER_ALREADY_OPEN
BUFFER_HAS_UNSAVED_CHANGES
BUFFER_STALE
BUFFER_INVALID
FORMATTER_NOT_FOUND
FORMATTER_UNSUPPORTED
CLIPBOARD_EMPTY
CLIPBOARD_FORMAT_MISMATCH
CLIPBOARD_SOURCE_STALE
SAVE_TARGET_EXISTS
SAVE_TARGET_MISSING
```

Главный принцип обновляется так:

```text
open/new -> edit buffers in memory with copy/cut/paste -> formatter.validate -> formatter.render -> checked save/save_as
```