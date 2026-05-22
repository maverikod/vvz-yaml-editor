"""AbstractSearch contract and SearchMatch result type."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchMatch:
    """Single search result with a tree stable_id address usable in BufferAddress.

    Attributes:
        buffer_id: Buffer containing the match.
        formatter: Formatter name (e.g. text, yaml, cst).
        address: Node stable_id (UUID str) for all formatters.
        preview: Short human-readable preview of the matched unit.
        unit_kind: Format-defined unit kind string.
        metadata: Additional match metadata from the formatter.
    """

    buffer_id: str
    formatter: str
    address: Any
    preview: str
    unit_kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AbstractSearch(ABC):
    """Search interface over a formatter in-memory Tree.

    Does not open or write files. session_key is diagnostic only.
    Delegates unit iteration and matching to formatter base hooks.
    """

    @abstractmethod
    def find(
        self,
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> list[SearchMatch]:
        """Return all units matching query within optional scope."""

    @abstractmethod
    def find_one(
        self,
        session_key: str,
        buffer_id: str,
        query: dict[str, Any],
        scope: str | None = None,
    ) -> SearchMatch | dict[str, Any]:
        """Return exactly one match or an error dict (never raises)."""

    @abstractmethod
    def list_units(
        self,
        session_key: str,
        buffer_id: str,
        scope: str | None = None,
    ) -> list[SearchMatch]:
        """List all navigable units in scope without applying a query filter."""
