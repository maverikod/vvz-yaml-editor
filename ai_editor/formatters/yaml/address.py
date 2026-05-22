"""YAML address resolution for YamlFormatter document trees."""
from __future__ import annotations

import re
from typing import Any

PATH_NOT_FOUND = "PATH_NOT_FOUND"
PATH_NOT_UNIQUE = "PATH_NOT_UNIQUE"


class AddressError(Exception):
    """Raised when a YAML address cannot be resolved."""

    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


_SEGMENT_RE = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_]*)"
    r"(?:\[(\d+)\]|\[([^=\]]+)=([^\]]+)\])?$"
)


def resolve_address(document: Any, address_str: str) -> Any:
    """Resolve dotted/list address against ruamel-parsed document.

    Supports: key.subkey, items[0], commands[name=value].
    Raises AddressError with PATH_NOT_FOUND or PATH_NOT_UNIQUE.
    """
    if not address_str:
        raise AddressError(PATH_NOT_FOUND, "empty address")
    current = document
    for part in address_str.split("."):
        m = _SEGMENT_RE.match(part)
        if not m:
            raise AddressError(PATH_NOT_FOUND, f"bad segment {part!r}")
        key, index_s, field, value = m.group(1), m.group(2), m.group(3), m.group(4)
        if index_s is not None:
            if not isinstance(current, list):
                raise AddressError(PATH_NOT_FOUND, part)
            idx = int(index_s)
            if idx < 0 or idx >= len(current):
                raise AddressError(PATH_NOT_FOUND, part)
            current = current[idx]
        elif field is not None:
            if not isinstance(current, list):
                raise AddressError(PATH_NOT_FOUND, part)
            matches = [
                x for x in current if isinstance(x, dict) and str(x.get(field)) == value
            ]
            if not matches:
                raise AddressError(PATH_NOT_FOUND, part)
            if len(matches) > 1:
                raise AddressError(PATH_NOT_UNIQUE, part)
            current = matches[0]
        else:
            if not isinstance(current, dict) or key not in current:
                raise AddressError(PATH_NOT_FOUND, part)
            current = current[key]
    return current
