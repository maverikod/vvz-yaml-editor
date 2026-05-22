"""Document-level JSON mutations by structural address for ai_editor JsonFormatter."""
from __future__ import annotations

import copy
import json
from typing import Any

from ai_editor.formatters.json.address import (
    JsonAddressError,
    normalize_json_address,
    resolve_json_address,
    resolve_json_parent,
)

_CLIPBOARD: Any | None = None


def _deepcopy_document(document: Any) -> Any:
    return copy.deepcopy(document)


def _parse_json_value(content: Any) -> Any:
    """Parse JSON string content or return native value as-is."""
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON content: {exc}") from exc
    return content


def json_mutate_set(document: Any, address: str, value: Any) -> tuple[Any, list[str]]:
    doc = _deepcopy_document(document)
    norm = normalize_json_address(address)
    parent, key = resolve_json_parent(doc, norm)
    parent[key] = _deepcopy_document(value)
    return doc, [norm]


def json_mutate_replace_block(document: Any, address: str, content: Any) -> tuple[Any, list[str]]:
    doc = _deepcopy_document(document)
    norm = normalize_json_address(address)
    value = _parse_json_value(content)
    if norm == "":
        return _deepcopy_document(value), [""]
    parent, key = resolve_json_parent(doc, norm)
    parent[key] = _deepcopy_document(value)
    return doc, [norm]


def json_mutate_append(document: Any, address: str, value: Any, *, dedupe: bool = False) -> tuple[Any, list[str]]:
    doc = _deepcopy_document(document)
    norm = normalize_json_address(address)
    target = resolve_json_address(doc, norm)
    payload = _deepcopy_document(value)
    if isinstance(target, list):
        if not (dedupe and any(item == payload for item in target)):
            target.append(payload)
    elif isinstance(target, dict):
        if not isinstance(payload, dict):
            raise JsonAddressError("TARGET_TYPE_MISMATCH", "Appending into object requires dict payload")
        target.update(payload)
    else:
        raise JsonAddressError("TARGET_TYPE_MISMATCH", "Append target must be list or dict")
    return doc, [norm]


def json_mutate_delete(document: Any, address: str) -> tuple[Any, list[str]]:
    doc = _deepcopy_document(document)
    norm = normalize_json_address(address)
    parent, key = resolve_json_parent(doc, norm)
    if isinstance(parent, dict):
        if key not in parent:
            raise JsonAddressError("PATH_NOT_FOUND", f"Key not found: {key}")
        del parent[key]
    elif isinstance(parent, list):
        index = int(key)
        if index < 0 or index >= len(parent):
            raise JsonAddressError("PATH_NOT_FOUND", f"Index out of range: {index}")
        parent.pop(index)
    else:
        raise JsonAddressError("TARGET_TYPE_MISMATCH", "Delete target parent must be list or dict")
    return doc, [norm]


def _insert_into_target(target: Any, value: Any, position: int | str) -> None:
    if isinstance(target, list):
        if position == "first":
            target.insert(0, value)
        elif position == "last":
            target.append(value)
        else:
            target.insert(int(position), value)
        return
    if isinstance(target, dict):
        if not isinstance(value, dict):
            raise JsonAddressError("TARGET_TYPE_MISMATCH", "Dict target accepts only dict value")
        target.update(value)
        return
    raise JsonAddressError("TARGET_TYPE_MISMATCH", "Move target must be list or dict")


def json_mutate_move(
    document: Any, source_address: str, target_address: str, position: int | str = "last"
) -> tuple[Any, list[str]]:
    doc = _deepcopy_document(document)
    src_norm = normalize_json_address(source_address)
    dst_norm = normalize_json_address(target_address)
    if dst_norm and src_norm and (dst_norm == src_norm or dst_norm.startswith(src_norm + ".")):
        raise JsonAddressError("PATH_PARSE_FAILED", "Cannot move node into its own subtree")
    value = _deepcopy_document(resolve_json_address(doc, src_norm))
    doc, _ = json_mutate_delete(doc, src_norm)
    target = resolve_json_address(doc, dst_norm)
    _insert_into_target(target, value, position)
    return doc, sorted({src_norm, dst_norm})


def json_copy_fragment(document: Any, address: str) -> tuple[Any, list[str]]:
    global _CLIPBOARD
    norm = normalize_json_address(address)
    _CLIPBOARD = _deepcopy_document(resolve_json_address(document, norm))
    return document, []


def json_cut_fragment(document: Any, address: str) -> tuple[Any, list[str]]:
    global _CLIPBOARD
    norm = normalize_json_address(address)
    _CLIPBOARD = _deepcopy_document(resolve_json_address(document, norm))
    return json_mutate_delete(document, norm)


def json_paste_fragment(document: Any, target_address: str, position: int | str = "last") -> tuple[Any, list[str]]:
    if _CLIPBOARD is None:
        raise JsonAddressError("CLIPBOARD_EMPTY", "Clipboard is empty")
    doc = _deepcopy_document(document)
    norm = normalize_json_address(target_address)
    target = resolve_json_address(doc, norm)
    _insert_into_target(target, _deepcopy_document(_CLIPBOARD), position)
    return doc, [norm]
