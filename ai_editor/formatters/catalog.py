"""Formatter command catalog datatypes (C-022)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FormatterCommandMetadata:
    """Metadata for one formatter command exposed via list_commands.

    Attributes:
        name: Command identifier (e.g. 'insert', 'yaml_validate').
        description: Human-readable command summary.
        input_schema: OpenAPI-compatible JSON Schema for command input.
        output_schema: OpenAPI-compatible JSON Schema for command output.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class FormatterCommandCatalog:
    """Structured catalogue of base and format-specific commands (C-022).

    Attributes:
        formatter_name: Formatter identifier (e.g. 'yaml', 'text').
        formatter_version: Semver or simple version string for the catalog snapshot.
        standard_commands: Commands inherited from AbstractFormatter base.
        specific_commands: Commands added by a concrete formatter subclass.
        openapi_schemas: Shared or referenced OpenAPI schema definitions.
    """

    formatter_name: str
    formatter_version: str = "1.0"
    standard_commands: list[FormatterCommandMetadata] = field(default_factory=list)
    specific_commands: list[FormatterCommandMetadata] = field(default_factory=list)
    openapi_schemas: dict[str, Any] = field(default_factory=dict)
