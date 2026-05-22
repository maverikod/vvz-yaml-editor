from __future__ import annotations

from ai_editor.formatters.text import TextFormatter
from ai_editor.formatters.tree import Tree


def test_formatter_identity() -> None:
    formatter = TextFormatter()
    assert formatter.formatter_name == "text"
    assert sorted(formatter.registered_extensions) == [
        ".cfg",
        ".ini",
        ".log",
        ".rst",
        ".toml",
        ".txt",
    ]


def test_linters_empty() -> None:
    formatter = TextFormatter()
    assert formatter.linters() == []


def test_parse_single_paragraph_multiple_lines() -> None:
    formatter = TextFormatter()
    root = formatter.parse("line1\nline2\n")
    assert len(root.children) == 1
    paragraph = root.children[0]
    assert paragraph.node_kind == "paragraph"
    assert len(paragraph.children) == 2
    assert paragraph.start_line == 1
    assert paragraph.end_line == 2


def test_parse_two_paragraphs() -> None:
    formatter = TextFormatter()
    root = formatter.parse("p1a\np1b\n\np2a\n")
    assert len(root.children) == 2
    first, second = root.children
    assert len(first.children) == 2
    assert len(second.children) == 1
    assert first.children[0].metadata["text"] == "p1a"
    assert second.children[0].metadata["text"] == "p2a"


def test_parse_no_internal_blanks_is_one_paragraph() -> None:
    formatter = TextFormatter()
    root = formatter.parse("a\nb\nc\n")
    assert len(root.children) == 1
    assert len(root.children[0].children) == 3


def test_render_roundtrip_structure() -> None:
    formatter = TextFormatter()
    raw = "hello\n\nworld\n"
    root = formatter.parse(raw)
    rendered = formatter.render(Tree(root=root))
    root2 = formatter.parse(rendered)
    assert len(root2.children) == len(root.children)
    assert [len(node.children) for node in root2.children] == [
        len(node.children) for node in root.children
    ]


def test_node_from_source_single_line() -> None:
    formatter = TextFormatter()
    node = formatter.node_from_source("only")
    assert node.node_kind == "line"
    assert node.metadata["text"] == "only"


def test_node_from_source_paragraph_block() -> None:
    formatter = TextFormatter()
    node = formatter.node_from_source("x\ny\n")
    assert node.node_kind == "paragraph"
    assert [line.metadata["text"] for line in node.children] == ["x", "y"]


def test_node_from_source_first_paragraph_only() -> None:
    formatter = TextFormatter()
    node = formatter.node_from_source("a\nb\n\nc\n")
    assert node.node_kind == "paragraph"
    assert [line.metadata["text"] for line in node.children] == ["a", "b"]


def test_node_to_source_line() -> None:
    formatter = TextFormatter()
    line = formatter.node_from_source("z\n")
    assert line.node_kind == "line"
    assert formatter.node_to_source(line) == "z\n"


def test_trailing_newline_flag() -> None:
    formatter = TextFormatter()
    root_with_newline = formatter.parse("a\n")
    assert root_with_newline.metadata.get("trailing_newline") is True
    assert formatter.render(Tree(root=root_with_newline)).endswith("\n")

    root_without_newline = formatter.parse("a")
    assert root_without_newline.metadata.get("trailing_newline") is False
    assert not formatter.render(Tree(root=root_without_newline)).endswith("\n")
