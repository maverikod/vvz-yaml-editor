"""XmlFormatter: lxml-based XML converter hooks for ai_editor."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.contracts.error_codes import ErrorCode
from ai_editor.contracts.results import ValidationResult
from ai_editor.formatters.base import AbstractFormatter, Linter
from ai_editor.formatters.tree import Tree, TreeNode


def _element_to_treenode(el: Any) -> TreeNode:
    tag = getattr(el, "tag", "?")
    if callable(tag):
        tag = str(el)
    attrib = dict(getattr(el, "attrib", {}))
    text = (el.text or "").strip()[:60]
    display = f"<{tag}>" + (f" {text}" if text else "") + (f" [{len(el)}]" if len(el) else "")
    line = el.sourceline if hasattr(el, "sourceline") and el.sourceline else 0
    return TreeNode(
        stable_id="",
        node_kind="element",
        start_line=line,
        end_line=line,
        display_text=display[:120],
        metadata={"tag": str(tag), "attrib": attrib, "text": el.text or "", "tail": el.tail or ""},
        children=[_element_to_treenode(child) for child in el],
    )


class XmlFormatter(AbstractFormatter):
    formatter_name = "xml"
    registered_extensions = [".xml", ".xsd", ".xsl", ".xslt", ".svg"]

    def __init__(self, schema_xsd: str | None = None):
        super().__init__()
        self._schema_xsd = schema_xsd

    def parse(self, raw_content: str) -> TreeNode:
        try:
            element = etree.fromstring(raw_content.encode("utf-8"))
        except etree.XMLSyntaxError as exc:
            raise ValueError(str(exc)) from exc
        root_node = _element_to_treenode(element)
        return TreeNode(
            stable_id="",
            node_kind="root",
            start_line=1,
            end_line=raw_content.count("\n") + 1,
            display_text="(xml document)",
            metadata={"_xml_root_tag": root_node.metadata.get("tag", "")},
            children=[root_node],
        )

    def render(self, tree: Tree) -> str:
        if not tree.root.children:
            return ""
        return self.node_to_source(tree.root.children[0])

    def node_from_source(self, raw_block: str) -> TreeNode:
        element = etree.fromstring(raw_block.strip().encode("utf-8"))
        return _element_to_treenode(element)

    def node_to_source(self, node: TreeNode) -> str:
        tag = str(node.metadata.get("tag", "node"))
        attrib_raw = node.metadata.get("attrib", {})
        attrib = dict(attrib_raw) if isinstance(attrib_raw, dict) else {}
        text = str(node.metadata.get("text", ""))
        tail = str(node.metadata.get("tail", ""))
        element = etree.Element(tag, attrib=attrib)
        element.text = text or None
        element.tail = tail or None
        for child in node.children:
            try:
                child_el = etree.fromstring(self.node_to_source(child).encode("utf-8"))
                element.append(child_el)
            except Exception:
                continue
        return etree.tostring(element, encoding="unicode", pretty_print=True)

    def linters(self) -> list[Linter]:
        def _lint_wellformed(path: str) -> ValidationResult:
            try:
                data = Path(path).read_bytes()
                etree.fromstring(data)
            except etree.XMLSyntaxError as exc:
                return ValidationResult(
                    success=False,
                    diagnostics=[
                        Diagnostic(
                            code=ErrorCode.FORMAT_VALIDATION_FAILED,
                            message=f"XML is not well-formed: {exc}",
                            path=path,
                        )
                    ],
                )
            return ValidationResult(success=True, diagnostics=[])

        def _lint_xsd(path: str) -> ValidationResult:
            if not self._schema_xsd:
                return ValidationResult(success=True, diagnostics=[])
            try:
                xml_doc = etree.parse(path)
                xsd_doc = etree.XML(self._schema_xsd.encode("utf-8"))
                schema = etree.XMLSchema(xsd_doc)
                valid = schema.validate(xml_doc)
                if valid:
                    return ValidationResult(success=True, diagnostics=[])
                errors = list(schema.error_log)
                message = errors[0].message if errors else "XML does not satisfy schema"
                return ValidationResult(
                    success=False,
                    diagnostics=[
                        Diagnostic(
                            code=ErrorCode.FORMAT_VALIDATION_FAILED,
                            message=message,
                            path=path,
                        )
                    ],
                )
            except Exception as exc:
                return ValidationResult(
                    success=False,
                    diagnostics=[
                        Diagnostic(
                            code=ErrorCode.FORMAT_VALIDATION_FAILED,
                            message=f"XSD validation failed: {exc}",
                            path=path,
                        )
                    ],
                )

        linters: list[Linter] = [_lint_wellformed]
        if self._schema_xsd:
            linters.append(_lint_xsd)
        return linters

    def to_string(self, fragment: Any) -> str:
        if hasattr(fragment, "tag"):
            return etree.tostring(fragment, encoding="unicode")
        return str(fragment)

    def from_string(self, body: str) -> Any:
        return etree.fromstring(body.encode("utf-8"))
