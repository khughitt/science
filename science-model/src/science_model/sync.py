"""Provenance model for cross-project sync-propagated entities."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class SyncSource(BaseModel):
    """Provenance marker for sync-propagated entities."""

    project: str
    entity_id: str
    sync_date: date
