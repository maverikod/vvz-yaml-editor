"""Plain-text formatter: paragraph/line tree conversion hooks for ai_editor."""

from __future__ import annotations

from ai_editor.formatters.base import AbstractFormatter, Linter
from ai_editor.formatters.tree import Tree, TreeNode

_DISPLAY_MAX = 120


def _truncate_display(text: str) -> str:
    if len(text) <= _DISPLAY_MAX:
        return text
    return text[:_DISPLAY_MAX]


def _is_blank(line: str) -> bool:
    return not line.strip()


def _physical_lines(raw_content: str) -> tuple[list[str], bool]:
    trailing_newline = raw_content.endswith("\n")
    if not raw_content:
        return [], trailing_newline
    return raw_content.splitlines(), trailing_newline


def _split_into_paragraphs(lines: list[str]) -> list[list[str]]:
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _is_blank(line):
            if current:
                paragraphs.append(current)
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(current)
    return paragraphs


def _line_node(line_num: int, line: str) -> TreeNode:
    stripped = line.strip()
    return TreeNode(
        stable_id="",
        node_kind="line",
        start_line=line_num,
        end_line=line_num,
        display_text=_truncate_display(stripped),
        metadata={"text": stripped},
        children=[],
    )


def _paragraph_node(start_line: int, lines: list[str]) -> TreeNode:
    line_children = [_line_node(start_line + index, line) for index, line in enumerate(lines)]
    display = line_children[0].display_text if line_children else "(empty paragraph)"
    end_line = line_children[-1].end_line if line_children else start_line
    return TreeNode(
        stable_id="",
        node_kind="paragraph",
        start_line=start_line,
        end_line=end_line,
        display_text=display,
        metadata={},
        children=line_children,
    )


class TextFormatter(AbstractFormatter):
    formatter_name = "text"
    registered_extensions = [".txt", ".log", ".rst", ".ini", ".cfg", ".toml"]

    def parse(self, raw_content: str) -> TreeNode:
        lines, trailing_newline = _physical_lines(raw_content)
        paragraph_blocks = _split_into_paragraphs(lines)

        paragraphs: list[TreeNode] = []
        next_line = 1
        for block in paragraph_blocks:
            paragraph = _paragraph_node(next_line, block)
            paragraphs.append(paragraph)
            next_line = paragraph.end_line + 1

        end_line = paragraphs[-1].end_line if paragraphs else 0
        root_metadata: dict[str, object] = {"trailing_newline": trailing_newline}
        return TreeNode(
            stable_id="",
            node_kind="root",
            start_line=1,
            end_line=end_line,
            display_text="(text document)",
            metadata=root_metadata,
            children=paragraphs,
        )

    def render(self, tree: Tree) -> str:
        root = tree.root
        paragraph_sources: list[str] = []
        for child in root.children:
            if child.node_kind != "paragraph":
                continue
            paragraph_sources.append(self.node_to_source(child).rstrip("\n"))

        rendered = "\n\n".join(paragraph_sources)
        if root.metadata.get("trailing_newline", False):
            return rendered + "\n"
        return rendered

    def node_from_source(self, raw_block: str) -> TreeNode:
        if "\n" not in raw_block:
            return _line_node(1, raw_block)

        lines = raw_block.splitlines()
        if raw_block.endswith("\n") and lines and lines[-1] == "":
            lines = lines[:-1]
        if len(lines) == 1 and not _is_blank(lines[0]):
            return _line_node(1, lines[0])

        if any(_is_blank(line) for line in lines):
            paragraphs = _split_into_paragraphs(lines)
            first_paragraph_lines = paragraphs[0] if paragraphs else []
            return _paragraph_node(1, first_paragraph_lines)
        return _paragraph_node(1, lines)

    def node_to_source(self, node: TreeNode) -> str:
        if node.node_kind == "line":
            return f"{node.metadata.get('text', '')}\n"
        if node.node_kind == "paragraph":
            return "".join(self.node_to_source(child) for child in node.children)
        if node.node_kind == "root":
            paragraph_sources = [
                self.node_to_source(child).rstrip("\n")
                for child in node.children
                if child.node_kind == "paragraph"
            ]
            rendered = "\n\n".join(paragraph_sources)
            if node.metadata.get("trailing_newline", False):
                return rendered + "\n"
            return rendered
        raise ValueError(f"unknown node_kind: {node.node_kind!r}")

    def linters(self) -> list[Linter]:
        return []
