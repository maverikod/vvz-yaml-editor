"""YAML document mutations by structural address (not stable_id)."""
from __future__ import annotations

import copy
from typing import Any

from ai_editor.formatters.yaml.address import AddressError, PATH_NOT_FOUND, resolve_address


def _parent_and_key(document: Any, address: str) -> tuple[Any, str | int]:
    if not address or "." not in address:
        parent_path, leaf = "", address
    else:
        parts = address.rsplit(".", 1)
        parent_path, leaf = parts[0], parts[1]
    parent = document if not parent_path else resolve_address(document, parent_path)
    import re

    m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)(?:\[(\d+)\])?$", leaf)
    if not m:
        raise AddressError(PATH_NOT_FOUND, leaf)
    key, idx = m.group(1), m.group(2)
    if idx is not None:
        if not isinstance(parent, list):
            raise AddressError(PATH_NOT_FOUND, leaf)
        return parent, int(idx)
    return parent, key


def yaml_mutate_set(document: Any, address: str, value: Any) -> tuple[Any, list[str]]:
    """Set value at address; returns (document, changed_paths)."""
    doc = copy.deepcopy(document)
    if not address:
        return value, [""]
    parent, key = _parent_and_key(doc, address)
    if isinstance(parent, dict):
        parent[key] = value  # type: ignore[index]
    elif isinstance(parent, list):
        parent[key] = value  # type: ignore[index]
    else:
        raise AddressError(PATH_NOT_FOUND, address)
    return doc, [address]


def yaml_mutate_replace_block(document: Any, address: str, block: Any) -> tuple[Any, list[str]]:
    return yaml_mutate_set(document, address, block)


def yaml_mutate_append(
    document: Any, address: str, value: Any, *, dedupe: bool = False
) -> tuple[Any, list[str]]:
    doc = copy.deepcopy(document)
    if not address:
        target = doc
    else:
        target = resolve_address(doc, address)
    if isinstance(target, list):
        if dedupe and value in target:
            return doc, []
        target.append(value)
    elif isinstance(target, dict):
        if isinstance(value, dict) and len(value) == 1:
            k, v = next(iter(value.items()))
            if dedupe and k in target and target[k] == v:
                return doc, []
            target[k] = v
            return doc, [f"{address}.{k}" if address else str(k)]
        raise AddressError(PATH_NOT_FOUND, address)
    else:
        raise AddressError(PATH_NOT_FOUND, address)
    return doc, [address]


def yaml_mutate_delete(document: Any, address: str) -> tuple[Any, list[str]]:
    doc = copy.deepcopy(document)
    if not address:
        return {}, [""]
    parent, key = _parent_and_key(doc, address)
    if isinstance(parent, dict):
        del parent[key]  # type: ignore[arg-type]
    elif isinstance(parent, list):
        del parent[key]  # type: ignore[arg-type]
    else:
        raise AddressError(PATH_NOT_FOUND, address)
    return doc, [address]


def yaml_mutate_move(document: Any, source: str, target: str) -> tuple[Any, list[str]]:
    doc = copy.deepcopy(document)
    value = resolve_address(doc, source)
    doc, _ = yaml_mutate_delete(doc, source)
    doc, paths = yaml_mutate_set(doc, target, value)
    return doc, [source, target] + paths


def yaml_copy_fragment(document: Any, address: str) -> dict[str, Any]:
    return {"address": address, "value": resolve_address(document, address)}


def yaml_cut_fragment(document: Any, address: str) -> tuple[Any, dict[str, Any], list[str]]:
    frag = yaml_copy_fragment(document, address)
    doc, paths = yaml_mutate_delete(document, address)
    return doc, frag, paths


def yaml_paste_fragment(
    document: Any, address: str, fragment: dict[str, Any], *, mode: str = "append"
) -> tuple[Any, list[str]]:
    value = fragment.get("value")
    if mode == "set":
        return yaml_mutate_set(document, address, value)
    if mode == "replace_block":
        return yaml_mutate_replace_block(document, address, value)
    if mode == "append":
        return yaml_mutate_append(document, address, value)
    raise ValueError(f"unknown paste mode: {mode}")
