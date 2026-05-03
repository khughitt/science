"""ReadinessResolver: tool-layer entity-lookup + cycle-guarded readiness resolution.

Constructed per CLI invocation with a snapshot of the local entity store.
Caches resolved readiness within its own lifetime so the same blocker
referenced by N tasks costs one resolution.
"""
from __future__ import annotations

from typing import Callable

from science_model.entities import Entity, Readiness


class ReadinessResolver:
    """Resolves entity references to Readiness, guarding against cycles."""

    def __init__(self, lookup: Callable[[str], Entity | None]) -> None:
        self._lookup = lookup
        self._visiting: set[str] = set()
        self._cache: dict[str, Readiness] = {}

    def resolve_ref(self, ref: str) -> Readiness:
        cached = self._cache.get(ref)
        if cached is not None:
            return cached
        if ref in self._visiting:
            return Readiness(
                ready=False, state="cycle", detail=f"derivation cycle through {ref}"
            )
        entity = self._lookup(ref)
        if entity is None:
            return Readiness(
                ready=False, state="unresolved", detail=f"unknown entity {ref}"
            )
        self._visiting.add(ref)
        try:
            result = entity.readiness(resolver=self)
        finally:
            self._visiting.discard(ref)
        self._cache[ref] = result
        return result
