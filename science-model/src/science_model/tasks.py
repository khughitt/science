"""Task data models."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    """Task status values used by science-tool."""

    PROPOSED = "proposed"
    ACTIVE = "active"
    DONE = "done"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
    RETIRED = "retired"


class Task(BaseModel):
    """A research task."""

    id: str
    project: str = ""
    title: str
    description: str = ""
    type: str = ""
    priority: str = "P2"
    status: str = TaskStatus.PROPOSED
    blocked_by: list[str] = []
    related: list[str] = []
    group: str = ""
    artifacts: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    created: date = Field(default_factory=date.today)
    completed: date | None = None


class TaskCreate(BaseModel):
    """Input for creating a new task."""

    title: str
    type: str = ""
    priority: str = "P2"
    related: list[str] = []
    blocked_by: list[str] = []
    group: str = ""
    description: str = ""


class TaskUpdate(BaseModel):
    """Partial update for a task."""

    title: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    type: str | None = None
    related: list[str] | None = None
    blocked_by: list[str] | None = None
    group: str | None = None
