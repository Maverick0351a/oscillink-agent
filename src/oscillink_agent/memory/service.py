"""Configured source loading for governed product memory."""

from pathlib import Path

from oscillink_agent.memory.obsidian import (
    ReviewedObsidianIndex,
    build_reviewed_obsidian_index,
)
from oscillink_agent.memory.projection import MemoryUnavailableReason


def load_memory_index(
    vault_root: Path | None,
) -> tuple[ReviewedObsidianIndex | None, MemoryUnavailableReason | None]:
    if vault_root is None:
        return None, MemoryUnavailableReason.VAULT_NOT_CONFIGURED
    if not vault_root.is_dir():
        return None, MemoryUnavailableReason.VAULT_NOT_FOUND
    try:
        return build_reviewed_obsidian_index(vault_root), None
    except (OSError, ValueError):
        return None, MemoryUnavailableReason.INDEX_BUILD_FAILED
