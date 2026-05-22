"""Structural JSON address parsing and resolution for ai_editor JsonFormatter."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


class JsonAddressError(Exception):
    """Raised when a structural JSON address cannot be resolved."""

    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class AddressSegment:
    kind: Literal["key", "index", "filter"]
    value: str
    filter_field: str | None = None
    filter_value: str | None = None


_SEGMENT_RE = re.compile(
    r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)(?P<bracket>\[(?P<bracket_body>[^\]]*)\])?$"
)
_FILTER_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def parse_json_address(address: str) -> list[AddressSegment]:
    """Parse address string into segments."""
    text = address.strip()
    if not text:
        return []
    chunks = text.split(".")
    if any(not chunk for chunk in chunks):
        raise JsonAddressError("PATH_PARSE_FAILED", "Address contains empty segment")
    segments: list[AddressSegment] = []
    for chunk in chunks:
        match = _SEGMENT_RE.match(chunk)
        if not match:
            raise JsonAddressError("PATH_PARSE_FAILED", f"Invalid segment: {chunk}")
        key = match.group("key")
        segments.append(AddressSegment(kind="key", value=key))
        body = match.group("bracket_body")
        if body is None:
            continue
        body = body.strip()
        if body.isdigit():
            segments.append(AddressSegment(kind="index", value=body))
            continue
        if "=" not in body:
            raise JsonAddressError("PATH_PARSE_FAILED", f"Invalid bracket expression: [{body}]")
        field, value = body.split("=", 1)
        field = field.strip()
        value = value.strip()
        if not _FILTER_FIELD_RE.match(field) or "]" in value:
            raise JsonAddressError("PATH_PARSE_FAILED", f"Invalid filter expression: [{body}]")
        segments.append(
            AddressSegment(kind="filter", value=f"{field}={value}", filter_field=field, filter_value=value)
        )
    return segments


def normalize_json_address(address: str) -> str:
    """Return canonical form of a JSON structural address."""
    text = address.strip()
    if not text:
        return ""
    if text.startswith(".") or text.endswith("."):
        raise JsonAddressError("PATH_PARSE_FAILED", "Address cannot start or end with dot")
    segments = parse_json_address(text)
    parts: list[str] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        if seg.kind != "key":
            raise JsonAddressError("PATH_PARSE_FAILED", "Address must start with key segment")
        token = seg.value
        if i + 1 < len(segments) and segments[i + 1].kind in {"index", "filter"}:
            nxt = segments[i + 1]
            if nxt.kind == "index":
                token += f"[{nxt.value}]"
            else:
                token += f"[{nxt.filter_field}={nxt.filter_value}]"
            i += 1
        parts.append(token)
        i += 1
    return ".".join(parts)


def _resolve_segment(current: Any, segment: AddressSegment) -> Any:
    if segment.kind == "key":
        if not isinstance(current, dict):
            raise JsonAddressError("TARGET_TYPE_MISMATCH", "Key segment requires object container")
        if segment.value not in current:
            raise JsonAddressError("PATH_NOT_FOUND", f"Key not found: {segment.value}")
        return current[segment.value]
    if segment.kind == "index":
        if not isinstance(current, list):
            raise JsonAddressError("TARGET_TYPE_MISMATCH", "Index segment requires list container")
        index = int(segment.value)
        if index < 0 or index >= len(current):
            raise JsonAddressError("PATH_NOT_FOUND", f"Index out of range: {index}")
        return current[index]
    if not isinstance(current, list):
        raise JsonAddressError("TARGET_TYPE_MISMATCH", "Filter segment requires list container")
    matches = [
        item
        for item in current
        if isinstance(item, dict)
        and segment.filter_field in item
        and str(item[segment.filter_field]) == str(segment.filter_value)
    ]
    if not matches:
        raise JsonAddressError("PATH_NOT_FOUND", f"Filter not found: {segment.filter_field}={segment.filter_value}")
    if len(matches) > 1:
        raise JsonAddressError(
            "PATH_NOT_UNIQUE",
            f"Filter matched multiple items: {segment.filter_field}={segment.filter_value}",
        )
    return matches[0]


def resolve_json_address(document: Any, address: str) -> Any:
    """Resolve a structural address against a parsed JSON value."""
    norm = normalize_json_address(address)
    if norm == "":
        return document
    current: Any = document
    for segment in parse_json_address(norm):
        current = _resolve_segment(current, segment)
    return current


def resolve_json_parent(document: Any, address: str) -> tuple[Any, str | int]:
    """Resolve parent container and final key/index for a structural address."""
    norm = normalize_json_address(address)
    if norm == "":
        raise JsonAddressError("PATH_PARSE_FAILED", "Empty address has no parent")
    segments = parse_json_address(norm)
    if len(segments) < 1:
        raise JsonAddressError("PATH_PARSE_FAILED", "Address has no segments")
    parent = document
    for segment in segments[:-1]:
        parent = _resolve_segment(parent, segment)
    last = segments[-1]
    if last.kind == "key":
        return parent, last.value
    if last.kind == "index":
        return parent, int(last.value)
    if not isinstance(parent, list):
        raise JsonAddressError("TARGET_TYPE_MISMATCH", "Filter parent must be list")
    matches = [
        idx
        for idx, item in enumerate(parent)
        if isinstance(item, dict)
        and last.filter_field in item
        and str(item[last.filter_field]) == str(last.filter_value)
    ]
    if not matches:
        raise JsonAddressError("PATH_NOT_FOUND", f"Filter not found: {last.filter_field}={last.filter_value}")
    if len(matches) > 1:
        raise JsonAddressError(
            "PATH_NOT_UNIQUE",
            f"Filter matched multiple items: {last.filter_field}={last.filter_value}",
        )
    return parent, matches[0]
