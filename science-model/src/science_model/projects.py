"""Project data models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel

from science_model.entities import Entity
from science_model.tasks import Task


class GraphSummary(BaseModel):
    """Summary statistics for a project's knowledge graph."""

    node_count: int
    edge_count: int
    top_domains: list[str]


class Project(BaseModel):
    """Summary of a Science project."""

    slug: str
    name: str
    path: str
    summary: str | None = None
    status: str | None = None
    aspects: list[str]
    tags: list[str]
    entity_counts: dict[str, int]
    created: date | None = None
    last_modified: date | None = None
    last_activity: datetime | None = None
    staleness_days: int | None = None


class ProjectDetail(Project):
    """Full project detail including top entities."""

    hypotheses: list[Entity]
    questions: list[Entity]
    tasks: list[Task]
    graph_summary: GraphSummary
