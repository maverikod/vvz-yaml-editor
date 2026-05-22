"""ConversionRegistry and ConversionRule for cross-formatter clipboard conversion."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ai_editor.contracts.error_codes import ErrorCode


@dataclass
class ConversionRule:
    """Single cross-formatter conversion entry."""

    source_formatter: str
    target_formatter: str
    converter: Callable[[Any, Any, Any], Any]
    lossy: bool
    description: str


class ConversionRegistry:
    """Registry of cross-formatter conversion rules."""

    def __init__(self) -> None:
        self._rules: dict[tuple[str, str], ConversionRule] = {}

    def register(self, rule: ConversionRule) -> None:
        """Register a ConversionRule; last write wins."""
        self._rules[(rule.source_formatter, rule.target_formatter)] = rule

    def can_convert(self, source_fmt: str, target_fmt: str) -> bool:
        """Return True if a conversion rule exists for this pair."""
        if source_fmt == target_fmt:
            return True
        return (source_fmt, target_fmt) in self._rules

    def convert(
        self,
        fragment: Any,
        source_fmt: str,
        target_fmt: str,
        src_inst: Any,
        tgt_inst: Any,
    ) -> Any:
        """Convert fragment. Raises ValueError(CLIPBOARD_FORMAT_MISMATCH) on unknown pair or error."""
        if source_fmt == target_fmt:
            return fragment
        rule = self._rules.get((source_fmt, target_fmt))
        if rule is None:
            raise ValueError(ErrorCode.CLIPBOARD_FORMAT_MISMATCH.value)
        try:
            return rule.converter(fragment, src_inst, tgt_inst)
        except Exception as exc:
            raise ValueError(ErrorCode.CLIPBOARD_FORMAT_MISMATCH.value) from exc

    def list_conversions(self) -> list[ConversionRule]:
        """Return all registered ConversionRule entries."""
        return list(self._rules.values())


# Module-level singleton
conversion_registry = ConversionRegistry()
