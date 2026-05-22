"""YAML fragment clipboard serialization."""
from __future__ import annotations

import json
from typing import Any

from ai_editor.formatters.yaml.formatter import YamlFormatter


def serialize_fragment(fragment: dict[str, Any], formatter: YamlFormatter) -> str:
    """Serialize fragment dict to a portable string."""
    _ = formatter
    return json.dumps(fragment, sort_keys=True)


def deserialize_fragment(body: str, formatter: YamlFormatter) -> dict[str, Any]:
    """Restore fragment dict from serialize_fragment output."""
    _ = formatter
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("clipboard body must be a JSON object")
    return data
