"""Compliance tests for MCP command metadata and schemas."""
from __future__ import annotations

import importlib
import inspect
import pkgutil

import ai_editor.commands as commands_pkg
from mcp_proxy_adapter.commands.base import Command

_REQUIRED_METADATA_KEYS = {
    "name",
    "version",
    "description",
    "category",
    "author",
    "email",
    "detailed_description",
    "parameters",
    "return_value",
    "usage_examples",
    "error_cases",
    "best_practices",
}


def _command_classes() -> list[type[Command]]:
    classes: list[type[Command]] = []
    for modinfo in pkgutil.iter_modules(commands_pkg.__path__, commands_pkg.__name__ + "."):
        if not modinfo.name.endswith("_command"):
            continue
        mod = importlib.import_module(modinfo.name)
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, Command) and obj is not Command and getattr(obj, "name", None):
                classes.append(obj)
    return sorted(classes, key=lambda c: c.name)


def test_all_commands_have_complete_metadata_and_schema() -> None:
    """Every registered command conforms to docs/metadatastd.md required fields."""
    assert len(_command_classes()) == 27
    for cmd_cls in _command_classes():
        schema = cmd_cls.get_schema()
        meta = cmd_cls.metadata()

        assert schema["type"] == "object", cmd_cls.name
        assert "additionalProperties" in schema, cmd_cls.name

        missing = _REQUIRED_METADATA_KEYS - set(meta)
        assert not missing, f"{cmd_cls.name} metadata missing {sorted(missing)}"

        assert meta["usage_examples"], f"{cmd_cls.name} has no usage_examples"
        assert "success" in meta["return_value"], cmd_cls.name

        props = schema.get("properties") or {}
        params = meta.get("parameters") or {}
        assert set(props) == set(params), (
            f"{cmd_cls.name}: schema/metadata parameter mismatch: "
            f"schema-only={set(props)-set(params)} meta-only={set(params)-set(props)}"
        )

        for entry in meta["parameters"].values():
            assert "description" in entry, cmd_cls.name
            assert "type" in entry, cmd_cls.name
            assert "required" in entry, cmd_cls.name
