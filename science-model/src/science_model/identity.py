"""Typed identity metadata for Science entities."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class EntityScope(StrEnum):
    """Scope of an entity's canonical identity."""

    PROJECT = "project"
    SHARED = "shared"


class ExternalId(BaseModel):
    """Structured external identifier attached to an entity."""

    source: str
    id: str
    curie: str
    provenance: str
    version: str | None = None
