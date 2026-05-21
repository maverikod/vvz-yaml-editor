# AI editor (`vvz-ai-editor`)

Python library for AI-assisted structural editing of YAML documents (path-based API, checked writes). PyPI distribution: **`vvz-ai-editor`**; import package: **`ai_editor`**.

- **Spec:** [`docs/tech_spec.md`](docs/tech_spec.md)
- **Project rules (Cursor / agents):** [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md)
- **Repo overlay for agents:** [`docs/agents/project_overlay.md`](docs/agents/project_overlay.md)

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check ai_editor tests
```
