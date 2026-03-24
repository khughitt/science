"""Pydantic models for ontology term catalogs."""

from __future__ import annotations

from pydantic import BaseModel


class OntologyTermType(BaseModel):
    """An entity type defined by an external ontology."""

    id: str
    name: str
    description: str
    curie_prefixes: list[str] = []
    recommended: bool = False


class OntologyPredicate(BaseModel):
    """A relation predicate defined by an external ontology."""

    id: str
    name: str
    description: str
    domain: str
    range: str
    recommended: bool = False


class OntologyCatalog(BaseModel):
    """A loaded ontology term catalog."""

    ontology: str
    version: str
    prefix: str
    prefix_uri: str
    entity_types: list[OntologyTermType]
    predicates: list[OntologyPredicate]


class OntologyRegistryEntry(BaseModel):
    """An entry in the built-in ontology registry."""

    name: str
    version: str
    source_url: str
    description: str
    catalog_path: str
