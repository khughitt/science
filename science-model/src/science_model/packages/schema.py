"""Pydantic models for Frictionless research package descriptors."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResourceSchema(BaseModel):
    """A tabular data resource within the package."""

    name: str
    path: str
    schema_: dict[str, Any] | None = Field(None, alias="schema")
    model_config = {"populate_by_name": True}


class FigureRef(BaseModel):
    """A static figure (image) included in the package."""

    name: str
    path: str
    caption: str


class CodeExcerpt(BaseModel):
    """An extracted code snippet with source provenance."""

    name: str
    path: str
    source: str
    lines: tuple[int, int]
    github_permalink: str = ""


class VegaLiteSpec(BaseModel):
    """A Vega-Lite visualization specification."""

    name: str
    path: str
    caption: str | None = None


class ProvenanceInput(BaseModel):
    """An input file tracked for freshness via SHA-256."""

    path: str
    sha256: str


class Provenance(BaseModel):
    """Execution provenance for a research package."""

    workflow: str
    config: str
    last_run: str
    git_commit: str
    repository: str
    inputs: list[ProvenanceInput]
    scripts: list[str]


class ResearchExtension(BaseModel):
    """Custom extension block within the Frictionless descriptor."""

    target_route: str | None = None
    cells: str
    figures: list[FigureRef] = Field(default_factory=list)
    vegalite_specs: list[VegaLiteSpec] = Field(default_factory=list)
    code_excerpts: list[CodeExcerpt] = Field(default_factory=list)
    provenance: Provenance


class ResearchPackageDescriptor(BaseModel):
    """A Frictionless data package with science research extensions."""

    name: str
    title: str
    profile: Literal["science-research-package"]
    version: str
    resources: list[ResourceSchema]
    research: ResearchExtension
