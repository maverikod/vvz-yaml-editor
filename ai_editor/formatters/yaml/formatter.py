"""YamlFormatter: ruamel.yaml conversion hooks for ai_editor."""
from __future__ import annotations

from io import StringIO
from typing import Any

from ruamel.yaml import YAML

from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.formatters.base import (
    AbstractFormatter,
    ComparisonResult,
    FormatterUnit,
    Linter,
)
from ai_editor.formatters.tree import Tree, TreeNode
from ai_editor.formatters.yaml import mutations as ym
from ai_editor.formatters.yaml import validation as yv


class YamlFormatter(AbstractFormatter):
    """YAML formatter: ruamel round-trip converters; base owns tree mutations."""

    formatter_name = "yaml"
    registered_extensions = [".yaml", ".yml"]

    def __init__(self) -> None:
        super().__init__()
        self._yaml = YAML(typ="rt")
        self._yaml.preserve_quotes = True
        self._document: Any = None

    def _kind_for(self, value: Any) -> str:
        if isinstance(value, dict):
            return "mapping"
        if isinstance(value, list):
            return "sequence"
        return "scalar"

    def _node_from_value(self, value: Any, display: str) -> TreeNode:
        kind = self._kind_for(value)
        children: list[TreeNode] = []
        if kind == "mapping":
            for k, v in value.items():
                children.append(
                    TreeNode("", "scalar", 0, 0, str(k), {"key": str(k), "value": v}, [])
                )
        elif kind == "sequence":
            for i, v in enumerate(value):
                children.append(
                    TreeNode("", "scalar", 0, 0, f"[{i}]", {"index": i, "value": v}, [])
                )
        return TreeNode("", kind, 1, 1, display[:120], {"value": value}, children)

    def parse(self, raw_content: str) -> TreeNode:
        self._document = self._yaml.load(raw_content) or {}
        return self._node_from_value(self._document, "yaml root")

    def render(self, tree: Tree) -> str:
        buf = StringIO()
        doc = tree.root.metadata.get("value", self._document or {})
        self._yaml.dump(doc, buf)
        return buf.getvalue()

    def node_from_source(self, raw_block: str) -> TreeNode:
        doc = self._yaml.load(raw_block)
        return self._node_from_value(doc, raw_block.strip()[:80])

    def node_to_source(self, node: TreeNode) -> str:
        buf = StringIO()
        self._yaml.dump(node.metadata.get("value", {}), buf)
        return buf.getvalue()

    def linters(self) -> list[Linter]:
        return [yv.yaml_linter_factory(self)]

    def validate_document(
        self, document: Any, schema: Any = None, options: dict[str, Any] | None = None
    ):
        return yv.yaml_validate_document(document, schema, options)

    def match_unit(self, unit: FormatterUnit, query: dict[str, Any]) -> bool:
        return yv.yaml_match_unit(unit, query)

    def compare_units(
        self,
        unit_a: FormatterUnit,
        unit_b: FormatterUnit,
        options: dict[str, Any] | None = None,
    ) -> ComparisonResult:
        return yv.yaml_compare_units(unit_a, unit_b, options)

    def diagnostics(self, tree: Tree | None = None) -> list[Diagnostic]:
        t = tree or self._tree
        doc = t.root.metadata.get("value", self._document) if t else self._document
        return yv.yaml_diagnostics(doc)

    def _apply_doc(self, doc: Any) -> None:
        self._document = doc
        if self._tree:
            root = self._node_from_value(doc, "yaml root")
            self._id_index.clear()
            self._assign_stable_ids(root)
            self._tree.root = root

    def yaml_mutate_set(self, address: str, value: Any):
        doc, paths = ym.yaml_mutate_set(self._document, address, value)
        self._apply_doc(doc)
        return doc, paths

    def yaml_mutate_replace_block(self, address: str, block: Any):
        doc, paths = ym.yaml_mutate_replace_block(self._document, address, block)
        self._apply_doc(doc)
        return doc, paths

    def yaml_mutate_append(self, address: str, value: Any, dedupe: bool = False):
        doc, paths = ym.yaml_mutate_append(self._document, address, value, dedupe=dedupe)
        self._apply_doc(doc)
        return doc, paths

    def yaml_mutate_delete(self, address: str):
        doc, paths = ym.yaml_mutate_delete(self._document, address)
        self._apply_doc(doc)
        return doc, paths

    def yaml_mutate_move(self, source: str, target: str):
        doc, paths = ym.yaml_mutate_move(self._document, source, target)
        self._apply_doc(doc)
        return doc, paths

    def yaml_copy_fragment(self, address: str):
        return ym.yaml_copy_fragment(self._document, address)

    def yaml_cut_fragment(self, address: str):
        doc, frag, paths = ym.yaml_cut_fragment(self._document, address)
        self._apply_doc(doc)
        return doc, frag, paths

    def yaml_paste_fragment(self, address: str, fragment: dict[str, Any], mode: str = "append"):
        doc, paths = ym.yaml_paste_fragment(self._document, address, fragment, mode=mode)
        self._apply_doc(doc)
        return doc, paths
