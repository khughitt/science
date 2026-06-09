from __future__ import annotations

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.base import StorageAdapter


def test_storage_adapter_default_participation_mode_is_owner() -> None:
    assert StorageAdapter.participation_mode is ParticipationMode.OWNER
