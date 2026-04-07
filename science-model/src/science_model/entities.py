"""Entity data models for Science research projects."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from science_model.sync import SyncSource


class EntityType(StrEnum):
    """Known entity types across Science projects."""

    CONCEPT = "concept"
    HYPOTHESIS = "hypothesis"
    QUESTION = "question"
    PROPOSITION = "proposition"
    OBSERVATION = "observation"
    INQUIRY = "inquiry"
    TOPIC = "topic"
    INTERPRETATION = "interpretation"
    DISCUSSION = "discussion"
    MODEL = "model"
    PLAN = "plan"
    ASSUMPTION = "assumption"
    TRANSFORMATION = "transformation"
    VARIABLE = "variable"
    DATASET = "dataset"
    METHOD = "method"
    EXPERIMENT = "experiment"
    ARTICLE = "article"
    WORKFLOW = "workflow"
    WORKFLOW_RUN = "workflow-run"
    WORKFLOW_STEP = "workflow-step"
    DATA_PACKAGE = "data-package"
    FINDING = "finding"
    STORY = "story"
    PAPER = "paper"
    UNKNOWN = "unknown"


class EntityUpdate(BaseModel):
    """Partial update for entity metadata (written back to frontmatter)."""

    status: str | None = None
    tags: list[str] | None = None


class Entity(BaseModel):
    """A research entity parsed from frontmatter or the knowledge graph."""

    id: str
    canonical_id: str = ""
    type: EntityType
    title: str
    status: str | None = None
    project: str
    profile: str = "core"
    domain: str | None = None
    tags: list[str]
    ontology_terms: list[str]
    created: date | None = None
    updated: date | None = None
    related: list[str]
    source_refs: list[str]
    content_preview: str
    content: str = ""
    file_path: str
    # Type-specific
    maturity: str | None = None
    confidence: float | None = None
    datasets: list[str] | None = None
    aliases: list[str] = Field(default_factory=list)
    pre_registered: bool = False
    pre_registered_date: date | None = None
    sync_source: SyncSource | None = None

    @model_validator(mode="after")
    def _fill_derived_defaults(self) -> "Entity":
        if not self.canonical_id:
            self.canonical_id = self.id
        return self
