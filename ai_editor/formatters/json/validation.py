"""JSON document validation and FormatterUnit matching for ai_editor JsonFormatter."""
from __future__ import annotations

import json
from typing import Any

from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.contracts.results import ValidationResult
from ai_editor.formatters.base import ComparisonResult, FormatterUnit


def json_validate_document(
    doc: Any,
    schema: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate parsed JSON or JSON text with optional schema."""
    data = doc
    if isinstance(doc, str):
        try:
            data = json.loads(doc)
        except json.JSONDecodeError as exc:
            return ValidationResult(
                success=False,
                diagnostics=[
                    Diagnostic(
                        code="JSON_PARSE_FAILED",
                        message=str(exc),
                        details={"line": exc.lineno, "column": exc.colno},
                    )
                ],
            )
    else:
        try:
            json.dumps(doc)
        except (TypeError, ValueError) as exc:
            return ValidationResult(
                success=False,
                diagnostics=[Diagnostic(code="JSON_PARSE_FAILED", message=str(exc))],
            )

    require_schema = bool((options or {}).get("require_schema"))
    if schema is not None:
        try:
            import jsonschema  # type: ignore
        except ImportError:
            if require_schema:
                return ValidationResult(
                    success=False,
                    diagnostics=[
                        Diagnostic(
                            code="SCHEMA_NOT_FOUND",
                            message="jsonschema package is not installed",
                        )
                    ],
                )
            return ValidationResult(success=True, diagnostics=[])
        validator = jsonschema.Draft7Validator(schema)
        diagnostics: list[Diagnostic] = []
        for err in validator.iter_errors(data):
            path = "/" + "/".join(str(x) for x in err.path) if err.path else ""
            diagnostics.append(
                Diagnostic(
                    code="SCHEMA_VALIDATION_FAILED",
                    message=err.message,
                    path=path,
                    details={"validator": err.validator},
                )
            )
        if diagnostics:
            return ValidationResult(success=False, diagnostics=diagnostics)
    return ValidationResult(success=True, diagnostics=[])


def json_match_unit(unit: FormatterUnit, query: dict[str, Any]) -> bool:
    """Match unit against supported query constraints."""
    text = query.get("contains_text")
    if text is not None and str(text).lower() not in unit.display_text.lower():
        return False
    node_type = query.get("node_type")
    if node_type is not None and str(node_type) != unit.unit_kind:
        return False
    metadata_key = query.get("metadata_key")
    metadata_value = query.get("metadata_value")
    if metadata_key is not None:
        if metadata_key not in unit.metadata:
            return False
        if "metadata_value" in query and unit.metadata.get(metadata_key) != metadata_value:
            return False
    elif "metadata_value" in query:
        if all(value != metadata_value for value in unit.metadata.values()):
            return False
    return True


def json_compare_units(
    unit_a: FormatterUnit,
    unit_b: FormatterUnit,
    options: dict[str, Any] | None = None,
) -> ComparisonResult:
    """Compare formatter units with optional metadata ignore mode."""
    ignore_metadata = bool((options or {}).get("ignore_metadata", False))
    metadata_equal = unit_a.metadata == unit_b.metadata
    equal = (
        unit_a.address == unit_b.address
        and unit_a.unit_kind == unit_b.unit_kind
        and unit_a.display_text == unit_b.display_text
        and (ignore_metadata or metadata_equal)
    )
    return ComparisonResult(
        equal=equal,
        details={
            "address_a": unit_a.address,
            "address_b": unit_b.address,
            "unit_kind_a": unit_a.unit_kind,
            "unit_kind_b": unit_b.unit_kind,
            "metadata_equal": metadata_equal,
        },
    )
