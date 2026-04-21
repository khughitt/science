"""Non-blocking ontology adoption suggestions during graph build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from science_model.ontologies import load_catalog, load_registry
from science_model.ontologies.schema import OntologyCatalog


class _EntityLike(Protocol):
    """Duck-typed view of the entity fields suggest_ontologies reads.

    Kept narrow so tests can pass lightweight stand-ins; production passes
    real Entity / ProjectEntity instances which satisfy this structurally.
    """

    ontology_terms: list[str]

    @property
    def type(self) -> object: ...


@dataclass(frozen=True)
class OntologySuggestion:
    """A suggestion to declare an undeclared ontology."""

    ontology_name: str
    reason: str
    entity_count: int


def suggest_ontologies(
    entities: Sequence[_EntityLike],
    declared_ontologies: list[str],
) -> list[OntologySuggestion]:
    """Scan entities for signals that suggest undeclared ontologies.

    Checks CURIE prefix matches in ontology_terms and entity kind matches
    against all registered ontologies that are not already declared.
    """
    registry = load_registry()
    undeclared = [entry for entry in registry if entry.name not in declared_ontologies]
    if not undeclared:
        return []

    suggestions: list[OntologySuggestion] = []

    for entry in undeclared:
        catalog = load_catalog(entry)
        prefix_matches = _count_prefix_matches(entities, catalog)
        kind_matches = _count_kind_matches(entities, catalog)
        total = prefix_matches + kind_matches

        if total > 0:
            parts: list[str] = []
            if prefix_matches:
                parts.append(f"{prefix_matches} entities with matching CURIE prefixes")
            if kind_matches:
                parts.append(f"{kind_matches} entities with matching kinds")
            suggestions.append(
                OntologySuggestion(
                    ontology_name=entry.name,
                    reason="; ".join(parts),
                    entity_count=total,
                )
            )

    suggestions.sort(key=lambda s: s.entity_count, reverse=True)
    return suggestions


def _count_prefix_matches(entities: Sequence[_EntityLike], catalog: OntologyCatalog) -> int:
    """Count entities whose ontology_terms contain CURIEs matching the catalog's curie_prefixes."""
    catalog_prefixes: set[str] = set()
    for et in catalog.entity_types:
        catalog_prefixes.update(p.lower() for p in et.curie_prefixes)

    if not catalog_prefixes:
        return 0

    count = 0
    for entity in entities:
        for term in entity.ontology_terms:
            if ":" in term:
                prefix, _ = term.split(":", 1)
                if prefix.lower() in catalog_prefixes:
                    count += 1
                    break
    return count


def _count_kind_matches(entities: Sequence[_EntityLike], catalog: OntologyCatalog) -> int:
    """Count entities whose kind matches an entity type in the catalog."""
    catalog_type_names = {et.name for et in catalog.entity_types}
    count = 0
    for entity in entities:
        type_value = _type_value(entity.type)
        if type_value in catalog_type_names:
            count += 1
    return count


def _type_value(value: object) -> str | None:
    maybe_value = getattr(value, "value", None)
    if isinstance(maybe_value, str):
        return maybe_value
    return None
