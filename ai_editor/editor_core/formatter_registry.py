"""FormatterRegistry — singleton mapping extensions and names to formatter classes."""
from __future__ import annotations

from typing import Any, Type


class FormatterRegistry:
    """Singleton registry mapping file extensions and formatter names to classes.

    Invariant: one extension maps to exactly one formatter. Registering an
    extension that already exists overwrites the previous mapping.
    """

    _instance: FormatterRegistry | None = None

    def __init__(self) -> None:
        """Initialise an empty registry. Use get_instance() for the singleton."""
        self._by_name: dict[str, type] = {}
        self._by_extension: dict[str, type] = {}

    @classmethod
    def get_instance(cls) -> FormatterRegistry:
        """Return the global singleton FormatterRegistry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing only)."""
        cls._instance = None

    def register(
        self,
        formatter_name: str,
        extensions: list[str],
        formatter_class: type,
    ) -> None:
        """Register a formatter class under a name and a list of file extensions.

        Invariant: one extension maps to exactly one formatter. Overwrites any
        prior mapping for the same extension.

        Args:
            formatter_name: Unique formatter identifier (e.g. 'yaml', 'text').
            extensions: File extensions this formatter handles (e.g. ['.yaml', '.yml']).
            formatter_class: The formatter class to register.
        """
        self._by_name[formatter_name] = formatter_class
        for ext in extensions:
            self._by_extension[ext.lower()] = formatter_class

    def get_by_extension(self, ext: str) -> type | None:
        """Return the formatter class for a file extension, or None.

        Args:
            ext: File extension including leading dot (e.g. '.yaml').

        Returns:
            Formatter class or None if no formatter handles this extension.
        """
        return self._by_extension.get(ext.lower())

    def get_by_name(self, name: str) -> type | None:
        """Return the formatter class for a formatter name, or None.

        Args:
            name: Formatter name (e.g. 'yaml', 'text').

        Returns:
            Formatter class or None if the name is not registered.
        """
        return self._by_name.get(name)

    def list_formatters(self) -> list[str]:
        """Return all registered formatter names in registration order.

        Returns:
            List of formatter name strings.
        """
        return list(self._by_name.keys())
