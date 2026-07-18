"""Typed identity metadata for Science entities."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class EntityScope(StrEnum):
    """Scope of an entity's canonical identity."""

    PROJECT = "project"
    SHARED = "shared"


class EntityClass(StrEnum):
    """High-level taxonomic classification of an entity kind.

    Distinguishes which kinds carry continuous belief (epistemic), which
    represent operational artifacts produced by project work (operational),
    and which name external things that rarely change (reference).

    Used by the freshness engine to decide whether an entity participates
    in `bears_on` propagation: only EPISTEMIC entities are valid targets.
    """

    EPISTEMIC = "epistemic"
    OPERATIONAL = "operational"
    REFERENCE = "reference"


class CurationScope(StrEnum):
    """Whether — and how — a kind's records may carry review state (design §5).

    An axis of its own, authored per kind and derived from NEITHER `EntityClass`
    (calibrated for `bears_on` propagation) NOR the deleted closed list. `epistemic`
    asks "given new evidence, is this still my belief?"; `correspondence` asks "does
    this record still correspond to reality — did it ship?"; `none` means there is
    nothing to review.
    """

    EPISTEMIC = "epistemic"
    CORRESPONDENCE = "correspondence"
    NONE = "none"


class ExternalId(BaseModel):
    """Structured external identifier attached to an entity."""

    source: str
    id: str
    curie: str
    provenance: str
    version: str | None = None
