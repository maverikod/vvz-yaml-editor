"""MarkdownFormatter: mistune AST-based converter hooks for ai_editor."""
from __future__ import annotations

from typing import Any

import mistune

from ai_editor.formatters.base import AbstractFormatter, Linter
from ai_editor.formatters.markdown.md_node import MdNode
from ai_editor.formatters.tree import Tree, TreeNode


def _tok_attrs(tok: dict[str, Any]) -> dict[str, Any]:
    attrs = tok.get("attrs")
    return attrs if isinstance(attrs, dict) else {}


def _tok_pos(tok: dict[str, Any]) -> tuple[int, int] | None:
    pos = tok.get("position")
    if (
        isinstance(pos, tuple)
        and len(pos) == 2
        and all(isinstance(v, int) for v in pos)
    ):
        return pos
    return None


def _join_raw(children: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        raw = child.get("raw")
        if isinstance(raw, str):
            parts.append(raw)
    return "".join(parts)


def _token_to_mdnode(tok: dict[str, Any]) -> MdNode:
    t = str(tok.get("type", "unknown"))
    attrs = _tok_attrs(tok)
    children_raw = tok.get("children")
    children_tokens = (
        children_raw if isinstance(children_raw, list) else []
    )
    child_nodes = [
        _token_to_mdnode(child)
        for child in children_tokens
        if isinstance(child, dict)
    ]

    if t == "heading":
        level_raw = attrs.get("level")
        level = level_raw if isinstance(level_raw, int) else None
        return MdNode(
            node_type="heading",
            content=_join_raw(children_tokens),
            level=level,
            attrs=dict(attrs),
            source_pos=_tok_pos(tok),
            children=child_nodes,
        )
    if t == "paragraph":
        return MdNode(
            node_type="paragraph",
            content=_join_raw(children_tokens),
            children=child_nodes,
        )
    if t in {"code", "block_code"}:
        raw = tok.get("raw")
        code_text = raw if isinstance(raw, str) else ""
        info = attrs.get("info")
        return MdNode(
            node_type="code_block",
            content=code_text,
            attrs={"info": info, "_content": code_text},
        )
    if t == "list":
        return MdNode(node_type="list", children=child_nodes)
    if t == "list_item":
        return MdNode(
            node_type="list_item",
            content=_join_raw(children_tokens),
            children=child_nodes,
        )
    if t == "block_quote":
        return MdNode(node_type="blockquote", children=child_nodes)
    if t == "thematic_break":
        return MdNode(node_type="thematic_break", content="---")
    if t == "block_html":
        raw = tok.get("raw")
        return MdNode(
            node_type="html_block",
            attrs={"_content": raw if isinstance(raw, str) else ""},
        )
    if t == "table":
        return MdNode(node_type="table", children=child_nodes)
    if t == "image":
        return MdNode(node_type="image", attrs=dict(attrs))
    if t == "link":
        return MdNode(
            node_type="link",
            content=_join_raw(children_tokens),
            attrs=dict(attrs),
            children=child_nodes,
        )
    return MdNode(node_type=t, content=str(tok))


def _node_display(n: MdNode) -> str:
    if n.node_type == "heading":
        level = n.level if isinstance(n.level, int) and n.level > 0 else 1
        return f"{'#' * level} {n.content}".strip()[:80]
    if n.node_type == "paragraph":
        if len(n.content) > 60:
            return f"{n.content[:60]} # {len(n.content)} chars"
        return n.content
    if n.node_type == "code_block":
        info = n.attrs.get("info", "")
        info_text = str(info) if info is not None else ""
        return f"```{info_text}\n{n.content[:40]}"
    if n.node_type == "list":
        return f"- [{len(n.children)} items]"
    if n.node_type == "table":
        return "| table"
    if n.node_type == "image":
        alt = str(n.attrs.get("alt", ""))
        src = str(n.attrs.get("url", n.attrs.get("src", "")))
        return f"![{alt}]({src})"
    if n.node_type == "link":
        href = str(n.attrs.get("url", ""))
        return f"[{n.content[:40]}]({href})"
    if n.node_type == "thematic_break":
        return "---"
    return f"{n.node_type}: {n.content[:60]}"


def _mdnode_to_treenode(n: MdNode) -> TreeNode:
    start_line = n.source_pos[0] if n.source_pos else 0
    end_line = n.source_pos[1] if n.source_pos else 0
    metadata = {
        "level": n.level,
        "md_attrs": dict(n.attrs),
        "md_content": n.content,
    }
    return TreeNode(
        stable_id="",
        node_kind=n.node_type,
        start_line=start_line,
        end_line=end_line,
        display_text=_node_display(n),
        metadata=metadata,
        children=[_mdnode_to_treenode(c) for c in n.children],
    )


class MarkdownFormatter(AbstractFormatter):
    formatter_name = "markdown"
    registered_extensions = [".md", ".markdown"]

    def parse(self, raw_content: str) -> TreeNode:
        md = mistune.create_markdown(renderer="ast")
        tokens = md(raw_content)
        if not isinstance(tokens, list):
            tokens = []
        nodes = [
            _token_to_mdnode(t)
            for t in tokens
            if isinstance(t, dict) and t.get("type") != "blank_line"
        ]
        line_count = raw_content.count("\n") + (
            1 if raw_content and not raw_content.endswith("\n") else 0
        )
        return TreeNode(
            stable_id="",
            node_kind="root",
            start_line=1,
            end_line=max(1, line_count),
            display_text="(markdown document)",
            metadata={"trailing_newline": raw_content.endswith("\n")},
            children=[_mdnode_to_treenode(n) for n in nodes],
        )

    def render(self, tree: Tree) -> str:
        parts = [self.node_to_source(c) for c in tree.root.children]
        result = "\n\n".join(parts)
        if tree.root.metadata.get("trailing_newline", True):
            result += "\n"
        return result

    def node_from_source(self, raw_block: str) -> TreeNode:
        md = mistune.create_markdown(renderer="ast")
        tokens = md(raw_block.strip())
        if not isinstance(tokens, list) or not tokens:
            return TreeNode(
                stable_id="",
                node_kind="paragraph",
                start_line=1,
                end_line=1,
                display_text="",
                metadata={"level": None, "md_attrs": {}, "md_content": ""},
                children=[],
            )
        first = tokens[0]
        if not isinstance(first, dict):
            return TreeNode(
                stable_id="",
                node_kind="paragraph",
                start_line=1,
                end_line=1,
                display_text="",
                metadata={"level": None, "md_attrs": {}, "md_content": ""},
                children=[],
            )
        return _mdnode_to_treenode(_token_to_mdnode(first))

    def node_to_source(self, node: TreeNode) -> str:
        attrs = node.metadata.get("md_attrs", {})
        md_attrs = attrs if isinstance(attrs, dict) else {}
        content = str(node.metadata.get("md_content", ""))

        if node.node_kind == "heading":
            level = node.metadata.get("level")
            heading_level = level if isinstance(level, int) and level > 0 else 1
            text = node.display_text.lstrip("# ").strip()
            return f"{'#' * heading_level} {text}".rstrip()
        if node.node_kind == "paragraph":
            return node.display_text.split(" # ", 1)[0]
        if node.node_kind == "code_block":
            lang = str(md_attrs.get("info", ""))
            code_content = content or str(md_attrs.get("_content", ""))
            return f"```{lang}\n{code_content}\n```"
        if node.node_kind == "thematic_break":
            return "---"
        if node.node_kind == "html_block":
            return str(md_attrs.get("_content", ""))
        if node.node_kind == "list":
            lines = [f"- {self.node_to_source(c)}" for c in node.children]
            return "\n".join(lines)
        if node.node_kind == "list_item":
            return node.display_text
        if node.node_kind == "blockquote":
            child_source = "\n".join(self.node_to_source(c) for c in node.children)
            if not child_source:
                return "> "
            return "\n".join(f"> {line}" for line in child_source.splitlines())
        if node.node_kind == "image":
            alt = str(md_attrs.get("alt", ""))
            src = str(md_attrs.get("url", md_attrs.get("src", "")))
            return f"![{alt}]({src})"
        if node.node_kind == "link":
            href = str(md_attrs.get("url", ""))
            text = content or node.display_text
            return f"[{text}]({href})"
        return node.display_text

    def linters(self) -> list[Linter]:
        return []
