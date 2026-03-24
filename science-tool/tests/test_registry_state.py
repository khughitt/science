from __future__ import annotations

from datetime import datetime

from science_tool.registry.state import (
    ProjectSyncState,
    SyncState,
    compute_entity_hash,
    load_sync_state,
    save_sync_state,
)


def test_compute_entity_hash_deterministic():
    ids_a = ["question:q1", "hypothesis:h1", "claim:c1"]
    ids_b = ["claim:c1", "hypothesis:h1", "question:q1"]
    assert compute_entity_hash(ids_a) == compute_entity_hash(ids_b)


def test_compute_entity_hash_differs():
    assert compute_entity_hash(["a:1"]) != compute_entity_hash(["a:2"])


def test_compute_entity_hash_empty():
    h = compute_entity_hash([])
    assert isinstance(h, str) and len(h) == 64


def test_sync_state_round_trip(tmp_path):
    state_path = tmp_path / "sync_state.yaml"
    now = datetime(2026, 3, 23, 14, 30, 0)
    state = SyncState(
        last_sync=now,
        projects={
            "proj-a": ProjectSyncState(last_synced=now, entity_count=42, entity_hash="abc123"),
        },
    )
    save_sync_state(state, state_path)
    loaded = load_sync_state(state_path)
    assert loaded.last_sync == now
    assert loaded.projects["proj-a"].entity_count == 42


def test_load_sync_state_missing(tmp_path):
    state = load_sync_state(tmp_path / "missing.yaml")
    assert state.last_sync is None
    assert state.projects == {}
