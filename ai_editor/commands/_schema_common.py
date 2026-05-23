"""Shared JSON Schema property fragments for ai_editor MCP commands."""
from __future__ import annotations

from typing import Any

SESSION_KEY_PROP: dict[str, Any] = {
    "type": "string",
    "description": "UUID4 session identifier returned by session_connect.",
}

BUFFER_ID_PROP: dict[str, Any] = {
    "type": "string",
    "description": "Open buffer identifier from file_open, file_create, or buf_new.",
}

PROJECT_ID_PROP: dict[str, Any] = {
    "type": "string",
    "description": "Project UUID. Use list_projects on the CA server to discover valid values.",
}

FILE_PATH_PROP: dict[str, Any] = {
    "type": "string",
    "description": "Literal project-relative file path. Wildcards are not allowed.",
}

DRY_RUN_PROP: dict[str, Any] = {
    "type": "boolean",
    "default": False,
    "description": "Preview the operation without modifying session state, local buffer files, or remote files.",
}

FORMATTER_ENUM: list[str] = [
    "auto",
    "text",
    "yaml",
    "json",
    "cst",
    "markdown",
    "xml",
    "html",
]

FORMATTER_PROP: dict[str, Any] = {
    "type": "string",
    "default": "auto",
    "enum": FORMATTER_ENUM,
    "description": (
        "Formatter name. auto selects by extension: .yaml/.yml→yaml, .py→cst, .json→json, "
        ".md/.markdown→markdown, .xml/.xsd/.xsl/.xslt/.svg→xml, .html/.htm/.xhtml→html, else→text."
    ),
}

QUERY_KINDS: list[str] = [
    "contains_text",
    "regex",
    "field_equals",
    "node_type",
    "xpath",
    "stable_id",
]

QUERY_PROP: dict[str, Any] = {
    "type": "object",
    "description": "Formatter search query. kind selects the matcher; value/options depend on kind.",
    "properties": {
        "kind": {
            "type": "string",
            "enum": QUERY_KINDS,
            "description": "Search matcher kind.",
        },
        "value": {
            "description": "Primary match value (string or formatter-specific scalar).",
        },
        "field": {
            "type": "string",
            "description": "Field name for field_equals queries.",
        },
        "options": {
            "type": "object",
            "description": "Optional formatter-specific query options.",
        },
    },
    "required": ["kind"],
    "additionalProperties": False,
}

ADDRESS_PROP: dict[str, Any] = {
    "description": "Formatter-specific address (path, stable_id, xpath, etc.). Shape depends on buffer formatter.",
}

SOURCE_PROP: dict[str, Any] = {
    "type": "object",
    "description": "Source fragment to copy or cut.",
    "properties": {
        "buffer_id": BUFFER_ID_PROP,
        "address": ADDRESS_PROP,
    },
    "required": ["buffer_id", "address"],
    "additionalProperties": False,
}

TARGET_PROP: dict[str, Any] = {
    "type": "object",
    "description": "Target location for paste.",
    "properties": {
        "buffer_id": BUFFER_ID_PROP,
        "address": ADDRESS_PROP,
    },
    "required": ["buffer_id", "address"],
    "additionalProperties": False,
}

PASTE_MODES: list[str] = [
    "set",
    "replace_block",
    "append",
    "insert_before",
    "insert_after",
    "insert",
    "replace_range",
    "prepend",
    "replace",
    "delete",
]

MUTATION_OP_ITEM: dict[str, Any] = {
    "type": "object",
    "description": "Single formatter mutation operation.",
    "properties": {
        "op": {
            "type": "string",
            "description": "Mutation opcode (set, append, delete, etc.) defined by the buffer formatter.",
        },
        "address": ADDRESS_PROP,
        "value": {
            "description": "New value for set/append operations; omitted for delete.",
        },
    },
    "required": ["op", "address"],
    "additionalProperties": False,
}
