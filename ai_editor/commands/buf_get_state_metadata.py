"""Extended metadata for buf_get_state command."""
from __future__ import annotations

from typing import Any, Type

from ai_editor.commands._metadata_common import (
    buffer_id_param,
    build_metadata,
    error_block,
    example_buffer_id,
    example_session_key,
    return_buffer_state,
    session_key_param,
)


def get_buf_get_state_metadata(cls: Type[Any]) -> dict[str, Any]:
    """Return AI/documentation metadata for buf_get_state."""
    sk = example_session_key()
    bid = example_buffer_id()
    return build_metadata(
        cls,
        detailed_description=(
            "Return a read-only snapshot of an open buffer: formatter name, skeleton "
            "preview, modified and readonly flags, and project-relative path when bound "
            "to a remote file. Does not mutate session state or write files."
        ),
        parameters={
            "session_key": session_key_param(),
            "buffer_id": buffer_id_param(),
        },
        return_value=return_buffer_state(),
        usage_examples=[
            {
                "description": "Inspect buffer before editing",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Returns preview skeleton and modified/readonly flags.",
            },
            {
                "description": "Verify path binding after buf_save_as",
                "command": {"session_key": sk, "buffer_id": bid},
                "explanation": "Check file_path/relative_path and formatter in the response.",
            },
        ],
        error_cases={
            "BUFFER_NOT_FOUND": error_block(
                "BUFFER_NOT_FOUND",
                "Buffer not found: {buffer_id}",
                "Verify buffer_id via session_status.",
                description="Unknown buffer_id returns success=false in data.",
            ),
        },
        best_practices=[
            "Use before buf_mutate_batch to confirm formatter and readonly state.",
            "Prefer file_get when you also need the full file_get command semantics.",
            "Check modified flag before file_close with force=false.",
        ],
    )
