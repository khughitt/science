"""Feedback entry CRUD, filtering, and deduplication for science-tool.

Stores structured feedback as individual YAML files in ~/.config/science/feedback/.
"""

from __future__ import annotations

import re
from datetime import date
from fnmatch import fnmatch
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
