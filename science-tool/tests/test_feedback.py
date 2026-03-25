"""Tests for feedback CRUD, filtering, and deduplication."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.feedback import (
    FeedbackEntry,
    VALID_CATEGORIES,
    VALID_STATUSES,
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
