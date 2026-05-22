from __future__ import annotations

from ai_editor.formatters.tree import Tree
from ai_editor.formatters.xml.formatter import XmlFormatter


class TestXmlFormatter:
    def test_formatter_identity(self) -> None:
        formatter = XmlFormatter()
        assert formatter.formatter_name == "xml"
        assert sorted(formatter.registered_extensions) == [
            ".svg",
            ".xml",
            ".xsd",
            ".xsl",
            ".xslt",
        ]

    def test_parse_well_formed_xml(self) -> None:
        formatter = XmlFormatter()
        root = formatter.parse("<root><child>value</child></root>")

        assert root.node_kind == "root"
        assert len(root.children) == 1
        assert root.children[0].metadata["tag"] == "root"

    def test_render_round_trip_well_formed(self) -> None:
        formatter = XmlFormatter()
        parsed = formatter.parse("<root><child>value</child></root>")
        rendered = formatter.render(Tree(root=parsed))
        reparsed = formatter.parse(rendered)

        assert rendered.strip() != ""
        assert reparsed.children[0].metadata["tag"] == "root"

    def test_linters_non_empty(self) -> None:
        formatter = XmlFormatter()
        assert len(formatter.linters()) >= 1

    def test_registered_extensions(self) -> None:
        formatter = XmlFormatter()
        assert ".xml" in formatter.registered_extensions
        assert ".svg" in formatter.registered_extensions
