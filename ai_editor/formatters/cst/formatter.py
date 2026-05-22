"""CST formatter integration class."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import libcst as cst

from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.contracts.results import ValidationResult
from ai_editor.formatters.base import AbstractFormatter, ComparisonResult, FormatterUnit, Linter
from ai_editor.formatters.cst.docstring_meta import DocstringMeta
from ai_editor.formatters.cst.models import CSTTree
from ai_editor.formatters.cst.sidecar import project_cst_path, save_sidecar
from ai_editor.formatters.cst.skeleton import (
    build_declarative_overview,
    build_node_declarative_overview,
)
from ai_editor.formatters.cst.tree_builder import create_tree_from_code, reload_tree_from_file
from ai_editor.formatters.cst.tree_modifier import modify_tree, rollback_tree_to_code
from ai_editor.formatters.cst.tree_modifier_ops import sort_operations
from ai_editor.formatters.tree import Tree, TreeNode
from ai_editor.writer import Writer


class CSTFormatter(AbstractFormatter):
    """Python CST-backed formatter with sidecar-aware helpers."""

    formatter_name = "cst"
    registered_extensions = [".py"]

    def __init__(self) -> None:
        super().__init__()
        self._tree: CSTTree | None = None

    def _cst_tree_to_tree_node(self, tree: CSTTree) -> TreeNode:
        return TreeNode(
            stable_id="",
            node_kind="root",
            start_line=1,
            end_line=max(1, tree.module.code.count("\n") + 1),
            display_text="(python module)",
            metadata={"cst_tree_id": tree.tree_id},
            children=[],
        )

    def parse(self, raw_content: str) -> TreeNode:
        self._tree = create_tree_from_code(raw_content)
        return self._cst_tree_to_tree_node(self._tree)

    def render(self, tree: Tree) -> str:  # noqa: ARG002
        return self._tree.module.code if self._tree else ""

    def node_from_source(self, raw_block: str) -> TreeNode:
        snippet = raw_block.strip()
        if not snippet:
            raise ValueError("raw_block cannot be empty")
        try:
            parsed = cst.parse_statement(snippet)
            kind = type(parsed).__name__
        except Exception:
            parsed = cst.parse_module(snippet)
            kind = type(parsed).__name__
        return TreeNode(
            stable_id="",
            node_kind=kind,
            start_line=1,
            end_line=max(1, snippet.count("\n") + 1),
            display_text=snippet.splitlines()[0][:120],
            metadata={"source": raw_block},
            children=[],
        )

    def node_to_source(self, node: TreeNode) -> str:
        return str(node.metadata.get("source", ""))

    def _compile_linter(self, path: str) -> ValidationResult:
        try:
            source = Path(path).read_text(encoding="utf-8")
            compile(source, path, "exec")
            return ValidationResult(success=True, diagnostics=[])
        except SyntaxError as exc:
            return ValidationResult(
                success=False,
                diagnostics=[
                    Diagnostic(
                        code="CST_COMPILE_FAILED",
                        message=str(exc),
                        path=path,
                        details={"line": exc.lineno, "column": exc.offset},
                    )
                ],
            )

    def linters(self) -> list[Linter]:
        return [self._compile_linter]

    def validate_document(self, tree: CSTTree) -> ValidationResult:
        try:
            compile(tree.module.code, "<cst>", "exec")
        except SyntaxError as exc:
            return ValidationResult(
                success=False,
                diagnostics=[
                    Diagnostic(
                        code="CST_COMPILE_FAILED",
                        message=str(exc),
                        details={"line": exc.lineno, "column": exc.offset},
                    )
                ],
            )
        return ValidationResult(success=True, diagnostics=[])

    def mutate_set(self, tree: CSTTree, stable_id: str, code: str) -> CSTTree:
        meta = tree.find_by_stable_id(stable_id)
        if meta is None:
            raise ValueError(f"stable_id not found: {stable_id}")
        return modify_tree(tree, [{"action": "replace", "node_id": meta.node_id, "code": code}])

    def mutate_replace_block(self, tree: CSTTree, stable_id: str, code: str) -> CSTTree:
        return self.mutate_set(tree, stable_id, code)

    def mutate_append(
        self,
        tree: CSTTree,
        parent_stable_id: str,
        code: str,
        position: str | int = "last",
    ) -> CSTTree:
        parent = tree.find_by_stable_id(parent_stable_id)
        if parent is None:
            raise ValueError(f"stable_id not found: {parent_stable_id}")
        return modify_tree(
            tree,
            [
                {
                    "action": "insert",
                    "parent_node_id": parent.node_id,
                    "position": position,
                    "code": code,
                }
            ],
        )

    def mutate_delete(self, tree: CSTTree, stable_id: str) -> CSTTree:
        meta = tree.find_by_stable_id(stable_id)
        if meta is None:
            raise ValueError(f"stable_id not found: {stable_id}")
        return modify_tree(tree, [{"action": "delete", "node_id": meta.node_id}])

    def mutate_move(
        self,
        tree: CSTTree,
        stable_id: str,
        target_parent_stable_id: str,
        position: str | int = "last",
    ) -> CSTTree:
        meta = tree.find_by_stable_id(stable_id)
        target_parent = tree.find_by_stable_id(target_parent_stable_id)
        if meta is None or target_parent is None:
            raise ValueError("stable_id not found")
        return modify_tree(
            tree,
            [
                {
                    "action": "move",
                    "node_id": meta.node_id,
                    "parent_node_id": target_parent.node_id,
                    "position": position,
                }
            ],
        )

    def _sort_operations(self, ops: list[dict[str, Any]], tree: CSTTree) -> list[dict[str, Any]]:
        return sort_operations(ops, tree)

    def _apply_operation(self, tree: CSTTree, op: dict[str, Any]) -> CSTTree:
        return modify_tree(tree, [op])

    def to_string(self, fragment: CSTTree) -> str:
        return json.dumps({meta.stable_id: meta.to_sidecar_dict() for meta in fragment.metadata_map.values()})

    def from_string(self, body: str) -> CSTTree:
        _ = json.loads(body)
        # Minimal restoration: metadata payload is parsed, tree content is placeholder.
        return create_tree_from_code("pass\n")

    def match_unit(self, a: FormatterUnit, b: FormatterUnit) -> bool:
        return a.address == b.address

    def compare_units(
        self,
        a: FormatterUnit,
        b: FormatterUnit,
        options: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ComparisonResult:
        return ComparisonResult(equal=a.address == b.address and a.unit_kind == b.unit_kind)

    def write(self, content: str, path, *, tree: CSTTree | None = None) -> None:
        writer = Writer()
        target = Path(path)
        writer.write_result(content, target)
        if tree is not None:
            save_sidecar(project_cst_path(target), tree, writer)

    def render_overview(self) -> tuple[str, list[dict[str, Any]]]:
        if self._tree is None:
            return "", []
        return build_declarative_overview(self._tree)

    def render_node_overview(self, stable_id: str) -> tuple[str, list[dict[str, Any]]]:
        if self._tree is None:
            return "", []
        return build_node_declarative_overview(self._tree, stable_id)

    def rollback(self, source: str) -> CSTTree | None:
        if self._tree is None:
            return None
        return rollback_tree_to_code(self._tree, source)

    def reload(self, file_path: str | Path) -> CSTTree | None:
        if self._tree is None:
            return None
        return reload_tree_from_file(self._tree, file_path)
