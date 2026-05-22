"""HtmlFormatter: BeautifulSoup4-based HTML converter hooks for ai_editor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from ai_editor.contracts.diagnostic import Diagnostic
from ai_editor.contracts.error_codes import ErrorCode
from ai_editor.contracts.results import ValidationResult
from ai_editor.formatters.base import AbstractFormatter, Linter
from ai_editor.formatters.tree import Tree, TreeNode

_DISPLAY_MAX = 120


def _tag_to_treenode(tag: Tag) -> TreeNode:
    name = tag.name or "?"
    id_attr = str(tag.get("id", ""))
    class_attr = " ".join(tag.get("class") or [])
    text_preview = tag.get_text(separator=" ", strip=True)[:60]

    display = f"<{name}>"
    if id_attr:
        display += f"#{id_attr}"
    if class_attr:
        display += f".{class_attr}"
    if text_preview:
        display += f" {text_preview}"

    children = [_tag_to_treenode(child) for child in tag.children if isinstance(child, Tag)]
    return TreeNode(
        stable_id="",
        node_kind=name,
        start_line=0,
        end_line=0,
        display_text=display[:_DISPLAY_MAX],
        metadata={
            "tag": name,
            "id": id_attr,
            "class": class_attr,
            "attrs": dict(tag.attrs),
            "_html": str(tag),
        },
        children=children,
    )


class HtmlFormatter(AbstractFormatter):
    formatter_name = "html"
    registered_extensions = [".html", ".htm", ".xhtml"]

    def __init__(self, require_full_document: bool = False) -> None:
        super().__init__()
        self._require_full_document = require_full_document

    def parse(self, raw_content: str) -> TreeNode:
        soup = BeautifulSoup(raw_content, "lxml")
        body = soup.body or soup
        block_children = [child for child in body.children if isinstance(child, Tag)]
        children = [_tag_to_treenode(child) for child in block_children]
        return TreeNode(
            stable_id="",
            node_kind="root",
            start_line=1,
            end_line=raw_content.count("\n") + 1,
            display_text="(html document)",
            metadata={
                "_full_html": str(soup),
                "trailing_newline": raw_content.endswith("\n"),
            },
            children=children,
        )

    def render(self, tree: Tree) -> str:
        full_html = tree.root.metadata.get("_full_html")
        trailing_newline = bool(tree.root.metadata.get("trailing_newline", False))
        if isinstance(full_html, str) and full_html:
            rendered = full_html
            if trailing_newline and not rendered.endswith("\n"):
                rendered += "\n"
            return rendered

        rendered = "\n".join(self.node_to_source(child) for child in tree.root.children)
        if trailing_newline and not rendered.endswith("\n"):
            rendered += "\n"
        return rendered

    def node_from_source(self, raw_block: str) -> TreeNode:
        soup = BeautifulSoup(raw_block.strip(), "lxml")
        body = soup.body or soup
        tags = [child for child in body.children if isinstance(child, Tag)]
        if not tags:
            text = raw_block.strip()
            return TreeNode(
                stable_id="",
                node_kind="span",
                start_line=1,
                end_line=1,
                display_text=(f"<span> {text}" if text else "<span>"),
                metadata={"tag": "span", "attrs": {}, "_html": f"<span>{text}</span>"},
                children=[],
            )
        return _tag_to_treenode(tags[0])

    def node_to_source(self, node: TreeNode) -> str:
        html = node.metadata.get("_html")
        if isinstance(html, str) and html:
            return html

        tag_name = str(node.metadata.get("tag") or node.node_kind or "div")
        attrs = dict(node.metadata.get("attrs") or {})
        attr_text = "".join(f' {key}="{value}"' for key, value in attrs.items())
        inner = "".join(self.node_to_source(child) for child in node.children)
        return f"<{tag_name}{attr_text}>{inner}</{tag_name}>"

    def linters(self) -> list[Linter]:
        def _lint_html(path: str) -> ValidationResult:
            content = Path(path).read_text(encoding="utf-8")
            soup = BeautifulSoup(content, "lxml")
            diagnostics: list[Diagnostic] = []
            if self._require_full_document:
                if soup.html is None:
                    diagnostics.append(
                        Diagnostic(
                            code=ErrorCode.FORMAT_VALIDATION_FAILED,
                            message="Missing <html> root element",
                            path=path,
                        )
                    )
                if soup.head is None:
                    diagnostics.append(
                        Diagnostic(
                            code=ErrorCode.FORMAT_VALIDATION_FAILED,
                            message="Missing <head> element",
                            path=path,
                        )
                    )
                if soup.body is None:
                    diagnostics.append(
                        Diagnostic(
                            code=ErrorCode.FORMAT_VALIDATION_FAILED,
                            message="Missing <body> element",
                            path=path,
                        )
                    )
            return ValidationResult(success=not diagnostics, diagnostics=diagnostics)

        return [_lint_html]

    def to_string(self, fragment: Any) -> str:
        return str(fragment)

    def from_string(self, body: str) -> Any:
        soup = BeautifulSoup(body, "lxml")
        body_tag = soup.body or soup
        tags = [child for child in body_tag.children if isinstance(child, Tag)]
        if tags:
            return tags[0]
        return soup
