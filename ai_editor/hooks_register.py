"""Register ai_editor formatters and commands with mcp_proxy_adapter."""
from __future__ import annotations

from typing import Any

from mcp_proxy_adapter.commands.hooks import register_custom_commands_hook

from ai_editor.editor_core.formatter_registry import FormatterRegistry

formatter_registry = FormatterRegistry.get_instance()


def _register_formatters() -> None:
    """Register formatters: text, yaml, json, cst, markdown, xml, html + conversion rules."""
    from ai_editor.formatters.cst.formatter import CSTFormatter
    from ai_editor.formatters.html.formatter import HtmlFormatter
    from ai_editor.formatters.json import JsonFormatter
    from ai_editor.formatters.markdown.formatter import MarkdownFormatter
    from ai_editor.formatters.text import TextFormatter
    from ai_editor.formatters.xml.formatter import XmlFormatter
    from ai_editor.formatters.yaml import YamlFormatter
    from ai_editor.formatters.conversion.registry import conversion_registry
    from ai_editor.formatters.conversion.rules import register_all_rules

    formatter_registry.register(
        "text",
        [".txt", ".log", ".rst", ".ini", ".cfg", ".toml"],
        TextFormatter,
    )
    formatter_registry.register("yaml", [".yaml", ".yml"], YamlFormatter)
    formatter_registry.register("json", [".json"], JsonFormatter)
    formatter_registry.register("cst", [".py"], CSTFormatter)
    formatter_registry.register("markdown", [".md", ".markdown"], MarkdownFormatter)
    formatter_registry.register("xml", [".xml", ".xsd", ".xsl", ".xslt", ".svg"], XmlFormatter)
    formatter_registry.register("html", [".html", ".htm", ".xhtml"], HtmlFormatter)
    register_all_rules(conversion_registry)


_register_formatters()


def _register(registry: Any) -> None:
    """Register EditorCommand subclasses."""
    from ai_editor.commands.session_connect_command import SessionConnectCommand
    from ai_editor.commands.session_reconnect_command import SessionReconnectCommand
    from ai_editor.commands.session_close_command import SessionCloseCommand
    from ai_editor.commands.session_status_command import SessionStatusCommand
    from ai_editor.commands.file_open_command import FileOpenCommand
    from ai_editor.commands.file_close_command import FileCloseCommand
    from ai_editor.commands.file_get_command import FileGetCommand
    from ai_editor.commands.file_send_command import FileSendCommand
    from ai_editor.commands.file_create_command import FileCreateCommand
    from ai_editor.commands.buf_undo_command import BufUndoCommand
    from ai_editor.commands.buf_redo_command import BufRedoCommand
    from ai_editor.commands.buf_copy_command import BufCopyCommand
    from ai_editor.commands.buf_cut_command import BufCutCommand
    from ai_editor.commands.buf_paste_command import BufPasteCommand
    from ai_editor.commands.search_find_command import SearchFindCommand
    from ai_editor.commands.search_find_one_command import SearchFindOneCommand
    from ai_editor.commands.search_list_units_command import SearchListUnitsCommand
    from ai_editor.commands.buf_validate_command import BufValidateCommand
    from ai_editor.commands.validate_file_command import ValidateFileCommand
    from ai_editor.commands.formatter_commands_command import FormatterCommandsCommand
    from ai_editor.commands.buf_new_command import BufNewCommand
    from ai_editor.commands.buf_save_as_command import BufSaveAsCommand
    from ai_editor.commands.buf_reload_command import BufReloadCommand
    from ai_editor.commands.buf_get_state_command import BufGetStateCommand
    from ai_editor.commands.buf_write_all_command import BufWriteAllCommand
    from ai_editor.commands.buf_mutate_batch_command import BufMutateBatchCommand

    registry.register(SessionConnectCommand, "custom")
    registry.register(SessionReconnectCommand, "custom")
    registry.register(SessionCloseCommand, "custom")
    registry.register(SessionStatusCommand, "custom")
    registry.register(FileOpenCommand, "custom")
    registry.register(FileCloseCommand, "custom")
    registry.register(FileGetCommand, "custom")
    registry.register(FileSendCommand, "custom")
    registry.register(FileCreateCommand, "custom")
    registry.register(BufUndoCommand, "custom")
    registry.register(BufRedoCommand, "custom")
    registry.register(BufCopyCommand, "custom")
    registry.register(BufCutCommand, "custom")
    registry.register(BufPasteCommand, "custom")
    registry.register(SearchFindCommand, "custom")
    registry.register(SearchFindOneCommand, "custom")
    registry.register(SearchListUnitsCommand, "custom")
    registry.register(BufValidateCommand, "custom")
    registry.register(ValidateFileCommand, "custom")
    registry.register(FormatterCommandsCommand, "custom")
    registry.register(BufNewCommand, "custom")
    registry.register(BufSaveAsCommand, "custom")
    registry.register(BufReloadCommand, "custom")
    registry.register(BufGetStateCommand, "custom")
    registry.register(BufWriteAllCommand, "custom")
    registry.register(BufMutateBatchCommand, "custom")


register_custom_commands_hook(_register)


def register_ai_editor_commands(registry: Any) -> None:
    """Public hook entry called from main.py."""
    _register(registry)
