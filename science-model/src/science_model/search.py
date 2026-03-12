"""Search and filter models."""

from __future__ import annotations

from pydantic import BaseModel

from science_model.entities import Entity


class Filters(BaseModel):
    """Query filters for entity listing."""

    project: str | None = None
    entity_type: str | None = None
    status: str | None = None
    domain: str | None = None
    tags: list[str] | None = None


class SearchResult(BaseModel):
    """A single search result."""

    entity: Entity
    score: float
    highlights: list[str]
