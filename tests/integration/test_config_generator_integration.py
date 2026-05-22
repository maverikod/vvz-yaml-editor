"""parent tactical step - AiEditorConfigGenerator round-trip integration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_editor.config.config_generator import AiEditorConfigGenerator, ConfigGenerationError
from ai_editor.config.config_section import AiEditorConfig
from ai_editor.config.config_validator import AiEditorConfigValidator


def test_generate_and_validate(tmp_path: Path) -> None:
    out = tmp_path / "config.json"
    gen = AiEditorConfigGenerator()
    gen.generate("https", str(out))
    assert not (tmp_path / "config.json.tmp").exists()
    raw = json.loads(out.read_text(encoding="utf-8"))
    errors = AiEditorConfigValidator().validate(raw)
    assert errors == [] or all("ai_editor" not in e for e in errors)
    cfg = AiEditorConfig.from_config_json(raw)
    assert cfg.formatter.small_file_formatter


def test_invalid_kwargs_raises_and_no_tmp(tmp_path: Path) -> None:
    gen = AiEditorConfigGenerator()
    out = tmp_path / "bad.json"
    with pytest.raises(ConfigGenerationError):
        gen.generate("https", str(out), small_file_threshold="1g")
    assert not (tmp_path / "bad.json.tmp").exists()
