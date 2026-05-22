"""Structured docstring metadata for CST nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DocstringMeta:
    summary: str = ""
    args: dict[str, str] = field(default_factory=dict)
    returns: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    docstring_body: str = ""

    def is_empty(self) -> bool:
        return not (self.summary or self.args or self.returns or self.attributes or self.docstring_body)

    def to_dict(self) -> dict[str, Any]:
        """Include only non-empty fields."""
        out: dict[str, Any] = {}
        if self.summary:
            out["summary"] = self.summary
        if self.args:
            out["args"] = dict(self.args)
        if self.returns:
            out["returns"] = self.returns
        if self.attributes:
            out["attributes"] = dict(self.attributes)
        if self.docstring_body:
            out["docstring_body"] = self.docstring_body
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocstringMeta:
        return cls(
            summary=str(data.get("summary", "") or ""),
            args={str(k): str(v) for k, v in dict(data.get("args", {})).items()},
            returns=str(data.get("returns", "") or ""),
            attributes={str(k): str(v) for k, v in dict(data.get("attributes", {})).items()},
            docstring_body=str(data.get("docstring_body", "") or ""),
        )

    @classmethod
    def parse_docstring(cls, raw: str) -> DocstringMeta:
        """Parse Google-style sections Args:/Returns:/Attributes:."""
        text = raw.strip("\n")
        if not text.strip():
            return cls()
        lines = [line.rstrip() for line in text.splitlines()]
        summary = lines[0].strip() if lines else ""
        args: dict[str, str] = {}
        attributes: dict[str, str] = {}
        returns_lines: list[str] = []
        body_lines: list[str] = []
        mode = "body"
        for line in lines[1:]:
            stripped = line.strip()
            if stripped in {"Args:", "Arguments:"}:
                mode = "args"
                continue
            if stripped == "Returns:":
                mode = "returns"
                continue
            if stripped == "Attributes:":
                mode = "attributes"
                continue
            if mode == "args" and ":" in stripped:
                key, value = stripped.split(":", 1)
                args[key.strip()] = value.strip()
            elif mode == "attributes" and ":" in stripped:
                key, value = stripped.split(":", 1)
                attributes[key.strip()] = value.strip()
            elif mode == "returns":
                if stripped:
                    returns_lines.append(stripped)
            elif stripped:
                body_lines.append(stripped)
        if not args and not attributes and not returns_lines and body_lines:
            return cls(summary=summary, docstring_body="\n".join(lines).strip())
        return cls(
            summary=summary,
            args=args,
            returns="\n".join(returns_lines).strip(),
            attributes=attributes,
            docstring_body="\n".join(body_lines).strip(),
        )
