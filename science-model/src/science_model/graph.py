"""Knowledge graph data models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class GraphNode(BaseModel):
    """A node in the knowledge graph for visualization."""

    id: str
    label: str
    type: str
    domain: str | None = None
    importance: float = 0.0
    status: str | None = None
    maturity: str | None = None
    confidence: float | None = None
    updated: date | None = None
    graph_layer: str
    inquiry: str | None = None
    boundary_role: str | None = None


class GraphEdge(BaseModel):
    """An edge in the knowledge graph for visualization."""

    source: str
    target: str
    predicate: str
    graph_layer: str
    provenance: str | None = None


class GraphData(BaseModel):
    """Complete graph payload for the frontend."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    domains: dict[str, str]
    lod: float
    total_nodes: int


class GraphSummary(BaseModel):
    """Summary statistics for a project's knowledge graph."""

    node_count: int
    edge_count: int
    top_domains: list[str]
