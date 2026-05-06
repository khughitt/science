"""Tests for feedback CRUD, filtering, and deduplication."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.feedback import (
    FeedbackEntry,
    VALID_CATEGORIES,
    VALID_STATUSES,
    detect_project,
    find_duplicate,
    group_for_triage,
    list_entries,
    load_all_entries,
    load_entry,
    next_feedback_id,
    render_report,
    save_entry,
    update_entry,
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


def _make_entry(
    feedback_dir: Path,
    id: str,
    *,
    created: str | None = None,
    project: str = "",
    target: str = "command:test",
    category: str = "suggestion",
    status: str = "open",
    summary: str = "Test",
    detail: str | None = None,
    resolution: str | None = None,
    recurrence: int = 1,
    related: list[str] | None = None,
) -> FeedbackEntry:
    """Helper to create and save an entry with defaults."""
    entry = FeedbackEntry(
        id=id,
        created=created or "2026-03-25",
        project=project,
        target=target,
        category=category,
        status=status,
        summary=summary,
        detail=detail,
        resolution=resolution,
        recurrence=recurrence,
        related=related or [],
    )
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


def test_update_entry_status(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001")
    updated = update_entry(
        tmp_path,
        "fb-2026-03-25-001",
        status="addressed",
        resolution="commit:abc123 — fixed it",
    )
    assert updated.status == "addressed"
    assert updated.resolution == "commit:abc123 — fixed it"
    reloaded = load_entry(tmp_path / "fb-2026-03-25-001.yaml")
    assert reloaded.status == "addressed"


def test_update_entry_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        update_entry(tmp_path, "fb-2026-03-25-999", status="addressed")


def test_update_entry_resolution_required_for_terminal_status(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001")
    with pytest.raises(ValueError, match="resolution"):
        update_entry(tmp_path, "fb-2026-03-25-001", status="addressed")


def test_update_entry_category(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", category="suggestion")
    updated = update_entry(tmp_path, "fb-2026-03-25-001", category="friction")
    assert updated.category == "friction"


def test_find_duplicate_exact_match(tmp_path: Path):
    _make_entry(
        tmp_path,
        "fb-2026-03-25-001",
        target="command:discuss",
        summary="Add User Questions section",
    )
    dup = find_duplicate(tmp_path, target="command:discuss", summary="Add User Questions section")
    assert dup is not None
    assert dup.id == "fb-2026-03-25-001"


def test_find_duplicate_substring_match(tmp_path: Path):
    _make_entry(
        tmp_path,
        "fb-2026-03-25-001",
        target="command:discuss",
        summary="Add User Questions section to interpretation template",
    )
    dup = find_duplicate(tmp_path, target="command:discuss", summary="User Questions section")
    assert dup is not None


def test_find_duplicate_no_match(tmp_path: Path):
    _make_entry(
        tmp_path,
        "fb-2026-03-25-001",
        target="command:discuss",
        summary="Something else entirely",
    )
    dup = find_duplicate(tmp_path, target="command:discuss", summary="User Questions section")
    assert dup is None


def test_find_duplicate_ignores_non_open(tmp_path: Path):
    _make_entry(
        tmp_path,
        "fb-2026-03-25-001",
        target="command:discuss",
        summary="Add User Questions section",
        status="addressed",
    )
    dup = find_duplicate(tmp_path, target="command:discuss", summary="Add User Questions section")
    assert dup is None


def test_find_duplicate_different_target_no_match(tmp_path: Path):
    _make_entry(
        tmp_path,
        "fb-2026-03-25-001",
        target="command:next-steps",
        summary="Add User Questions section",
    )
    dup = find_duplicate(tmp_path, target="command:discuss", summary="Add User Questions section")
    assert dup is None


def test_group_for_triage(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", target="command:discuss", project="proj-a")
    _make_entry(tmp_path, "fb-2026-03-25-002", target="command:discuss", project="proj-b")
    _make_entry(tmp_path, "fb-2026-03-25-003", target="command:next-steps", project="proj-a")

    groups = group_for_triage(tmp_path)
    assert "command:discuss" in groups
    assert "command:next-steps" in groups
    assert len(groups["command:discuss"]["entries"]) == 2
    assert groups["command:discuss"]["projects"] == {"proj-a", "proj-b"}
    assert groups["command:discuss"]["total_recurrence"] == 2


def test_group_for_triage_with_target_glob(tmp_path: Path):
    _make_entry(tmp_path, "fb-2026-03-25-001", target="command:discuss")
    _make_entry(tmp_path, "fb-2026-03-25-002", target="template:discussion")
    groups = group_for_triage(tmp_path, target="command:*")
    assert "command:discuss" in groups
    assert "template:discussion" not in groups


def test_render_report(tmp_path: Path):
    _make_entry(
        tmp_path,
        "fb-2026-03-25-001",
        target="command:discuss",
        category="friction",
        summary="Test issue",
        project="seq-feats",
    )
    report = render_report(tmp_path)
    assert "command:discuss" in report
    assert "Test issue" in report
    assert "friction" in report


def test_render_report_empty(tmp_path: Path):
    report = render_report(tmp_path)
    assert "No feedback entries" in report


def test_detect_project_from_science_yaml(tmp_path: Path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    (project_dir / "science.yaml").write_text("profile: research\n")
    result = detect_project(project_dir)
    assert result == "my-project"


def test_detect_project_walks_up(tmp_path: Path):
    project_dir = tmp_path / "my-project"
    sub_dir = project_dir / "src" / "deep"
    sub_dir.mkdir(parents=True)
    (project_dir / "science.yaml").write_text("profile: research\n")
    result = detect_project(sub_dir)
    assert result == "my-project"


def test_detect_project_no_science_yaml_uses_cwd_name(tmp_path: Path):
    leaf = tmp_path / "some-dir"
    leaf.mkdir()
    result = detect_project(leaf)
    assert result == "some-dir"
