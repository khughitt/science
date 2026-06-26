"""ReadinessResolver: tool-layer entity-lookup + cycle-guarded readiness resolution.

Constructed per CLI invocation with a snapshot of the local entity store.
Caches resolved readiness within its own lifetime so the same blocker
referenced by N tasks costs one resolution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from science_model.entities import ProjectEntity, Readiness


class ReadinessResolver:
    """Resolves entity references to Readiness, guarding against cycles."""

    def __init__(self, lookup: Callable[[str], ProjectEntity | None]) -> None:
        self._lookup = lookup
        self._visiting: set[str] = set()
        self._cache: dict[str, Readiness] = {}

    def resolve_ref(self, ref: str) -> Readiness:
        cached = self._cache.get(ref)
        if cached is not None:
            return cached
        if ref in self._visiting:
            return Readiness(ready=False, state="cycle", detail=f"derivation cycle through {ref}")
        entity = self._lookup(ref)
        if entity is None:
            return Readiness(ready=False, state="unresolved", detail=f"unknown entity {ref}")
        self._visiting.add(ref)
        try:
            result = entity.readiness(resolver=self)
        finally:
            self._visiting.discard(ref)
        self._cache[ref] = result
        return result


def make_local_resolver(project_root: Path | None = None) -> ReadinessResolver:
    """Construct a ReadinessResolver backed by the local project's entity index."""
    from science_tool.entities import load_local_entity_index

    root = project_root or Path.cwd()
    index = load_local_entity_index(root)
    return ReadinessResolver(lookup=index.get)


def make_project_entity_lookup(project_root: Path | None = None) -> Callable[[str], ProjectEntity | None]:
    """Return a lookup for local refs and declared peer-scoped refs.

    Local refs use the canonical ``<kind>:<id>`` shape. Declared peer refs use
    ``<peer-id>:<kind>:<id>`` and are resolved by loading that peer's local
    entity index, then stripping the peer scope before lookup.
    """
    from science_tool.entities import load_local_entity_index
    from science_tool.peers import PeerNotFound, PeerUnresolved, load_peer_entity_index
    from science_tool.peers import make_local_resolver as make_peer_resolver

    root = project_root or Path.cwd()
    local_index = load_local_entity_index(root)
    try:
        peer_resolver = make_peer_resolver(root)
    except FileNotFoundError:
        peer_resolver = None
    except PeerUnresolved as exc:
        raise ValueError(str(exc)) from exc
    peer_indexes: dict[str, dict[str, ProjectEntity]] = {}

    def lookup(ref: str) -> ProjectEntity | None:
        local = local_index.get(ref)
        if local is not None:
            return local

        parts = ref.split(":", 2)
        if len(parts) != 3:
            return None
        if peer_resolver is None:
            return None
        peer_id, kind, slug = parts
        if peer_id not in peer_resolver.known_ids() or not kind or not slug:
            return None

        if peer_id not in peer_indexes:
            try:
                peer_indexes[peer_id] = load_peer_entity_index(peer_resolver, peer_id)
            except (PeerNotFound, PeerUnresolved, FileNotFoundError):
                return None
        return peer_indexes[peer_id].get(f"{kind}:{slug}")

    return lookup


def make_project_resolver(project_root: Path | None = None) -> ReadinessResolver:
    """Construct a resolver backed by the local project plus declared peers."""
    return ReadinessResolver(lookup=make_project_entity_lookup(project_root))
