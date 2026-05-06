"""
Structural YAML manipulation: path-based read/write with checked, atomic saves.

Designed to be embedded in an MCP server as a dependency (`pip install vvz-yaml-editor`).
"""

from yaml_editor._version import __version__
from yaml_editor.cmd_convenience import (
    yaml_append_verification,
    yaml_get_command,
    yaml_get_verification,
    yaml_update_command,
    yaml_validate_plan_task,
)
from yaml_editor.cmd_load import yaml_load
from yaml_editor.cmd_mutations import (
    yaml_append,
    yaml_delete,
    yaml_get,
    yaml_move,
    yaml_replace_block,
    yaml_set,
)
from yaml_editor.cmd_unsafe import yaml_read_lines, yaml_write_lines_unsafe
from yaml_editor.cmd_validate import yaml_validate
from yaml_editor.cmd_write_checked import yaml_write_checked

__all__ = [
    "__version__",
    "yaml_append",
    "yaml_append_verification",
    "yaml_delete",
    "yaml_get",
    "yaml_get_command",
    "yaml_get_verification",
    "yaml_load",
    "yaml_move",
    "yaml_read_lines",
    "yaml_replace_block",
    "yaml_set",
    "yaml_update_command",
    "yaml_validate",
    "yaml_validate_plan_task",
    "yaml_write_checked",
    "yaml_write_lines_unsafe",
]
