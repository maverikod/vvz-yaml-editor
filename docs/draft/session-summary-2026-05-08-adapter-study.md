# Session Summary: 2026-05-08 — Блокировки + изучение mcp_proxy_adapter

## Что было сделано

### 1. Блокировки файлов (завершено)

Изучен `code_analysis/core/database/file_edit_lock.py`. Обновлён G-009:
- `file_edit_lock_policy` раздел в README.yaml
- `abstract_buffer_contract.responsibilities` — добавлен пункт про lock
- `buffer_model.invariants` — 3 инварианта про open/close/save
- `verification.expected` — 3 ожидания
- `acceptance_criteria` — 4 критерия
- `model_assignment_spec.instruction` — полное описание lock lifecycle

Механизм: `files.editing_pid INTEGER NULL`, `os.kill(pid, 0)` для liveness check,
атомарный UPDATE с conditional WHERE, release в finally.

### 2. mcp_proxy_adapter — изучено

**project_id:** `3f4e4ba4-9706-4243-a45b-82fe9c9705bf`
**root:** `/home/vasilyvz/projects/tools/mcp_proxy_adapter`

---

## Архитектура mcp_proxy_adapter

### Как регистрируются команды

Всё через **hooks** — НЕ прямое API.

```python
# В [app_dir]/hooks.py
from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook

def register_commands(registry):
    from ai_editor.commands.open_command import OpenCommand
    from ai_editor.commands.close_command import CloseCommand
    registry.register(OpenCommand, "custom")
    registry.register(CloseCommand, "custom")

register_custom_commands_hook(register_commands)
```

Глобальный `hooks` объект (`CommandHooks`) в `mcp_proxy_adapter.commands.hooks`.

`register_custom_commands_hook(func)` — функция принимает `registry`, регистрирует команды.

Для spawn-mode (очередь) + `use_queue=True` → дополнительно вызвать:
```python
from mcp_proxy_adapter.commands.hooks import register_auto_import_module
register_auto_import_module("ai_editor.commands.some_queue_command")
```

### Шаблон команды (per metadatastd.md)

```python
# ai_editor/commands/buf_open_command.py
class BufOpenCommand(Command):  # наследник mcp_proxy_adapter.commands.base.Command
    name = "buf_open"
    version = "1.0.0"
    descr = "Open a file buffer"
    category = "editor"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return get_buf_open_schema()

    def validate_params(self, params):
        params = super().validate_params(params)
        # semantic checks
        return params

    async def execute(self, file_path: str, ...) -> CommandResult:
        ...

    @classmethod
    def metadata(cls) -> Dict[str, Any]:
        return get_buf_open_metadata(cls)
```

Файловая раскладка:
```
ai_editor/commands/buf_open_command.py
ai_editor/commands/buf_open_schema.py
ai_editor/commands/buf_open_metadata.py
```

### Конфиг — SimpleConfig и расширение

**Адаптер читает** конфиг через `SimpleConfig(config_path).load()` → `SimpleConfigModel`.

**ai_editor НЕ пишет свой config.json** — использует секцию в адаптерном конфиге.

**Вариант А: секция `ai_editor` в корневом config.json:**
```json
{
  "server": { ... },
  "ai_editor": {
    "formatter": {
      "small_file_threshold": "1k",
      "small_file_formatter": "text"
    }
  }
}
```

**Вариант Б: прямо в корень** (если настройки немногочисленны).

**Секция `database`** берётся из `config.json` сервера анализа (корень проекта).
**Пароли** — из `.env` в корне проекта.

### Что создаёт ai_editor для конфига

1. **`AiEditorConfig`** dataclass → `ai_editor/config/config_section.py`  
   Хранит настройки из секции `ai_editor` конфига адаптера.

2. **`AiEditorConfigGenerator`** → `ai_editor/config/config_generator.py`  
   Наследует `SimpleConfigGenerator`. Добавляет генерацию секции `ai_editor` в `generate()`.

3. **`AiEditorConfigValidator`** → `ai_editor/config/config_validator.py`  
   Наследует `BaseValidator`. Валидирует секцию `ai_editor` в `validate(model)`.

4. **Reader** — НЕ пишем свой, используем `SimpleConfig.load()` адаптера.

```python
# ai_editor/config/config_section.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AiEditorFormatterConfig:
    small_file_threshold: str = "1k"  # '1k', '500', '2m', '0'=disabled
    small_file_formatter: str = "text"

@dataclass
class AiEditorConfig:
    formatter: AiEditorFormatterConfig = field(default_factory=AiEditorFormatterConfig)

    @classmethod
    def from_dict(cls, data: dict) -> 'AiEditorConfig':
        # parse from raw config dict
        ...

    @classmethod
    def from_config_json(cls, config_path: str) -> 'AiEditorConfig':
        # load from config.json, read ['ai_editor'] section, use defaults if absent
        ...
```

```python
# ai_editor/config/config_validator.py
from mcp_proxy_adapter.core.config.validators.base_validator import BaseValidator, ValidationError

class AiEditorConfigValidator(BaseValidator):
    def validate(self, raw_config: dict) -> list[ValidationError]:
        errors = []
        ai_cfg = raw_config.get('ai_editor', {})
        # validate threshold syntax, allowed formatters, etc.
        return errors
```

```python
# ai_editor/config/config_generator.py
from mcp_proxy_adapter.core.config.simple_config_generator import SimpleConfigGenerator

class AiEditorConfigGenerator(SimpleConfigGenerator):
    def generate_ai_editor_section(self, ...) -> dict:
        return {
            'ai_editor': {
                'formatter': {
                    'small_file_threshold': '1k',
                    'small_file_formatter': 'text',
                }
            }
        }
```

### Как main.py запускает ai_editor на адаптере

```python
# ai_editor/main.py (или ai_editor/interfaces/mcp_server.py)
from mcp_proxy_adapter.api.app import create_app
from mcp_proxy_adapter.core.server_engine import ServerEngineFactory
from mcp_proxy_adapter.commands.command_registry import registry
from mcp_proxy_adapter.core.config.simple_config import SimpleConfig
from mcp_proxy_adapter.config import get_config

# 1. Загрузить SimpleConfig
simple_config = SimpleConfig(config_path)
model = simple_config.load()

# 2. Дополнительно валидировать секцию ai_editor
from ai_editor.config.config_validator import AiEditorConfigValidator
validator = AiEditorConfigValidator(config_path=config_path)
errors = validator.validate(app_config)
# abort if errors

# 3. Загрузить ai_editor config
from ai_editor.config.config_section import AiEditorConfig
ai_cfg = AiEditorConfig.from_config_json(config_path)

# 4. create_app
app = create_app(..., app_config=app_config, config_path=config_path)

# 5. Зарегистрировать команды
from ai_editor.hooks import register_all_commands
register_all_commands(registry)

# 6. Запустить
engine = ServerEngineFactory.get_engine('hypercorn')
engine.run_server(app, server_config)
```

### Hooks файл ai_editor

```python
# ai_editor/hooks.py
from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook

def _register(registry):
    from ai_editor.commands.buf_open_command import BufOpenCommand
    from ai_editor.commands.buf_close_command import BufCloseCommand
    from ai_editor.commands.buf_save_command import BufSaveCommand
    # ... все команды
    registry.register(BufOpenCommand, "custom")
    registry.register(BufCloseCommand, "custom")
    registry.register(BufSaveCommand, "custom")
    # ...

register_custom_commands_hook(_register)

def register_all_commands(registry):
    _register(registry)
```

### metadatastd.md — ключевые правила

1. **Два слоя РАЗДЕЛЬНО**: `get_schema()` (machine) и `metadata()` (AI/docs). НЕ смешивать.
2. **Раскладка файлов**: `<cmd>_command.py`, `<cmd>_schema.py`, `<cmd>_metadata.py`
3. **Регистрация**: `registry.register(Cmd, 'custom')` через hooks. НЕ напрямую API.
4. **Деструктивные команды**: обязательно `dry_run`.
5. **`validate_params()`**: `super()` первым + семантика.
6. **Обязательные поля** `metadata()`: name, version, description, category, author, email, detailed_description, parameters, return_value, usage_examples, error_cases, best_practices.
7. **Адаптер сам генерирует** JSON-RPC, OpenAPI, MCP tools из `get_schema()` и `metadata()`. НЕ писать API.

---

## СЛЕДУЮЩИЕ ЗАДАЧИ (PENDING)

### ЗАДАЧА 1: T-декомпозиция G-009..G-014

Для каждого G-шага (G-009, G-010, G-011, G-012, G-013, G-014) нужны T-файлы.
Пока T-файлы есть только у G-001..G-008.
После завершения изучения адаптера — добавить T-декомпозицию:
- G-009: T-001 EditorCore, T-002 BufferRegistry, T-003 FileEditLock, T-004 Config
- G-010: T-001 TextFormatter, T-002 YamlFormatter
- G-011: T-001 Search
- G-012: T-001 ForeignFormatter
- G-013: T-001 CSTParser, T-002 Sidecar, T-003 StableId, T-004 Mutations
- G-014: T-001 Rename

### ЗАДАЧА 2: Обновить G-008 — metadatastd требования

В `docs/plans/G-008-regression-release-readiness/README.yaml` уже есть упоминания.
Проверить/добавить:
- Требование metadatastd.md соблюдается для ВСЕХ команд G-008
- Файловая раскладка schema/metadata описана в plane
- `cst_query` (G-013) и `rename` (G-014) также покрыты

### ЗАДАЧА 3: Обновить G-009 — описать интеграцию с адаптером

В G-009 README.yaml добавить:
- Как ai_editor интегрируется с mcp_proxy_adapter (не API напрямую)
- hooks.py → register_custom_commands_hook
- config section ai_editor
- AiEditorConfig, AiEditorConfigGenerator, AiEditorConfigValidator
- main.py паттерн (validate → sync config → create_app → register → run)

### ЗАДАЧА 4: Написать G-008 instruction для команд

G-008 содержит MCP-интерфейс. Нужно в instruction прописать:
- Все команды наследуют `mcp_proxy_adapter.commands.base.Command`
- Регистрируются через `ai_editor/hooks.py` + `register_custom_commands_hook`
- Раскладка файлов по metadatastd.md
- НЕ реализовывать HTTP/JSON-RPC — адаптер делает сам

### ЗАДАЧА 5: Создать docs/plans/G-009-editor-core-buffer-registry/adapter-integration.yaml

Отдельный файл описывающий:
- Паттерн main.py для ai_editor
- Hooks регистрация
- Config section
- Пример конфига

---

## Ключевые пути для следующей сессии

| Файл | Описание |
|------|----------|
| `mcp_proxy_adapter/commands/base.py` | Базовый класс Command, CommandResult |
| `mcp_proxy_adapter/commands/hooks.py` | register_custom_commands_hook, CommandHooks |
| `mcp_proxy_adapter/core/config/simple_config.py` | SimpleConfig, SimpleConfigModel |
| `mcp_proxy_adapter/core/config/simple_config_generator.py` | SimpleConfigGenerator |
| `mcp_proxy_adapter/core/config/simple_config_validator.py` | SimpleConfigValidator |
| `mcp_proxy_adapter/core/config/validators/base_validator.py` | BaseValidator, ValidationError |
| `mcp_proxy_adapter/examples/full_application/main.py` | Полный паттерн запуска |
| `docs/metadatastd.md` (yaml_editor) | Стандарт команд |
| `docs/plans/G-008-regression-release-readiness/README.yaml` | MCP интерфейс |
| `docs/plans/G-009-editor-core-buffer-registry/README.yaml` | Editor core + locks |

## Важные решения (зафиксированы)

1. **НЕ писать API напрямую** — адаптер генерирует из `get_schema()` + `metadata()`
2. **Команды регистрируются через hooks** → `register_custom_commands_hook`
3. **Reader конфига — адаптерный** (`SimpleConfig.load()`), свои только validator + generator
4. **Секция конфига** — `ai_editor` в корне config.json адаптера
5. **database секция** — из config.json сервера анализа
6. **Пароли** — из `.env` в корне проекта
7. **Файловая раскладка команд**: `<cmd>_command.py` + `<cmd>_schema.py` + `<cmd>_metadata.py`
8. **metadatastd.md** — обязательное требование для всех команд G-008, G-013, G-014
