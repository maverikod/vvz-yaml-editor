"""Tests for project-relative path normalization."""
from __future__ import annotations

import pytest

from ai_editor.sessions.project_paths import normalize_project_relative_path


def test_normalize_accepts_project_relative_path() -> None:
    assert normalize_project_relative_path("tmp/foo.txt") == "tmp/foo.txt"


def test_normalize_rejects_absolute_path() -> None:
    with pytest.raises(ValueError, match="Absolute file_path"):
        normalize_project_relative_path("/tmp/foo.txt")
