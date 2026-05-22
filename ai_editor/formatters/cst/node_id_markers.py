"""Helpers for removing persisted CST node-id marker blocks."""
from __future__ import annotations

import json
import re
import uuid
from typing import cast

PersistedNodeIds = dict[str, str]

MARKERS_BEGIN = "# cst-node-ids: begin"
MARKERS_END = "# cst-node-ids: end"
MARKERS_VERSION_V2 = "# cst-node-ids: version=2"
_V2_DATA_PREFIX = "# cst-node-ids: data="
_LEGACY_RE = re.compile(r"^# cst-node-id ([0-9.]+) [A-Za-z_][A-Za-z0-9_]* ([0-9a-fA-F-]{36})$")


def build_marker_path(path_indices: tuple[int, ...]) -> str:
    """Build dotted persisted marker path from DFS child indices."""
    return ".".join(str(i) for i in path_indices)


def _is_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4


def strip_persisted_node_ids(source: str) -> tuple[str, PersistedNodeIds]:
    """Strip trailing marker block and return (logical_source, path->uuid map)."""
    lines = source.splitlines()
    if not lines:
        return source, {}

    end = len(lines) - 1
    while end >= 0 and not lines[end].strip():
        end -= 1
    if end < 0 or lines[end].strip() != MARKERS_END:
        return source, {}

    begin = end
    while begin >= 0 and lines[begin].strip() != MARKERS_BEGIN:
        begin -= 1
    if begin < 0:
        return source, {}

    block = [line.strip() for line in lines[begin : end + 1]]
    parsed: PersistedNodeIds = {}
    if len(block) >= 3 and block[1] == MARKERS_VERSION_V2 and block[2].startswith(_V2_DATA_PREFIX):
        payload = block[2][len(_V2_DATA_PREFIX) :]
        try:
            raw = cast(dict[str, str], json.loads(payload))
        except json.JSONDecodeError:
            return source, {}
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, str) and _is_uuid4(value):
                parsed[key] = value
    else:
        for line in block[1:-1]:
            match = _LEGACY_RE.match(line)
            if match and _is_uuid4(match.group(2)):
                parsed[match.group(1)] = match.group(2)

    logical_lines = lines[:begin]
    while logical_lines and not logical_lines[-1].strip():
        logical_lines.pop()
    logical = "\n".join(logical_lines)
    if logical:
        logical += "\n"
    return logical, parsed
