"""Conversion rules for cross-formatter clipboard paste in ai_editor."""
from __future__ import annotations

import html as html_lib
import json
from typing import Any

from ai_editor.formatters.conversion.registry import ConversionRegistry, ConversionRule


def _text_to_markdown(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    return "\n\n" + str(fragment) + "\n\n"

def _text_to_yaml(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    return str(fragment)

def _text_to_json(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    return json.dumps(str(fragment))


def _text_to_xml(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    escaped = html_lib.escape(str(fragment))
    return f"<text>{escaped}</text>"


def _text_to_html(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    return f"<p>{html_lib.escape(str(fragment))}</p>"


def _markdown_to_text(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    import mistune

    md = mistune.create_markdown(renderer="ast")
    tokens = md(str(fragment))
    return " ".join(tok.get("raw", "") for tok in tokens if isinstance(tok, dict))


def _markdown_to_yaml(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from io import StringIO

    import mistune
    from ruamel.yaml import YAML

    md = mistune.create_markdown(renderer="ast")
    tokens = md(str(fragment))
    y = YAML()
    buf = StringIO()
    y.dump(
        [
            {"type": tok.get("type"), "content": tok.get("raw", "")}
            for tok in tokens
            if isinstance(tok, dict)
        ],
        buf,
    )
    return buf.getvalue()


def _markdown_to_xml(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    import mistune
    from lxml import etree

    html_str = mistune.create_markdown()(str(fragment))
    try:
        return etree.tostring(etree.fromstring(f"<doc>{html_str}</doc>".encode()), encoding="unicode")
    except Exception:
        return f"<doc>{html_str}</doc>"


def _markdown_to_html(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    import mistune

    return mistune.create_markdown()(str(fragment))


def _yaml_to_text(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from io import StringIO

    from ruamel.yaml import YAML

    y = YAML()
    buf = StringIO()
    y.dump(fragment, buf)
    return buf.getvalue()


def _yaml_to_json(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from io import StringIO

    from ruamel.yaml import YAML

    y = YAML()
    buf = StringIO()
    y.dump(fragment, buf)
    return json.dumps(json.loads(buf.getvalue()), indent=2)


def _json_to_text(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    return json.dumps(fragment, indent=2)


def _json_to_yaml(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from io import StringIO

    from ruamel.yaml import YAML

    y = YAML()
    buf = StringIO()
    y.dump(fragment, buf)
    return buf.getvalue()


def _json_to_markdown(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    return f"```json\n{json.dumps(fragment, indent=2)}\n```"


def _xml_to_text(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from lxml import etree

    return etree.tostring(fragment, encoding="unicode") if hasattr(fragment, "tag") else str(fragment)


def _xml_to_yaml(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from io import StringIO

    from lxml import etree
    from ruamel.yaml import YAML

    data = {
        "tag": fragment.tag,
        "attrs": dict(fragment.attrib),
        "text": fragment.text or "",
        "children": [c.tag for c in fragment],
    }
    y = YAML()
    buf = StringIO()
    y.dump(data, buf)
    return buf.getvalue()


def _xml_to_html(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from lxml import etree

    return etree.tostring(fragment, encoding="unicode")


def _html_to_text(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from bs4 import BeautifulSoup

    soup = fragment if hasattr(fragment, "get_text") else BeautifulSoup(str(fragment), "lxml")
    return soup.get_text(separator="\n")


def _html_to_markdown(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    import html2text

    h = html2text.HTML2Text()
    h.ignore_links = False
    return h.handle(str(fragment))


def _html_to_xml(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    from lxml import etree

    return etree.fromstring(str(fragment).encode("utf-8"))


def _cst_to_text(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    return fragment.module.code if hasattr(fragment, "module") else str(fragment)


def _cst_to_cst(fragment: Any, src_inst: Any, tgt_inst: Any) -> Any:
    return fragment


def register_all_rules(registry: ConversionRegistry) -> None:
    registry.register(ConversionRule("text", "markdown", _text_to_markdown, False, "text->markdown"))
    registry.register(ConversionRule("text", "yaml", _text_to_yaml, True, "text->yaml"))
    registry.register(ConversionRule("text", "json", _text_to_json, False, "text->json"))
    registry.register(ConversionRule("text", "xml", _text_to_xml, True, "text->xml"))
    registry.register(ConversionRule("text", "html", _text_to_html, False, "text->html"))
    registry.register(ConversionRule("markdown", "text", _markdown_to_text, True, "markdown->text"))
    registry.register(ConversionRule("markdown", "yaml", _markdown_to_yaml, True, "markdown->yaml"))
    registry.register(ConversionRule("markdown", "xml", _markdown_to_xml, True, "markdown->xml"))
    registry.register(ConversionRule("markdown", "html", _markdown_to_html, True, "markdown->html"))
    registry.register(ConversionRule("yaml", "text", _yaml_to_text, False, "yaml->text"))
    registry.register(ConversionRule("yaml", "json", _yaml_to_json, True, "yaml->json"))
    registry.register(ConversionRule("json", "text", _json_to_text, False, "json->text"))
    registry.register(ConversionRule("json", "yaml", _json_to_yaml, False, "json->yaml"))
    registry.register(ConversionRule("json", "markdown", _json_to_markdown, True, "json->markdown"))
    registry.register(ConversionRule("xml", "text", _xml_to_text, False, "xml->text"))
    registry.register(ConversionRule("xml", "yaml", _xml_to_yaml, True, "xml->yaml"))
    registry.register(ConversionRule("xml", "html", _xml_to_html, True, "xml->html"))
    registry.register(ConversionRule("html", "text", _html_to_text, True, "html->text"))
    registry.register(ConversionRule("html", "markdown", _html_to_markdown, True, "html->markdown"))
    registry.register(ConversionRule("html", "xml", _html_to_xml, True, "html->xml"))
    registry.register(ConversionRule("cst", "text", _cst_to_text, False, "cst->text"))
    registry.register(ConversionRule("cst", "cst", _cst_to_cst, False, "cst->cst"))
