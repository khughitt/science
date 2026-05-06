"""Pydantic models for research package cell definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class NarrativeCell(BaseModel):
    """Markdown prose cell. Content is a file path within the package."""

    type: Literal["narrative"]
    content: str


class DataTableCell(BaseModel):
    """Sortable data table rendered from a CSV resource."""

    type: Literal["data-table"]
    resource: str
    columns: list[str] | None = None
    caption: str | None = None


class FigureCell(BaseModel):
    """Static image with caption."""

    type: Literal["figure"]
    ref: str


class VegaLiteCell(BaseModel):
    """Interactive Vega-Lite chart."""

    type: Literal["vegalite"]
    ref: str
    caption: str | None = None


class CodeReferenceCell(BaseModel):
    """Collapsible code excerpt with optional GitHub permalink."""

    type: Literal["code-reference"]
    excerpt: str
    description: str | None = None


class ProvenanceCell(BaseModel):
    """Auto-rendered provenance summary from package metadata."""

    type: Literal["provenance"]


Cell = NarrativeCell | DataTableCell | FigureCell | VegaLiteCell | CodeReferenceCell | ProvenanceCell

_CELL_TYPE_MAP: dict[str, type[BaseModel]] = {
    "narrative": NarrativeCell,
    "data-table": DataTableCell,
    "figure": FigureCell,
    "vegalite": VegaLiteCell,
    "code-reference": CodeReferenceCell,
    "provenance": ProvenanceCell,
}


def parse_cells(raw: list[dict]) -> list[Cell]:
    """Parse a list of raw cell dicts into typed Cell instances."""
    cells: list[Cell] = []
    for item in raw:
        cell_type = item.get("type")
        model_class = _CELL_TYPE_MAP.get(cell_type) if isinstance(cell_type, str) else None
        if model_class is None:
            raise ValueError(f"Unknown cell type: {cell_type}")
        cells.append(model_class(**item))  # type: ignore[arg-type]
    return cells
