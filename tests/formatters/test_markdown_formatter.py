from __future__ import annotations

from ai_editor.formatters.markdown.formatter import MarkdownFormatter
from ai_editor.formatters.tree import Tree


class TestMarkdownFormatter:
    def test_formatter_identity(self) -> None:
        formatter = MarkdownFormatter()
        assert formatter.formatter_name == "markdown"
        assert sorted(formatter.registered_extensions) == [".markdown", ".md"]

    def test_linters_empty(self) -> None:
        formatter = MarkdownFormatter()
        assert formatter.linters() == []

    def test_parse_headings_and_paragraphs(self) -> None:
        formatter = MarkdownFormatter()
        root = formatter.parse("# Title\n\nBody paragraph.\n")

        assert root.node_kind == "root"
        assert len(root.children) >= 2
        assert root.children[0].node_kind == "heading"
        assert root.children[1].node_kind == "paragraph"

    def test_render_non_empty(self) -> None:
        formatter = MarkdownFormatter()
        root = formatter.parse("# H1\n\nParagraph text.\n")
        rendered = formatter.render(Tree(root=root))
        assert isinstance(rendered, str)
        assert rendered.strip() != ""

    def test_node_round_trip_basics(self) -> None:
        formatter = MarkdownFormatter()
        node = formatter.node_from_source("## Section")
        source = formatter.node_to_source(node)

        assert node.node_kind == "heading"
        assert "Section" in source
