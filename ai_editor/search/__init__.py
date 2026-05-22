"""Universal search layer."""

from ai_editor.search.base import AbstractSearch, SearchMatch
from ai_editor.search.query import KNOWN_QUERY_KINDS, validate_query
from ai_editor.search.search import Search

__all__ = [
    "AbstractSearch",
    "SearchMatch",
    "Search",
    "KNOWN_QUERY_KINDS",
    "validate_query",
]
