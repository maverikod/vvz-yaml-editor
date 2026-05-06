"""Public exports for in-memory YAML mutation operations."""

from yaml_editor.mutations.operations import (
    MutationBatchResult,
    MutationOperation,
    MutationResult,
    apply_mutation,
    apply_mutation_batch,
    collect_changed_paths,
)

__all__ = [
    "MutationBatchResult",
    "MutationOperation",
    "MutationResult",
    "apply_mutation",
    "apply_mutation_batch",
    "collect_changed_paths",
]
