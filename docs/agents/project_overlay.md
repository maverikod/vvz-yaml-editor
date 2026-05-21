<!--
Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
-->

# Project overlay — `ai_editor` (this repository)

Repository-specific paths, behavior, and restrictions. Universal layout: [`PROJECT_RULES.md`](../PROJECT_RULES.md) §3 (`LAYOUT-*`).

## Functional context

- **Role:** **AI editor** — Python library for structural YAML document editing by tree paths (load, validate, get/set, append/delete/move, atomic `yaml_write_checked`, optional `plan_task_v1` semantics). Consumed as **`pip install vvz-ai-editor`** from an MCP server or other apps.
- **Installable package:** [`ai_editor/`](../../ai_editor/) at repository root (flat layout; **no `src/`**).
- **Specification:** product behavior and command surface live in [`docs/tech_spec.md`](../tech_spec.md).
- **Tests:** pytest suite under [`tests/`](../../tests/). **Non-pytest** harnesses and ops scripts → [`scripts/`](../../scripts/) per **LAYOUT-07**.

## Directories and files beyond the universal skeleton

| Path | Note |
|------|------|
| `docs/tech_spec.md` | Technical specification for the AI editor command surface and validation pipeline. |
| `docs/ai_reports/` | Working AI reports per **LAYOUT-06**; promote stable write-ups into `docs/`. |
| `configs/` | Sample or non-secret configuration snippets when needed (no production secrets in git). |
| `logs/` | Runtime logs (ignored except `.gitkeep`); no secrets. |
| `rules_template_agents_protocols_updated.zip` | Bundled Cursor rules/agents template; regenerate per template README if you maintain a fork. |

## Project-specific restrictions

- **Secrets:** Do not commit credentials, tokens, or private keys.
- **Scope:** Stay within this repository unless the user explicitly allows other paths.
- **Write safety:** Prefer structural APIs and `yaml_write_checked`; line-based `yaml_write_lines_unsafe` is emergency-only per tech spec.
- **Dependencies:** Round-trip YAML uses **`ruamel.yaml`**; path filters may use **`jsonpath-ng`**; schema checks use **`jsonschema`** — see `pyproject.toml`.

## Filled profile pointer

Concrete profile values: [`PROJECT_RULES.md`](../PROJECT_RULES.md) **§7**.
