"""Sync state tracking for cross-project sync."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from science_tool.registry.config import get_science_config_dir


def get_default_state_path() -> Path:
    """Resolve the default sync state path at runtime."""
    return get_science_config_dir() / "sync_state.yaml"


DEFAULT_STATE_PATH = get_default_state_path()


class ProjectSyncState(BaseModel):
    """Per-project sync state."""

    last_synced: datetime
    entity_count: int
    entity_hash: str


class SyncState(BaseModel):
    """Global sync state at ~/.config/science/sync_state.yaml."""

    last_sync: datetime | None = None
    projects: dict[str, ProjectSyncState] = Field(default_factory=dict)


def compute_entity_hash(canonical_ids: list[str]) -> str:
    """SHA-256 of sorted, newline-joined canonical IDs."""
    joined = "\n".join(sorted(canonical_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def load_sync_state(state_path: Path | None = None) -> SyncState:
    """Load sync state from YAML. Returns defaults if file missing."""
    state_path = state_path or get_default_state_path()
    if not state_path.is_file():
        return SyncState()
    data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
    return SyncState.model_validate(data)


def save_sync_state(state: SyncState, state_path: Path | None = None) -> None:
    """Save sync state to YAML."""
    state_path = state_path or get_default_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    data = state.model_dump(mode="json")
    state_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
