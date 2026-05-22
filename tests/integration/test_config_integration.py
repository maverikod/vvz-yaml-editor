"""parent tactical step - AiEditorConfig integration with main.py startup."""
from __future__ import annotations

import inspect

import pytest

from ai_editor.config.config_section import AiEditorConfig
from ai_editor.config.config_validator import AiEditorConfigValidator


def test_ai_editor_config_importable() -> None:
    cfg = AiEditorConfig.from_dict({})
    assert cfg.formatter.small_file_threshold == "50kb"
    assert cfg.formatter.small_file_formatter == "text"
    assert cfg.sessions.base_dir == "/tmp/ai_editor_sessions"


def test_from_config_json_reads_ai_editor_section() -> None:
    raw = {"ai_editor": {"formatter": {"small_file_threshold": "2kb"}}}
    cfg = AiEditorConfig.from_config_json(raw)
    assert cfg.formatter.small_file_threshold == "2kb"


def test_validator_returns_list() -> None:
    errors = AiEditorConfigValidator().validate({})
    assert isinstance(errors, list)


def test_main_validates_before_from_config_json(monkeypatch: pytest.MonkeyPatch) -> None:
    import ai_editor.main as main_mod

    src = inspect.getsource(main_mod.main)
    v_idx = src.index("AiEditorConfigValidator")
    f_idx = src.index("AiEditorConfig.from_config_json")
    assert v_idx < f_idx, "validator must run before from_config_json in main.py"
