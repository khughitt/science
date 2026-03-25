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
