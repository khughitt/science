"""Shared graph export payload types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# V1 terminology:
# - base edge: one exported (subject, predicate, object, layer) edge
# - supporting claim: one proposition attached to a base edge


class GraphExportNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    type: str | None = None
    graph_layer: str | None = None
    status: str | None = None
    confidence: float | None = None
    source_refs: list[str] = Field(default_factory=list)


class GraphExportEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    subject: str
    predicate: str
    object: str
    graph_layer: str | None = None
    provenance: str | None = None
    claim_ids: list[str] = Field(default_factory=list)


class GraphExportLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    node_count: int = 0
    edge_count: int = 0
    default_visible: bool = True


class GraphExportScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    label: str
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class GraphExportOverlays(BaseModel):
    model_config = ConfigDict(extra="forbid")

    causal: dict[str, object] = Field(default_factory=dict)
    evidence: dict[str, object] = Field(default_factory=dict)


class GraphExportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    nodes: list[GraphExportNode]
    edges: list[GraphExportEdge]
    layers: list[GraphExportLayer]
    scopes: list[GraphExportScope]
    overlays: GraphExportOverlays = Field(default_factory=GraphExportOverlays)
    warnings: list[str] = Field(default_factory=list)
