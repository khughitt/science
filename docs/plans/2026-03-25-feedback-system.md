# Centralized Feedback System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `feedback` command group to `science-tool` that stores structured feedback entries as individual YAML files in `~/.config/science/feedback/`, with CLI commands for add, list, update, triage, and report.

**Architecture:** New `feedback.py` module handles YAML CRUD, filtering, deduplication, and report rendering. CLI commands in `cli.py` delegate to this module following the same pattern as `tasks`. The process reflection section in all 16 command files is updated to call `science-tool feedback add` instead of appending to markdown.

**Tech Stack:** Python, Click, PyYAML, Pydantic, Rich (all existing dependencies)

**Spec:** `docs/superpowers/specs/2026-03-25-feedback-system-design.md`

**Existing patterns to follow:**
- Module: `science-tool/src/science_tool/tasks.py` (CRUD functions)
- CLI: `cli.py:1439-1638` (tasks group registration + subcommands)
- Config: `registry/config.py` (SCIENCE_CONFIG_DIR, YAML load/save)
- Output: `output.py` (emit_query_rows for table/json)
- Tests: `tests/test_tasks.py` (unit), `tests/test_tasks_cli.py` (CLI integration)

---

### Task 1: Feedback data model and YAML I/O

**Files:**
- Create: `science-tool/src/science_tool/feedback.py`
- Test: `science-tool/tests/test_feedback.py`

- [ ] **Step 1: Write the failing tests for the data model and YAML round-trip**

```python
# science-tool/tests/test_feedback.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.feedback'`

- [ ] **Step 3: Write minimal implementation**

```python
# science-tool/src/science_tool/feedback.py
"""Feedback entry CRUD, filtering, and deduplication for science-tool.

Stores structured feedback as individual YAML files in ~/.config/science/feedback/.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

VALID_CATEGORIES = ("friction", "gap", "guidance", "suggestion", "positive")
VALID_STATUSES = ("open", "addressed", "deferred", "wontfix")

_ID_RE = re.compile(r"^fb-(\d{4}-\d{2}-\d{2})-(\d{3})$")


class FeedbackEntry(BaseModel):
    """A single feedback entry."""

    id: str
    created: str = Field(default_factory=lambda: date.today().isoformat())
    project: str = ""
    target: str
    category: str = "suggestion"
    status: str = "open"
    summary: str
    detail: str | None = None
    resolution: str | None = None
    recurrence: int = 1
    related: list[str] = Field(default_factory=list)


def save_entry(feedback_dir: Path, entry: FeedbackEntry) -> Path:
    """Write a feedback entry to a YAML file. Returns the file path."""
    feedback_dir.mkdir(parents=True, exist_ok=True)
    path = feedback_dir / f"{entry.id}.yaml"
    data = entry.model_dump(mode="json")
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return path


def load_entry(path: Path) -> FeedbackEntry:
    """Load a feedback entry from a YAML file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return FeedbackEntry.model_validate(data)


def next_feedback_id(feedback_dir: Path, date_str: str) -> str:
    """Determine the next feedback ID for a given date."""
    max_num = 0
    prefix = f"fb-{date_str}-"

    if feedback_dir.is_dir():
        for path in feedback_dir.glob(f"{prefix}*.yaml"):
            m = _ID_RE.match(path.stem)
            if m and m.group(1) == date_str:
                max_num = max(max_num, int(m.group(2)))

    return f"fb-{date_str}-{max_num + 1:03d}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
git add src/science_tool/feedback.py tests/test_feedback.py
git commit -m "feat(feedback): add data model and YAML I/O"
```

---

### Task 2: List and filter operations

**Files:**
- Modify: `science-tool/src/science_tool/feedback.py`
- Modify: `science-tool/tests/test_feedback.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_feedback.py`:

```python
from science_tool.feedback import list_entries, load_all_entries


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
    # Sorted by recurrence descending, then date descending (most recent first)
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
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v -k "test_list or test_load_all"`
Expected: FAIL — `ImportError: cannot import name 'list_entries'`

- [ ] **Step 3: Implement list and filter functions**

Add to `feedback.py`:

```python
from fnmatch import fnmatch


def load_all_entries(feedback_dir: Path) -> list[FeedbackEntry]:
    """Load all feedback entries from a directory."""
    if not feedback_dir.is_dir():
        return []
    entries = []
    for path in sorted(feedback_dir.glob("fb-*.yaml")):
        entries.append(load_entry(path))
    return entries


def list_entries(
    feedback_dir: Path,
    *,
    status: str | None = "open",
    target: str | None = None,
    category: str | None = None,
    project: str | None = None,
) -> list[FeedbackEntry]:
    """Filter feedback entries. Default: open entries only. Pass status=None for all."""
    entries = load_all_entries(feedback_dir)

    if status is not None:
        entries = [e for e in entries if e.status == status]
    if target is not None:
        entries = [e for e in entries if fnmatch(e.target, target)]
    if category is not None:
        entries = [e for e in entries if e.category == category]
    if project is not None:
        entries = [e for e in entries if e.project == project]

    # Sort by recurrence descending, then date descending (most recent first)
    entries.sort(key=lambda e: (e.recurrence, e.created), reverse=True)

    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
git add src/science_tool/feedback.py tests/test_feedback.py
git commit -m "feat(feedback): add list and filter operations"
```

---

### Task 3: Update and deduplication operations

**Files:**
- Modify: `science-tool/src/science_tool/feedback.py`
- Modify: `science-tool/tests/test_feedback.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_feedback.py`:

```python
from science_tool.feedback import update_entry, find_duplicate


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
    # Verify persisted
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
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v -k "test_update or test_find_duplicate"`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement update and deduplication**

Add to `feedback.py`:

```python
def update_entry(
    feedback_dir: Path,
    entry_id: str,
    *,
    status: str | None = None,
    resolution: str | None = None,
    category: str | None = None,
    summary: str | None = None,
    detail: str | None = None,
    related: list[str] | None = None,
) -> FeedbackEntry:
    """Update fields on an existing entry. Raises FileNotFoundError if not found."""
    path = feedback_dir / f"{entry_id}.yaml"
    if not path.exists():
        msg = f"Feedback entry not found: {entry_id}"
        raise FileNotFoundError(msg)

    entry = load_entry(path)

    if status is not None:
        if status in ("addressed", "deferred", "wontfix") and resolution is None:
            msg = f"--resolution is required when setting status to '{status}'"
            raise ValueError(msg)
        entry.status = status
    if resolution is not None:
        entry.resolution = resolution
    if category is not None:
        entry.category = category
    if summary is not None:
        entry.summary = summary
    if detail is not None:
        entry.detail = detail
    if related is not None:
        entry.related = related

    save_entry(feedback_dir, entry)
    return entry


def find_duplicate(
    feedback_dir: Path,
    *,
    target: str,
    summary: str,
) -> FeedbackEntry | None:
    """Find an existing open entry with the same target and similar summary.

    Uses bidirectional substring matching: returns a match if either summary
    is a substring of the other.
    """
    entries = list_entries(feedback_dir, status="open", target=target)
    summary_lower = summary.lower()
    for entry in entries:
        entry_summary_lower = entry.summary.lower()
        if summary_lower in entry_summary_lower or entry_summary_lower in summary_lower:
            return entry
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
git add src/science_tool/feedback.py tests/test_feedback.py
git commit -m "feat(feedback): add update and deduplication operations"
```

---

### Task 4: Triage grouping and report rendering

**Files:**
- Modify: `science-tool/src/science_tool/feedback.py`
- Modify: `science-tool/tests/test_feedback.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_feedback.py`:

```python
from science_tool.feedback import group_for_triage, render_report


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
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v -k "test_group or test_render"`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement triage grouping and report rendering**

Add to `feedback.py`:

```python
def group_for_triage(
    feedback_dir: Path,
    *,
    target: str | None = None,
) -> dict[str, dict]:
    """Group open entries by target for triage display.

    Returns: {target: {entries: [...], projects: set, total_recurrence: int}}
    Sorted by total_recurrence descending.
    """
    entries = list_entries(feedback_dir, status="open", target=target)

    groups: dict[str, dict] = {}
    for entry in entries:
        if entry.target not in groups:
            groups[entry.target] = {
                "entries": [],
                "projects": set(),
                "total_recurrence": 0,
            }
        groups[entry.target]["entries"].append(entry)
        if entry.project:
            groups[entry.target]["projects"].add(entry.project)
        groups[entry.target]["total_recurrence"] += entry.recurrence

    # Sort groups by total recurrence descending
    return dict(
        sorted(groups.items(), key=lambda item: -item[1]["total_recurrence"])
    )


def render_report(
    feedback_dir: Path,
    *,
    status: str | None = None,
    project: str | None = None,
) -> str:
    """Render a human-readable markdown report of feedback entries."""
    entries = list_entries(feedback_dir, status=status, project=project)

    if not entries:
        return "No feedback entries found.\n"

    # Group by target
    by_target: dict[str, list[FeedbackEntry]] = {}
    for entry in entries:
        by_target.setdefault(entry.target, []).append(entry)

    lines = ["# Feedback Report", ""]
    for target, group in sorted(by_target.items()):
        lines.append(f"## {target}")
        lines.append("")
        for entry in group:
            status_badge = f"[{entry.status}]"
            lines.append(f"- **{entry.id}** {status_badge} ({entry.category}) — {entry.summary}")
            if entry.recurrence > 1:
                lines.append(f"  - Recurrence: {entry.recurrence}")
            if entry.resolution:
                lines.append(f"  - Resolution: {entry.resolution}")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
git add src/science_tool/feedback.py tests/test_feedback.py
git commit -m "feat(feedback): add triage grouping and report rendering"
```

---

### Task 5: Project auto-detection helper

**Files:**
- Modify: `science-tool/src/science_tool/feedback.py`
- Modify: `science-tool/tests/test_feedback.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_feedback.py`:

```python
from science_tool.feedback import detect_project


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
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v -k "test_detect"`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement detect_project**

Add to `feedback.py`:

```python
def detect_project(start: Path) -> str:
    """Detect the project name by walking up to find science.yaml.

    Returns the directory name of the nearest ancestor containing science.yaml,
    or the start directory name if none found. Walk stops at $HOME.
    """
    home = Path.home()
    current = start.resolve()

    while current != current.parent:
        if (current / "science.yaml").exists():
            return current.name
        if current == home:
            break
        current = current.parent

    return start.resolve().name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
git add src/science_tool/feedback.py tests/test_feedback.py
git commit -m "feat(feedback): add project auto-detection"
```

---

### Task 6: CLI command group — add, list, update

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Create: `science-tool/tests/test_feedback_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

```python
# science-tool/tests/test_feedback_cli.py
"""Tests for the feedback CLI command group."""

from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestFeedbackAdd:
    def test_add_creates_entry(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(
            main,
            [
                "feedback", "add",
                "--target", "command:discuss",
                "--summary", "Test feedback entry",
            ],
            env=env,
        )
        assert result.exit_code == 0
        assert "fb-" in result.output
        # Verify file was created
        files = list(tmp_path.glob("fb-*.yaml"))
        assert len(files) == 1

    def test_add_with_all_options(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(
            main,
            [
                "feedback", "add",
                "--target", "template:interpretation",
                "--category", "friction",
                "--summary", "Data quality section missing",
                "--detail", "Found two data bugs at interpretation time",
                "--project", "seq-feats",
            ],
            env=env,
        )
        assert result.exit_code == 0
        assert "fb-" in result.output

    def test_add_requires_target(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(
            main,
            ["feedback", "add", "--summary", "No target"],
            env=env,
        )
        assert result.exit_code != 0

    def test_add_requires_summary(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(
            main,
            ["feedback", "add", "--target", "command:test"],
            env=env,
        )
        assert result.exit_code != 0


class TestFeedbackList:
    def test_list_empty(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(main, ["feedback", "list"], env=env)
        assert result.exit_code == 0

    def test_list_json_format(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        # Add an entry first
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:test", "--summary", "Test"],
            env=env,
        )
        result = runner.invoke(
            main,
            ["feedback", "list", "--format", "json"],
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["rows"]) == 1


class TestFeedbackUpdate:
    def test_update_status(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        # Add an entry
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:test", "--summary", "Test"],
            env=env,
        )
        # Find the ID
        files = list(tmp_path.glob("fb-*.yaml"))
        entry_id = files[0].stem

        result = runner.invoke(
            main,
            ["feedback", "update", entry_id, "--status", "addressed", "--resolution", "Fixed in v2"],
            env=env,
        )
        assert result.exit_code == 0
        assert "updated" in result.output.lower() or entry_id in result.output

    def test_update_requires_resolution_for_addressed(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:test", "--summary", "Test"],
            env=env,
        )
        files = list(tmp_path.glob("fb-*.yaml"))
        entry_id = files[0].stem

        result = runner.invoke(
            main,
            ["feedback", "update", entry_id, "--status", "addressed"],
            env=env,
        )
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback_cli.py -v`
Expected: FAIL — `Error: No such command 'feedback'`

- [ ] **Step 3: Add the feedback CLI group with add, list, update commands**

Add to `cli.py` after the sync group (around line 1740). Also add a `FEEDBACK_DIR` constant near the top of the file and an env var override for testing:

Near the top of `cli.py`, after the existing imports, add:
```python
from science_tool.registry.config import SCIENCE_CONFIG_DIR
```

(Note: `SCIENCE_CONFIG_DIR` may already be imported — check first. If not, add it.)

Then after the last existing command group, add:

```python
@main.group()
def feedback() -> None:
    """Feedback management commands."""


def _get_feedback_dir() -> Path:
    import os
    return Path(os.environ.get("SCIENCE_FEEDBACK_DIR", str(SCIENCE_CONFIG_DIR / "feedback")))


@feedback.command("add")
@click.option("--target", required=True, help="What the feedback is about (e.g., command:interpret-results)")
@click.option("--summary", required=True, help="One-line description")
@click.option("--category", default="suggestion", type=click.Choice(_FB_CATEGORIES))
@click.option("--detail", default=None, help="Optional prose detail")
@click.option("--project", default=None, help="Project name (auto-detected if omitted)")
@click.option("--related", multiple=True, help="Related feedback entry IDs")
def feedback_add(
    target: str,
    summary: str,
    category: str,
    detail: str | None,
    project: str | None,
    related: tuple[str, ...],
) -> None:
    """Add a feedback entry."""
    from datetime import date as _date

    from science_tool.feedback import (
        FeedbackEntry,
        detect_project,
        find_duplicate,
        next_feedback_id,
        save_entry,
    )

    fb_dir = _get_feedback_dir()

    if project is None:
        project = detect_project(Path.cwd())

    # Check for duplicates
    dup = find_duplicate(fb_dir, target=target, summary=summary)
    if dup is not None:
        dup.recurrence += 1
        save_entry(fb_dir, dup)
        click.echo(f"Incremented recurrence on {dup.id} (now {dup.recurrence})")
        return

    today = _date.today().isoformat()
    entry_id = next_feedback_id(fb_dir, today)

    entry = FeedbackEntry(
        id=entry_id,
        created=today,
        project=project,
        target=target,
        category=category,
        summary=summary,
        detail=detail,
        related=list(related),
    )
    save_entry(fb_dir, entry)
    click.echo(f"Created {entry.id}: {entry.summary}")


@feedback.command("list")
@click.option("--status", default="open", help="Filter by status (omit for 'open'; use 'all' for all statuses)")
@click.option("--target", default=None, help="Filter by target (supports fnmatch globs)")
@click.option("--category", default=None, type=click.Choice(_FB_CATEGORIES))
@click.option("--project", default=None, help="Filter by project")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def feedback_list(
    status: str | None,
    target: str | None,
    category: str | None,
    project: str | None,
    output_format: str,
) -> None:
    """List feedback entries (default: open only)."""
    if status == "all":
        status = None
    from science_tool.feedback import list_entries

    fb_dir = _get_feedback_dir()
    entries = list_entries(fb_dir, status=status, target=target, category=category, project=project)

    columns = [
        ("id", "ID"),
        ("created", "Date"),
        ("project", "Project"),
        ("target", "Target"),
        ("category", "Category"),
        ("summary", "Summary"),
        ("recurrence", "Recur"),
    ]
    rows = [
        {
            "id": e.id,
            "created": e.created,
            "project": e.project,
            "target": e.target,
            "category": e.category,
            "summary": e.summary,
            "recurrence": e.recurrence,
        }
        for e in entries
    ]
    emit_query_rows(output_format=output_format, title="Feedback", columns=columns, rows=rows)


@feedback.command("update")
@click.argument("entry_id")
@click.option("--status", default=None, type=click.Choice(_FB_STATUSES))
@click.option("--resolution", default=None, help="Required when setting terminal status")
@click.option("--category", default=None, type=click.Choice(_FB_CATEGORIES))
@click.option("--summary", default=None)
@click.option("--detail", default=None)
@click.option("--related", multiple=True, help="Related feedback entry IDs")
def feedback_update(
    entry_id: str,
    status: str | None,
    resolution: str | None,
    category: str | None,
    summary: str | None,
    detail: str | None,
    related: tuple[str, ...],
) -> None:
    """Update a feedback entry."""
    from science_tool.feedback import update_entry as _update

    fb_dir = _get_feedback_dir()
    try:
        entry = _update(
            fb_dir,
            entry_id,
            status=status,
            resolution=resolution,
            category=category,
            summary=summary,
            detail=detail,
            related=list(related) if related else None,
        )
    except (FileNotFoundError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Updated {entry.id}")
```

Add the necessary constants near the top of `cli.py` (defined inline to avoid importing feedback.py at module level, which would slow startup for unrelated commands):
```python
_FB_CATEGORIES = ("friction", "gap", "guidance", "suggestion", "positive")
_FB_STATUSES = ("open", "addressed", "deferred", "wontfix")
```

Also ensure `SCIENCE_CONFIG_DIR` is imported from `science_tool.registry.config` (check if already imported; add if not).

Then replace `VALID_CATEGORIES` with `_FB_CATEGORIES` and `VALID_STATUSES` with `_FB_STATUSES` throughout the feedback CLI commands below.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
git add src/science_tool/cli.py tests/test_feedback_cli.py
git commit -m "feat(feedback): add CLI commands — add, list, update"
```

---

### Task 7: CLI commands — triage and report

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/tests/test_feedback_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_feedback_cli.py`:

```python
class TestFeedbackTriage:
    def test_triage_shows_grouped_output(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:discuss", "--summary", "Issue A", "--project", "proj-a"],
            env=env,
        )
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:discuss", "--summary", "Issue B", "--project", "proj-b"],
            env=env,
        )
        result = runner.invoke(main, ["feedback", "triage"], env=env)
        assert result.exit_code == 0
        assert "command:discuss" in result.output

    def test_triage_with_target_glob(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:discuss", "--summary", "A"],
            env=env,
        )
        runner.invoke(
            main,
            ["feedback", "add", "--target", "template:discussion", "--summary", "B"],
            env=env,
        )
        result = runner.invoke(main, ["feedback", "triage", "--target", "command:*"], env=env)
        assert result.exit_code == 0
        assert "command:discuss" in result.output
        assert "template:discussion" not in result.output


class TestFeedbackReport:
    def test_report_generates_markdown(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:discuss", "--summary", "Test issue"],
            env=env,
        )
        result = runner.invoke(main, ["feedback", "report"], env=env)
        assert result.exit_code == 0
        assert "Feedback Report" in result.output
        assert "Test issue" in result.output

    def test_report_empty(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(main, ["feedback", "report"], env=env)
        assert result.exit_code == 0
        assert "No feedback entries" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback_cli.py -v -k "TestFeedbackTriage or TestFeedbackReport"`
Expected: FAIL — `Error: No such command 'triage'`

- [ ] **Step 3: Add triage and report commands to cli.py**

Add after the `feedback_update` command:

```python
@feedback.command("triage")
@click.option("--target", default=None, help="Filter by target (fnmatch glob)")
def feedback_triage(target: str | None) -> None:
    """Show open entries grouped by target for triage."""
    from science_tool.feedback import group_for_triage

    fb_dir = _get_feedback_dir()
    groups = group_for_triage(fb_dir, target=target)

    if not groups:
        click.echo("No open feedback entries.")
        return

    for target_key, group in groups.items():
        n_projects = len(group["projects"])
        n_entries = len(group["entries"])
        total_recur = group["total_recurrence"]
        projects_str = ", ".join(sorted(group["projects"])) if group["projects"] else "unknown"
        click.echo(f"\n## {target_key}  ({n_entries} entries, {total_recur} recurrences, {n_projects} projects: {projects_str})")
        for entry in group["entries"]:
            click.echo(f"  - {entry.id} [{entry.category}] {entry.summary}")


@feedback.command("report")
@click.option("--status", default=None, help="Filter by status")
@click.option("--project", default=None, help="Filter by project")
def feedback_report(status: str | None, project: str | None) -> None:
    """Generate a markdown report of feedback entries."""
    from science_tool.feedback import render_report

    fb_dir = _get_feedback_dir()
    report = render_report(fb_dir, status=status, project=project)
    click.echo(report)
```

- [ ] **Step 4: Run all feedback CLI tests**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_feedback_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/ -v --timeout=30`
Expected: All PASS (no regressions in existing tests)

- [ ] **Step 6: Commit**

```bash
cd /mnt/ssd/Dropbox/science/science-tool
git add src/science_tool/cli.py tests/test_feedback_cli.py
git commit -m "feat(feedback): add CLI commands — triage and report"
```

---

### Task 8: Update process reflection in all 16 command files

**Files:**
- Modify: `commands/interpret-results.md`
- Modify: `commands/next-steps.md`
- Modify: `commands/discuss.md`
- Modify: `commands/pre-register.md`
- Modify: `commands/plan-pipeline.md`
- Modify: `commands/review-pipeline.md`
- Modify: `commands/research-paper.md`
- Modify: `commands/research-topic.md`
- Modify: `commands/bias-audit.md`
- Modify: `commands/add-hypothesis.md`
- Modify: `commands/compare-hypotheses.md`
- Modify: `commands/critique-approach.md`
- Modify: `commands/find-datasets.md`
- Modify: `commands/search-literature.md`
- Modify: `commands/sketch-model.md`
- Modify: `commands/specify-model.md`

- [ ] **Step 1: Replace process reflection in all 16 commands**

For each command file, find the `## Process Reflection` section (from that header to the end of the file) and replace it with:

```markdown
## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:<this-command>" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead
```

Replace `<this-command>` with the actual command name in each file (e.g., `interpret-results`, `next-steps`, `discuss`, etc.).

Two format variants exist in the current files:
- **Full variant** (~35 lines with markdown code block template): `interpret-results`, `next-steps`, `discuss`, `pre-register`, `plan-pipeline`, `review-pipeline`, `research-paper`, `research-topic`, `bias-audit`, `find-datasets`, `search-literature`
- **Minimal variant** (~5 lines): `add-hypothesis`, `compare-hypotheses`, `critique-approach`, `sketch-model`, `specify-model`

Both are replaced with the same new block above.

- [ ] **Step 2: Verify a sample of files**

Read the `## Process Reflection` section from 3 files (one from each variant + one from the minimal set) to confirm the replacement is correct:
- `commands/interpret-results.md`
- `commands/sketch-model.md`
- `commands/bias-audit.md`

- [ ] **Step 3: Commit**

```bash
cd /mnt/ssd/Dropbox/science
git add commands/*.md
git commit -m "commands: update process reflection to use science-tool feedback add"
```
