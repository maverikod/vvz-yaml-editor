"""JSON Schema for validate_file command parameters."""
from __future__ import annotations

from typing import Any


def get_validate_file_schema() -> dict[str, Any]:
    """Return machine-readable input schema for validate_file."""
    return {
        "type": "object",
        "properties": {
            "session_key": {"type": "string", "description": "UUID4 session identifier."},
            "file_path": {"type": "string"},
            "buffer_id": {"type": "string", "description": "Open buffer identifier."},
            "project_id": {"type": "string"},
            "formatter": {
                "type": "string",
                "default": "auto",
                "enum": ["auto", "text", "yaml", "json", "cst", "markdown", "xml", "html"],
                "description": "Formatter name. auto detects by extension: .yaml/.yml->yaml, .py->cst, .json->json, .md/.markdown->markdown, .xml/.xsd/.xsl/.xslt/.svg->xml, .html/.htm/.xhtml->html, else->text.",
            },
            "schema": {"type": "object"},
        },
        "required": ["session_key"],
        "additionalProperties": False,
    }
