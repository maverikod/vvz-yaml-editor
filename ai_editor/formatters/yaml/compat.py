"""Legacy YAML command wrappers - do not use in new code.

Thin adapters mapping old yaml_* names to formatter/buffer operations.
Every call logs WARNING. Emergency helpers are named *_unsafe / *_lines.
"""
from __future__ import annotations

import logging
from typing import Any

from ai_editor.formatters.yaml.formatter import YamlFormatter

logger = logging.getLogger(__name__)

_WARN = "legacy YAML compat wrapper called; migrate to buffer/formatter APIs"


def yaml_load(raw_content: str, **kwargs: Any) -> YamlFormatter:
    logger.warning("%s: yaml_load", _WARN)
    fmt = YamlFormatter()
    fmt.open_tree(raw_content)
    return fmt


def yaml_write_checked(fmt: YamlFormatter, path: str, **kwargs: Any) -> dict[str, Any]:
    logger.warning("%s: yaml_write_checked", _WARN)
    from pathlib import Path

    return fmt.write(Path(path), preview_only=kwargs.get("preview_only", False))


def yaml_validate(fmt: YamlFormatter, document: Any = None, **kwargs: Any) -> Any:
    logger.warning("%s: yaml_validate", _WARN)
    from ai_editor.formatters.yaml import validation as yv

    doc = document if document is not None else fmt._document
    return yv.yaml_validate_document(doc, kwargs.get("schema"), kwargs.get("options"))


def yaml_get(fmt: YamlFormatter, address: str, **kwargs: Any) -> Any:
    logger.warning("%s: yaml_get", _WARN)
    return fmt.get_unit(address)


def yaml_get_command(fmt: YamlFormatter, name: str, **kwargs: Any) -> Any:
    logger.warning("%s: yaml_get_command", _WARN)
    for unit in fmt.iter_units():
        if unit.metadata.get("key") == name or name in unit.display_text:
            return unit
    return None


def yaml_set(fmt: YamlFormatter, address: str, value: Any, **kwargs: Any) -> Any:
    logger.warning("%s: yaml_set", _WARN)
    return fmt.yaml_mutate_set(address, value)


def yaml_replace_block(fmt: YamlFormatter, address: str, block: str, **kwargs: Any) -> Any:
    logger.warning("%s: yaml_replace_block", _WARN)
    return fmt.yaml_mutate_replace_block(address, block)


def yaml_append(fmt: YamlFormatter, address: str, value: Any, **kwargs: Any) -> Any:
    logger.warning("%s: yaml_append", _WARN)
    return fmt.yaml_mutate_append(address, value, dedupe=kwargs.get("dedupe", False))


def yaml_delete(fmt: YamlFormatter, address: str, **kwargs: Any) -> Any:
    logger.warning("%s: yaml_delete", _WARN)
    return fmt.yaml_mutate_delete(address)


def yaml_move(fmt: YamlFormatter, source: str, target: str, **kwargs: Any) -> Any:
    logger.warning("%s: yaml_move", _WARN)
    return fmt.yaml_mutate_move(source, target)


def yaml_read_lines_emergency_unsafe(path: str, start: int, end: int, **kwargs: Any) -> list[str]:
    logger.warning("%s: yaml_read_lines_emergency_unsafe", _WARN)
    lines = open(path, encoding="utf-8").readlines()
    return lines[start - 1 : end]


def yaml_write_lines_emergency_unsafe(
    path: str, start: int, lines: list[str], **kwargs: Any
) -> None:
    logger.warning("%s: yaml_write_lines_emergency_unsafe", _WARN)
    all_lines = open(path, encoding="utf-8").readlines()
    all_lines[start - 1 : start - 1 + len(lines)] = [
        ln if ln.endswith("\n") else ln + "\n" for ln in lines
    ]
    open(path, "w", encoding="utf-8").writelines(all_lines)
