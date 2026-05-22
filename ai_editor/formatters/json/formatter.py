"""JSON formatter: mapping/sequence/scalar tree conversion hooks for ai_editor."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.contracts.error_codes import ErrorCode
from ai_editor.contracts.results import OperationResult, ValidationResult
from ai_editor.formatters.base import AbstractFormatter, ComparisonResult, FormatterUnit, Linter
from ai_editor.formatters.tree import Tree, TreeNode
from ai_editor.formatters.json.address import JsonAddressError, resolve_json_address
from ai_editor.formatters.json import mutations as json_mutations
from ai_editor.formatters.json.validation import (
    json_compare_units,
    json_match_unit,
    json_validate_document,
)

_DISPLAY_MAX = 120


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _scalar_display(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= _DISPLAY_MAX:
        return text
    return text[: _DISPLAY_MAX - 3] + "..."


def _value_to_node(value: Any, *, key: str | None = None, index: int | None = None) -> TreeNode:
    meta: dict[str, Any] = {}
    if key is not None:
        meta["key"] = key
    if index is not None:
        meta["index"] = index
    if isinstance(value, dict):
        children = [_value_to_node(v, key=k) for k, v in value.items()]
        return TreeNode("", "mapping", 1, 1, "{...}", meta, children)
    if isinstance(value, list):
        children = [_value_to_node(v, index=i) for i, v in enumerate(value)]
        return TreeNode("", "sequence", 1, 1, "[...]", meta, children)
    meta["value"] = value
    meta["json_type"] = _json_type(value)
    return TreeNode("", "scalar", 1, 1, _scalar_display(value), meta, [])


def _node_to_value(node: TreeNode) -> Any:
    if node.node_kind == "root":
        if not node.children:
            return None
        return _node_to_value(node.children[0])
    if node.node_kind == "mapping":
        out: dict[str, Any] = {}
        for child in node.children:
            key = str(child.metadata.get("key", ""))
            out[key] = _node_to_value(child)
        return out
    if node.node_kind == "sequence":
        return [_node_to_value(child) for child in node.children]
    if node.node_kind == "scalar":
        return node.metadata.get("value")
    raise ValueError(f"Unknown node_kind: {node.node_kind}")


def _build_root_node(value: Any) -> TreeNode:
    child = _value_to_node(value)
    return TreeNode(
        "",
        "root",
        1,
        1,
        "(json document)",
        {},
        [child],
    )


def _make_json_parse_linter() -> Linter:
    def _lint(path: str) -> ValidationResult:
        try:
            raw = Path(path).read_text(encoding="utf-8")
            json.loads(raw)
            return ValidationResult(success=True, diagnostics=[])
        except json.JSONDecodeError as exc:
            return ValidationResult(
                success=False,
                diagnostics=[
                    Diagnostic(
                        code="JSON_PARSE_FAILED",
                        message=str(exc),
                        path=path,
                        details={"line": exc.lineno, "column": exc.colno},
                    )
                ],
            )

    return _lint


def _make_jsonschema_linter(schema: dict[str, Any] | None) -> Linter:
    def _lint(path: str) -> ValidationResult:
        if schema is None:
            return ValidationResult(success=True, diagnostics=[])
        try:
            import jsonschema  # type: ignore
        except ImportError:
            return ValidationResult(success=True, diagnostics=[])
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return ValidationResult(
                success=False,
                diagnostics=[Diagnostic(code="JSON_PARSE_FAILED", message=str(exc), path=path)],
            )
        validator = jsonschema.Draft7Validator(schema)
        diagnostics: list[Diagnostic] = []
        for err in validator.iter_errors(data):
            diagnostics.append(
                Diagnostic(
                    code="SCHEMA_VALIDATION_FAILED",
                    message=err.message,
                    path="/" + "/".join(str(part) for part in err.path) if err.path else "",
                )
            )
        return ValidationResult(success=not diagnostics, diagnostics=diagnostics)

    return _lint


class JsonFormatter(AbstractFormatter):
    formatter_name = "json"
    registered_extensions = [".json"]

    def __init__(self, schema: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._schema = schema

    def parse(self, raw_content: str) -> TreeNode:
        try:
            value = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON parse error: {exc}") from exc
        return _build_root_node(value)

    def render(self, tree: Tree) -> str:
        value = _node_to_value(tree.root)
        return json.dumps(value, indent=2, ensure_ascii=False) + "\n"

    def node_from_source(self, raw_block: str) -> TreeNode:
        text = raw_block.strip()
        value = json.loads(text)
        return _value_to_node(value)

    def node_to_source(self, node: TreeNode) -> str:
        if node.node_kind not in {"mapping", "sequence", "scalar"}:
            raise ValueError(f"Unknown node_kind: {node.node_kind}")
        return json.dumps(_node_to_value(node), indent=2, ensure_ascii=False)

    def linters(self) -> list[Linter]:
        return [_make_json_parse_linter(), _make_jsonschema_linter(self._schema)]

    def validate_document(
        self,
        schema: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Validate current tree as JSON."""
        if self._tree is None:
            return ValidationResult(
                success=False,
                diagnostics=[Diagnostic(code="JSON_PARSE_FAILED", message="No tree loaded")],
            )
        data = _node_to_value(self._tree.root)
        return json_validate_document(data, schema or self._schema, options)

    def match_unit(self, unit: FormatterUnit, query: dict[str, Any]) -> bool:
        return json_match_unit(unit, query)

    def compare_units(
        self,
        unit_a: FormatterUnit,
        unit_b: FormatterUnit,
        options: dict[str, Any] | None = None,
    ) -> ComparisonResult:
        return json_compare_units(unit_a, unit_b, options)

    def diagnostics(self, tree: Tree | None = None) -> list[Diagnostic]:
        active = tree or self._tree
        if active is None:
            return []
        data = _node_to_value(active.root)
        return json_validate_document(data, self._schema, {}).diagnostics

    def _tree_to_document(self) -> Any:
        """Return parsed JSON document from active tree."""
        if self._tree is None:
            raise RuntimeError("No tree loaded")
        return _node_to_value(self._tree.root)

    def _apply_document(self, document: Any) -> None:
        """Apply updated document into the in-memory formatter tree."""
        root = _build_root_node(document)
        if self._tree is None:
            self._tree = Tree(root=root)
        else:
            self._tree.root = root
        self._id_index.clear()
        self._assign_stable_ids(self._tree.root)

    def _map_json_error(self, exc: JsonAddressError) -> ErrorCode:
        mapping = {
            "PATH_NOT_FOUND": ErrorCode.PATH_NOT_FOUND,
            "PATH_NOT_UNIQUE": ErrorCode.PATH_NOT_UNIQUE,
            "PATH_PARSE_FAILED": ErrorCode.ADDRESS_INVALID,
            "TARGET_TYPE_MISMATCH": ErrorCode.ADDRESS_INVALID,
            "CLIPBOARD_EMPTY": ErrorCode.CLIPBOARD_EMPTY,
        }
        return mapping.get(exc.error_code, ErrorCode.ADDRESS_INVALID)

    def resolve_address(self, address: str) -> Any:
        """Resolve structural JSON address against current document."""
        return resolve_json_address(self._tree_to_document(), address)

    def document_mutate_set(self, address: str, value: Any) -> tuple[list[str], OperationResult]:
        try:
            document, paths = json_mutations.json_mutate_set(self._tree_to_document(), address, value)
            self._apply_document(document)
            return paths, OperationResult(success=True)
        except JsonAddressError as exc:
            return [], OperationResult(success=False, error_code=self._map_json_error(exc), message=str(exc))

    def document_mutate_replace_block(self, address: str, content: Any) -> tuple[list[str], OperationResult]:
        try:
            document, paths = json_mutations.json_mutate_replace_block(
                self._tree_to_document(), address, content
            )
            self._apply_document(document)
            return paths, OperationResult(success=True)
        except JsonAddressError as exc:
            return [], OperationResult(success=False, error_code=self._map_json_error(exc), message=str(exc))

    def document_mutate_append(
        self, address: str, value: Any, *, dedupe: bool = False
    ) -> tuple[list[str], OperationResult]:
        try:
            document, paths = json_mutations.json_mutate_append(
                self._tree_to_document(), address, value, dedupe=dedupe
            )
            self._apply_document(document)
            return paths, OperationResult(success=True)
        except JsonAddressError as exc:
            return [], OperationResult(success=False, error_code=self._map_json_error(exc), message=str(exc))

    def document_mutate_delete(self, address: str) -> tuple[list[str], OperationResult]:
        try:
            document, paths = json_mutations.json_mutate_delete(self._tree_to_document(), address)
            self._apply_document(document)
            return paths, OperationResult(success=True)
        except JsonAddressError as exc:
            return [], OperationResult(success=False, error_code=self._map_json_error(exc), message=str(exc))

    def document_mutate_move(
        self, source: str, target: str, position: int | str = "last"
    ) -> tuple[list[str], OperationResult]:
        try:
            document, paths = json_mutations.json_mutate_move(
                self._tree_to_document(), source, target, position=position
            )
            self._apply_document(document)
            return paths, OperationResult(success=True)
        except JsonAddressError as exc:
            return [], OperationResult(success=False, error_code=self._map_json_error(exc), message=str(exc))

    def document_copy_fragment(self, address: str) -> tuple[list[str], OperationResult]:
        try:
            _, paths = json_mutations.json_copy_fragment(self._tree_to_document(), address)
            return paths, OperationResult(success=True)
        except JsonAddressError as exc:
            return [], OperationResult(success=False, error_code=self._map_json_error(exc), message=str(exc))

    def document_cut_fragment(self, address: str) -> tuple[list[str], OperationResult]:
        try:
            document, paths = json_mutations.json_cut_fragment(self._tree_to_document(), address)
            self._apply_document(document)
            return paths, OperationResult(success=True)
        except JsonAddressError as exc:
            return [], OperationResult(success=False, error_code=self._map_json_error(exc), message=str(exc))

    def document_paste_fragment(
        self, target: str, position: int | str = "last"
    ) -> tuple[list[str], OperationResult]:
        try:
            document, paths = json_mutations.json_paste_fragment(
                self._tree_to_document(), target, position=position
            )
            self._apply_document(document)
            return paths, OperationResult(success=True)
        except JsonAddressError as exc:
            return [], OperationResult(success=False, error_code=self._map_json_error(exc), message=str(exc))
