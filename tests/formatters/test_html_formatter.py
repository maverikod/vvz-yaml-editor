from __future__ import annotations

from ai_editor.formatters.html.formatter import HtmlFormatter
from ai_editor.formatters.tree import Tree


class TestHtmlFormatter:
    def test_formatter_identity(self) -> None:
        formatter = HtmlFormatter()
        assert formatter.formatter_name == "html"
        assert sorted(formatter.registered_extensions) == [".htm", ".html", ".xhtml"]

    def test_parse_sample_html(self) -> None:
        formatter = HtmlFormatter()
        root = formatter.parse("<html><body><h1>Hello</h1><p>World</p></body></html>")

        assert root.node_kind == "root"
        assert len(root.children) >= 1
        assert root.children[0].node_kind in {"h1", "p", "div"}

    def test_render_non_empty(self) -> None:
        formatter = HtmlFormatter()
        root = formatter.parse("<html><body><p>hello</p></body></html>\n")
        rendered = formatter.render(Tree(root=root))

        assert isinstance(rendered, str)
        assert rendered.strip() != ""

    def test_linters_non_empty(self) -> None:
        formatter = HtmlFormatter()
        assert len(formatter.linters()) >= 1

    def test_registered_extensions(self) -> None:
        formatter = HtmlFormatter()
        assert ".html" in formatter.registered_extensions
        assert ".xhtml" in formatter.registered_extensions
