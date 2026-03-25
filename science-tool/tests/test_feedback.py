"""Tests for feedback CRUD, filtering, and deduplication."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.feedback import (
    FeedbackEntry,
    VALID_CATEGORIES,
    VALID_STATUSES,
    list_entries,
    load_all_entries,
    load_entry,
    save_entry,
    next_feedback_id,
)


def test_valid_categories():
    assert VALID_CATEGORIES == ("friction", "gap", "guidance", "suggestion", "positive")


def test_valid_statuses():
    assert VALID_STATUSES == ("open", "addressed", "deferred", "wontfix")


def test_create_entry_defaults():
    entry = FeedbackEntry(
        id="fb-2026-03-25-001",
        target="command:interpret-results",
        summary="Test summary",
    )
    assert entry.status == "open"
    assert entry.category == "suggestion"
    assert entry.recurrence == 1
    assert entry.related == []
    assert entry.resolution is None
    assert entry.detail is None


def test_save_and_load_round_trip(tmp_path: Path):
    entry = FeedbackEntry(
        id="fb-2026-03-25-001",
        created="2026-03-25",
        project="test-project",
        target="command:discuss",
        category="friction",
        summary="Critical analysis overlaps with alternatives",
        detail="These two sections cover the same ground.",
    )
    save_entry(tmp_path, entry)

    path = tmp_path / "fb-2026-03-25-001.yaml"
    assert path.exists()

    loaded = load_entry(path)
    assert loaded.id == entry.id
    assert loaded.target == entry.target
    assert loaded.category == entry.category
    assert loaded.summary == entry.summary
    assert loaded.detail == entry.detail
    assert loaded.status == "open"
    assert loaded.recurrence == 1


def test_next_feedback_id_empty_dir(tmp_path: Path):
    result = next_feedback_id(tmp_path, "2026-03-25")
    assert result == "fb-2026-03-25-001"


def test_next_feedback_id_existing_entries(tmp_path: Path):
    entry = FeedbackEntry(
        id="fb-2026-03-25-002",
        target="command:discuss",
        summary="Test",
    )
    save_entry(tmp_path, entry)
    result = next_feedback_id(tmp_path, "2026-03-25")
    assert result == "fb-2026-03-25-003"


def test_next_feedback_id_different_date(tmp_path: Path):
    entry = FeedbackEntry(
        id="fb-2026-03-24-005",
        target="command:discuss",
        summary="Test",
    )
    save_entry(tmp_path, entry)
    result = next_feedback_id(tmp_path, "2026-03-25")
    assert result == "fb-2026-03-25-001"


def _make_entry(feedback_dir: Path, id: str, **kwargs) -> FeedbackEntry:
    """Helper to create and save an entry with defaults."""
    defaults = {"target": "command:test", "summary": "Test", "status": "open"}
    defaults.update(kwargs)
    entry = FeedbackEntry(id=id, **defaults)
    save_entry(feedback_dir, entry)
    return entry


def test_load_all_entries(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", summary="First")
    _make_entry(tmp_path, "fb-2026-03-25-002", summary="Second")
    entries = load_all_entries(tmp_path)
    assert len(entries) == 2


def test_load_all_entries_empty_dir(tmp_path: Path):
    entries = load_all_entries(tmp_path)
    assert entries == []


def test_list_entries_default_filters_to_open(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", status="open")
    _make_entry(tmp_path, "fb-2026-03-25-002", status="addressed")
    result = list_entries(tmp_path)
    assert len(result) == 1
    assert result[0].id == "fb-2026-03-25-001"


def test_list_entries_filter_by_target(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", target="command:discuss")
    _make_entry(tmp_path, "fb-2026-03-25-002", target="command:next-steps")
    result = list_entries(tmp_path, target="command:discuss")
    assert len(result) == 1
    assert result[0].target == "command:discuss"


def test_list_entries_filter_by_target_glob(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", target="command:discuss")
    _make_entry(tmp_path, "fb-2026-03-25-002", target="template:discussion")
    _make_entry(tmp_path, "fb-2026-03-25-003", target="command:next-steps")
    result = list_entries(tmp_path, target="command:*")
    assert len(result) == 2


def test_list_entries_filter_by_category(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", category="friction")
    _make_entry(tmp_path, "fb-2026-03-25-002", category="suggestion")
    result = list_entries(tmp_path, category="friction")
    assert len(result) == 1


def test_list_entries_filter_by_project(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", project="seq-feats")
    _make_entry(tmp_path, "fb-2026-03-25-002", project="natural-systems")
    result = list_entries(tmp_path, project="seq-feats")
    assert len(result) == 1


def test_list_entries_sorted_by_recurrence_then_date(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", created="2026-03-25", recurrence=1)
    _make_entry(tmp_path, "fb-2026-03-24-001", created="2026-03-24", recurrence=5)
    _make_entry(tmp_path, "fb-2026-03-25-002", created="2026-03-25", recurrence=3)
    result = list_entries(tmp_path, status=None)  # all statuses
    assert result[0].recurrence == 5
    assert result[1].recurrence == 3
    assert result[2].recurrence == 1


def test_list_entries_multiple_filters_and(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", target="command:discuss", category="friction", project="seq-feats")
    _make_entry(tmp_path, "fb-2026-03-25-002", target="command:discuss", category="suggestion", project="seq-feats")
    _make_entry(tmp_path, "fb-2026-03-25-003", target="command:discuss", category="friction", project="other")
    result = list_entries(tmp_path, target="command:discuss", category="friction", project="seq-feats")
    assert len(result) == 1
    assert result[0].id == "fb-2026-03-25-001"
