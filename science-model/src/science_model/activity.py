"""Activity feed models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityItem(BaseModel):
    """A single activity event."""

    project: str
    entity_id: str | None = None
    entity_type: str | None = None
    title: str
    action: str
    timestamp: datetime
    detail: str | None = None
