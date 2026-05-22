"""YAML validation, unit match/compare, and diagnostics."""
from __future__ import annotations

from typing import Any, Callable

from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.contracts.error_codes import ErrorCode
from ai_editor.contracts.results import ValidationResult
from ai_editor.formatters.base import ComparisonResult, FormatterUnit
from ai_editor.formatters.yaml.address import resolve_address

_PLAN_KINDS = frozenset({"spec", "global", "tactical", "atomic"})
_PLAN_STATUSES = frozenset(
    {"draft", "ready_for_review", "ready_for_implementation", "blocked"}
)


def _check_plan_task_v1(document: dict[str, Any]) -> list[Diagnostic]:
    """Nine semantic checks for plan_task_v1 documents."""
    diags: list[Diagnostic] = []
    if document.get("format") != "plan_task_v1":
        diags.append(
            Diagnostic(
                code=ErrorCode.VALIDATION_FAILED,
                message="format must be plan_task_v1",
                path="format",
            )
        )
    kind = document.get("kind")
    if kind not in _PLAN_KINDS:
        diags.append(Diagnostic(code=ErrorCode.VALIDATION_FAILED, message="invalid kind", path="kind"))
    depends = document.get("depends_on")
    if depends is not None and (
        not isinstance(depends, list) or not all(isinstance(x, str) for x in depends)
    ):
        diags.append(
            Diagnostic(
                code=ErrorCode.VALIDATION_FAILED,
                message="depends_on must be list[str]",
                path="depends_on",
            )
        )
    commands = document.get("commands")
    if commands is not None:
        if not isinstance(commands, list):
            diags.append(
                Diagnostic(
                    code=ErrorCode.VALIDATION_FAILED,
                    message="commands must be a list",
                    path="commands",
                )
            )
        else:
            names: list[str] = []
            for i, cmd in enumerate(commands):
                if not isinstance(cmd, dict):
                    continue
                n = cmd.get("name")
                if isinstance(n, str):
                    if n in names:
                        diags.append(
                            Diagnostic(
                                code=ErrorCode.VALIDATION_FAILED,
                                message=f"duplicate command name {n!r}",
                                path=f"commands[{i}].name",
                            )
                        )
                    names.append(n)
                schema = cmd.get("schema")
                if isinstance(schema, dict):
                    req = schema.get("required")
                    props = schema.get("properties")
                    if isinstance(req, list) and isinstance(props, dict):
                        for r in req:
                            if r not in props:
                                diags.append(
                                    Diagnostic(
                                        code=ErrorCode.VALIDATION_FAILED,
                                        message=f"required {r!r} not in properties",
                                        path=f"commands[{i}].schema.required",
                                    )
                                )
    verification = document.get("verification")
    if not verification or not isinstance(verification, list):
        diags.append(
            Diagnostic(
                code=ErrorCode.VALIDATION_FAILED,
                message="verification must be non-empty list",
                path="verification",
            )
        )
    status = document.get("status")
    if status not in _PLAN_STATUSES:
        diags.append(
            Diagnostic(code=ErrorCode.VALIDATION_FAILED, message="invalid status", path="status")
        )
    return diags


def yaml_validate_document(
    document: Any, schema: Any = None, options: dict[str, Any] | None = None
) -> ValidationResult:
    """Validate YAML document: optional jsonschema + plan_task_v1 semantics."""
    opts = options or {}
    diags: list[Diagnostic] = []
    if opts.get("format") == "plan_task_v1" and isinstance(document, dict):
        diags.extend(_check_plan_task_v1(document))
    if schema is not None:
        try:
            import jsonschema

            jsonschema.validate(document, schema)
        except Exception as exc:
            diags.append(Diagnostic(code=ErrorCode.SCHEMA_VALIDATION_FAILED, message=str(exc), path=None))
    return ValidationResult(success=len(diags) == 0, diagnostics=diags)


def yaml_match_unit(unit: FormatterUnit, query: dict[str, Any]) -> bool:
    text = query.get("contains_text")
    if text and text.lower() not in unit.display_text.lower():
        return False
    kind = query.get("node_type")
    if kind and unit.unit_kind != kind:
        return False
    name = query.get("name")
    if name and name != unit.metadata.get("key") and name not in unit.display_text:
        return False
    return True


def yaml_compare_units(
    unit_a: FormatterUnit, unit_b: FormatterUnit, options: dict[str, Any] | None = None
) -> ComparisonResult:
    _ = options
    equal = (
        unit_a.unit_kind == unit_b.unit_kind
        and unit_a.display_text == unit_b.display_text
        and unit_a.metadata.get("value") == unit_b.metadata.get("value")
    )
    return ComparisonResult(equal=equal, details={"a": unit_a.address, "b": unit_b.address})


def yaml_diagnostics(document: Any) -> list[Diagnostic]:
    if isinstance(document, dict) and document.get("format") == "plan_task_v1":
        return _check_plan_task_v1(document)
    return []


def yaml_linter_factory(formatter: Any) -> Callable[[str], ValidationResult]:
    def _lint(path: str) -> ValidationResult:
        from pathlib import Path

        text = Path(path).read_text(encoding="utf-8")
        try:
            doc = formatter._yaml.load(text) or {}
        except Exception as exc:
            return ValidationResult(
                success=False,
                diagnostics=[Diagnostic(code=ErrorCode.YAML_PARSE_FAILED, message=str(exc))],
            )
        return yaml_validate_document(doc, options={"format": "plan_task_v1"})

    return _lint
