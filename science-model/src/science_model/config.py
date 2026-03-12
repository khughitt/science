"""Dashboard configuration models."""

from __future__ import annotations

from pydantic import BaseModel


class LodWeights(BaseModel):
    """Weights for the LoD importance scoring function."""

    degree: float = 0.4
    recency: float = 0.3
    status: float = 0.2
    evidence_density: float = 0.1


class DashboardConfig(BaseModel):
    """Dashboard configuration."""

    projects: list[str]
    palette: str = "onedark"
    domain_colors: dict[str, str] = {}
    lod_weights: LodWeights = LodWeights()
    sqlite_path: str | None = None


class ConfigUpdate(BaseModel):
    """Partial config update."""

    projects: list[str] | None = None
    palette: str | None = None
    domain_colors: dict[str, str] | None = None
    lod_weights: LodWeights | None = None
    sqlite_path: str | None = None
