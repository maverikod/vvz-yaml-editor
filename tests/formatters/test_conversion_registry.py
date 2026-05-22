from __future__ import annotations

import pytest

from ai_editor.contracts.error_codes import ErrorCode
from ai_editor.formatters.conversion.registry import ConversionRegistry
from ai_editor.formatters.conversion.rules import register_all_rules
from ai_editor.formatters.markdown import MarkdownFormatter
from ai_editor.formatters.text import TextFormatter


class TestConversionRegistry:
    def test_register_all_rules_registers_22_rules(self) -> None:
        registry = ConversionRegistry()
        register_all_rules(registry)

        assert len(registry.list_conversions()) == 22

    def test_can_convert_known_pairs(self) -> None:
        registry = ConversionRegistry()
        register_all_rules(registry)

        assert registry.can_convert("text", "markdown") is True
        assert registry.can_convert("markdown", "html") is True

    def test_convert_produces_output(self) -> None:
        registry = ConversionRegistry()
        register_all_rules(registry)

        converted = registry.convert(
            "hello world",
            "text",
            "markdown",
            TextFormatter(),
            MarkdownFormatter(),
        )
        assert isinstance(converted, str)
        assert converted.strip() != ""

    def test_unsupported_pair_raises_clipboard_mismatch(self) -> None:
        registry = ConversionRegistry()
        register_all_rules(registry)

        with pytest.raises(ValueError) as exc:
            registry.convert("x", "yaml", "html", object(), object())

        assert str(exc.value) == ErrorCode.CLIPBOARD_FORMAT_MISMATCH.value
