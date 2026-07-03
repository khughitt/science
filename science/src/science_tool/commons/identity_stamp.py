"""Derived datapackage stamp helpers for dataset identity_context."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel


def derive_stamp(entity_identity: Any) -> dict[str, Any]:
    """Return a JSON/YAML-safe copy of an entity identity_context block."""
    if isinstance(entity_identity, BaseModel):
        dumped = entity_identity.model_dump(mode="json", by_alias=True, exclude_none=True)
        if not isinstance(dumped, dict):
            raise TypeError("entity_identity model must dump to a mapping")
        return dumped
    if isinstance(entity_identity, dict):
        return deepcopy(entity_identity)
    raise TypeError("entity_identity must be a mapping or Pydantic model")


def stamp_agrees(entity_identity: Any, datapackage: dict[str, Any]) -> bool:
    """Return whether a present datapackage identity stamp matches the entity.

    Missing stamps are intentionally ignored for P1.4 adoption: the stamp is
    derived/read-only metadata, never authoritative.
    """
    science = datapackage.get("science")
    if not isinstance(science, dict) or "identity_context" not in science:
        return True
    return science["identity_context"] == derive_stamp(entity_identity)
