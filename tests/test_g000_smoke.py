"""G-000 smoke tests: import verification and text format group end-to-end."""
from __future__ import annotations

import tempfile
import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Import smoke tests
# ---------------------------------------------------------------------------

def test_result_shim_importable() -> None:
    """ai_editor.result imports and functions work correctly."""
    from ai_editor.result import SuccessResult, ErrorResult

    ok = SuccessResult({"x": 1})
    assert ok == {"success": True, "x": 1}

    err = ErrorResult("E_CODE", "bad thing")
    assert err == {"success": False, "error_code": "E_CODE", "message": "bad thing", "details": {}}


def test_project_shim_importable() -> None:
    """ai_editor.project BaseMCPCommand shim imports and works correctly."""
    from ai_editor.project import BaseMCPCommand

    root = Path(tempfile.mkdtemp())
    BaseMCPCommand.register_project_root("test-proj", root)
    cmd = BaseMCPCommand()
    assert cmd._resolve_project_root("test-proj") == root
    assert cmd.validate_params({"a": 1}) == {"a": 1}


def test_git_shim_importable() -> None:
    """ai_editor.git commit_after_write is a no-op."""
    from ai_editor.git import commit_after_write

    result = commit_after_write(Path("/tmp/x"), "msg")
    assert result is None


def test_ported_packages_importable() -> None:
    """ai_editor.ported sub-packages are importable."""
    import ai_editor.ported  # noqa: F401
    import ai_editor.ported.universal_file_edit  # noqa: F401
    import ai_editor.ported.file_handlers  # noqa: F401
    import ai_editor.ported.universal_file_edit.errors  # noqa: F401
    import ai_editor.ported.universal_file_edit.format_group  # noqa: F401
    import ai_editor.ported.universal_file_edit.session  # noqa: F401
    import ai_editor.ported.universal_file_edit.sidecar_cst_apply  # noqa: F401
    import ai_editor.ported.universal_file_edit.tree_temp_edit_batch  # noqa: F401


# ---------------------------------------------------------------------------
# Text format group end-to-end
# ---------------------------------------------------------------------------

def test_text_group_open_edit_write_close() -> None:
    """Open, edit, write, close a .txt file via ported universal_file_edit commands."""
    from ai_editor.project import BaseMCPCommand
    from ai_editor.ported.universal_file_edit.open_command import UniversalFileOpenCommand
    from ai_editor.ported.universal_file_edit.edit_command import UniversalFileEditCommand
    from ai_editor.ported.universal_file_edit.write_command import UniversalFileWriteCommand
    from ai_editor.ported.universal_file_edit.close_command import UniversalFileCloseCommand
    import asyncio

    # Set up a temp project root with a test file
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        project_id = "smoke-test-proj"
        BaseMCPCommand.register_project_root(project_id, root)

        test_file = root / "hello.txt"
        test_file.write_text("line one\nline two\nline three\n", encoding="utf-8")

        # Open
        open_cmd = UniversalFileOpenCommand()
        open_result = asyncio.get_event_loop().run_until_complete(
            open_cmd.execute(project_id=project_id, file_path="hello.txt")
        )
        assert open_result.get("success") is True, f"Open failed: {open_result}"
        session_id = open_result["session_id"]
        assert open_result["format_group"] == "text"

        # Edit: replace line 2
        edit_cmd = UniversalFileEditCommand()
        edit_result = asyncio.get_event_loop().run_until_complete(
            edit_cmd.execute(
                project_id=project_id,
                session_id=session_id,
                operations=[{"type": "replace", "start_line": 2, "end_line": 2, "content": "line TWO"}],
            )
        )
        assert edit_result.get("success") is True, f"Edit failed: {edit_result}"

        # Write (commit)
        write_cmd = UniversalFileWriteCommand()
        write_result = asyncio.get_event_loop().run_until_complete(
            write_cmd.execute(
                project_id=project_id,
                session_id=session_id,
                write_mode="commit",
            )
        )
        assert write_result.get("success") is True, f"Write failed: {write_result}"

        # Close
        close_cmd = UniversalFileCloseCommand()
        close_result = asyncio.get_event_loop().run_until_complete(
            close_cmd.execute(project_id=project_id, session_id=session_id)
        )
        assert close_result.get("success") is True, f"Close failed: {close_result}"

        # Verify file content
        content = test_file.read_text(encoding="utf-8")
        assert "line TWO" in content, f"Expected edited content; got: {content!r}"
        assert "line two" not in content, f"Old content still present: {content!r}"
