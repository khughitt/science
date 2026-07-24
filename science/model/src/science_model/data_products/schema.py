"""The canonical data-product term catalog contract.

One owner for data-product terms and their `broader` DAG. Plain Pydantic, mirroring
ontologies. Models are CLOSED (extra="forbid") so a typo'd key fails loudly instead
of vanishing. Structural checks are the models'; semantic (dup/DAG) checks are
`build_catalog`'s, which raises CatalogError at the loader boundary -- so callers
get one clean exception type, not a Pydantic wrapper.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_ID_PATTERN = r"^data-product:[a-z0-9][a-z0-9-]*$"


class CatalogError(ValueError):
    """The data-product catalog is semantically invalid (dup id or broken broader DAG)."""


class DataProductTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=_ID_PATTERN)
    label: str = Field(min_length=1)
    assay: str = Field(min_length=1)
    technology: str = ""
    broader: list[str] = Field(default_factory=list)


class DataProductCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"]
    terms: list[DataProductTerm]

    @property
    def by_id(self) -> dict[str, DataProductTerm]:
        return {t.id: t for t in self.terms}

    def descends(self, child_id: str, ancestor_id: str) -> bool:
        index = self.by_id
        if child_id not in index or ancestor_id not in index:
            return False
        seen: set[str] = set()
        stack = [child_id]
        while stack:
            current = stack.pop()
            if current == ancestor_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(index[current].broader)
        return False


def build_catalog(payload: dict) -> DataProductCatalog:
    """Validate structure (Pydantic) then integrity (CatalogError), returning the catalog."""
    catalog = DataProductCatalog.model_validate(payload)
    index: dict[str, DataProductTerm] = {}
    for term in catalog.terms:
        if term.id in index:
            raise CatalogError(f"duplicate term id {term.id!r}")
        index[term.id] = term
    for term in catalog.terms:
        for parent in term.broader:
            if parent == term.id:
                raise CatalogError(f"term {term.id!r} lists itself as broader")
            if parent not in index:
                raise CatalogError(f"term {term.id!r} broader {parent!r} does not resolve")
    _reject_cycles(index)
    return catalog


def _reject_cycles(index: dict[str, DataProductTerm]) -> None:
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {tid: WHITE for tid in index}

    def visit(tid: str, path: list[str]) -> None:
        colour[tid] = GREY
        for parent in index[tid].broader:
            if colour[parent] == GREY:
                raise CatalogError(f"broader cycle: {' -> '.join([*path, tid, parent])}")
            if colour[parent] == WHITE:
                visit(parent, [*path, tid])
        colour[tid] = BLACK

    for tid in index:
        if colour[tid] == WHITE:
            visit(tid, [])
