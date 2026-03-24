# Ontology Consumption & Knowledge Model Redesign — Design Spec

**Date:** 2026-03-24
**Status:** Draft

## Problem

The current `BIO_PROFILE` hand-builds 4 entity kinds and 3 relations that
duplicate a tiny subset of what biolink-model already defines. This approach
doesn't scale: every new domain requires a custom profile, biases toward current
projects, and ignores the extensive community ontologies already available.

Meanwhile, no project actually populates bio-typed entities — the profile exists
as schema but provides no practical value. Cross-project sync found zero shared
domain entities because projects don't model domain concepts precisely.

## Goal

Replace the hand-built domain profile system with ontology consumption: science
uses existing community ontologies (starting with biolink-model) as vocabulary
for entity types and relation predicates. This gives projects precise, standard
domain vocabulary without reinventing what the community has already built.

## Knowledge Model Definition

A science project's **knowledge model** = internal (user-authored) + external
(community-authored, read-only reference).

### Internal layers

| Layer | Profile | Purpose |
|---|---|---|
| `core` | `CORE_PROFILE` | Science-native types: hypothesis, question, claim, evidence, etc. |
| `shared` | auto-loaded from registry | Cross-project user entities/relations |
| `local` | `LOCAL_PROFILE` | Project-specific extensions |

### External layer

| Layer | Source | Purpose |
|---|---|---|
| `domain` | declared ontologies | Vocabulary for domain entity types and relation predicates |

### The boundary rule

**Use external types/predicates freely; don't import external assertions.**

User entities use ontology terms as their *types* (e.g., kind = `biolink:Gene`)
and *predicates* (e.g., `biolink:interacts_with`). But external knowledge graph
assertions (e.g., "TP53 interacts_with MDM2") are never auto-imported. The user
authors all claims and evidence themselves.

Ontologies provide vocabulary. Users provide knowledge.

---

## 1. Ontology Registry & Term Catalogs

### Built-in registry

`science-model` ships with a registry of known ontologies:

```yaml
# science_model/ontologies/registry.yaml
ontologies:
  - name: biolink
    version: "4.3.7"
    source_url: "https://github.com/biolink/biolink-model"
    description: "Biolink Model — biomedical and translational science data model"
    catalog_path: "biolink/catalog.yaml"
```

Initially just biolink. More ontologies can be added in future `science-model`
releases by adding entries and bundling catalogs.

### Term catalog format

Each ontology has a YAML catalog bundled as package data:

```yaml
# science_model/ontologies/biolink/catalog.yaml
ontology: biolink
version: "4.3.7"
prefix: "biolink"
prefix_uri: "https://w3id.org/biolink/vocab/"

entity_types:
  - id: "biolink:Gene"
    name: "gene"
    description: "A region that encodes a functional transcript"
    curie_prefixes: ["NCBIGene", "ENSEMBL", "HGNC"]
    recommended: true
  - id: "biolink:Protein"
    name: "protein"
    description: "A gene product composed of amino acids"
    curie_prefixes: ["UniProtKB", "PR"]
    recommended: true
  - id: "biolink:SequenceVariant"
    name: "sequence_variant"
    description: "A genomic feature with sequence alteration"
    curie_prefixes: ["CLINVAR", "DBSNP"]
    recommended: false
  # ... full biolink entity type list

predicates:
  - id: "biolink:interacts_with"
    name: "interacts_with"
    description: "Holds between entities that directly or indirectly interact"
    domain: "biolink:NamedThing"
    range: "biolink:NamedThing"
    recommended: true
  # ... full biolink predicate list
```

### Full catalog with recommended subset

The catalog includes the **full** biolink entity type and predicate lists
(extracted programmatically from the LinkML source). A `recommended: true` field
marks the commonly-used terms (~30-40 types, ~20-30 predicates) that the
suggestion system highlights.

The full list is always available for validation — a user who wants
`biolink:Transcript` or `biolink:SequenceVariant` can use them without waiting
for a release. Suggestions only reference `recommended: true` terms.

### Pydantic models

```python
class OntologyTermType(BaseModel):
    """An entity type defined by an external ontology."""
    id: str                          # "biolink:Gene"
    name: str                        # "gene"
    description: str
    curie_prefixes: list[str] = []   # valid ID prefixes
    recommended: bool = False

class OntologyPredicate(BaseModel):
    """A relation predicate defined by an external ontology."""
    id: str                          # "biolink:interacts_with"
    name: str                        # "interacts_with"
    description: str
    domain: str                      # "biolink:NamedThing"
    range: str                       # "biolink:NamedThing"
    recommended: bool = False

class OntologyCatalog(BaseModel):
    """A loaded ontology term catalog."""
    ontology: str                    # "biolink"
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
```

---

## 2. science.yaml Schema Changes

### New schema

```yaml
name: seq-feats
ontologies: [biolink]
knowledge_profiles:
  local: local
```

- **`ontologies`** — list of declared external ontology names. Validated against
  the built-in registry. Optional (defaults to empty list).
- **`curated`** — removed entirely from `knowledge_profiles`.

### Shared profile becomes implicit

The `shared` profile (cross-project registry) is no longer declared in
`science.yaml`. It loads automatically if the registry exists at
`~/.config/science/registry/manifest.yaml`. Like `core`, it's infrastructure —
not a per-project opt-in.

---

## 3. Graph Layer Changes

### Flat `layer/domain`

All ontology-typed entities go into a single `layer/domain` layer, regardless
of which ontology defines their type:

| Layer | Contents |
|---|---|
| `layer/core` | Science-native entities |
| `layer/domain` | All domain entities (biolink-typed, GO-typed, etc.) |
| `layer/shared` | Cross-project shared entities |
| `layer/local` | Project-specific extensions |
| `layer/bridge` | External term references |
| `layer/provenance` | Confidence, epistemic status, parameter bindings |
| `layer/causal` | Causal structure |
| `layer/datasets` | Dataset linkage |

The ontology a type comes from is tracked via the CURIE prefix on each entity,
not the graph layer. This avoids layer proliferation when multiple ontologies are
declared.

**Breaking change:** existing `layer/domain/bio` URIs in `graph.trig` files
become `layer/domain`. Projects must rebuild their graphs.

### Entity kind routing during graph build

For each entity:
1. Kind matches a `core` entity kind → `layer/core`
2. Kind matches a declared ontology entity type → `layer/domain`
3. Kind matches a `shared` entity kind → `layer/shared`
4. Kind matches a `local` entity kind → `layer/local`
5. No match → warning (unknown entity kind)

---

## 4. Ontology Suggestion Mechanism

### Primary: during `graph build`

After loading project sources, before materialization:

```python
def suggest_ontologies(
    entities: list[SourceEntity],
    declared_ontologies: list[str],
) -> list[OntologySuggestion]:
```

Scans entities for two signals:

1. **CURIE prefix match** — entity `ontology_terms` contain CURIEs whose
   prefixes match a known ontology's `curie_prefixes` (e.g., `NCBIGene:7157` →
   biolink). Checks all registered ontologies, not just declared ones.

2. **Kind match** — entity `kind` matches an undeclared ontology's entity type
   name (e.g., `type: gene` when biolink isn't declared).

Output is a non-blocking suggestion:

```
Ontology suggestion: Found 3 entities referencing NCBIGene/ENSEMBL terms.
  Consider adding `ontologies: [biolink]` to science.yaml.
```

### Secondary: command prompt guidance

`/science:status` and `/science:next-steps` prompts include guidance to check
for ontology adoption opportunities.

---

## 5. What Gets Removed

### `BIO_PROFILE`

- Delete `science-model/src/science_model/profiles/bio.py`
- Remove `BIO_PROFILE` from `profiles/__init__.py` exports
- Remove bio-related tests from `test_profile_manifests.py`
- Remove `BIO_PROFILE` from `__init__.py` re-exports

### `curated` field

- Remove `curated: list[str]` from `KnowledgeProfiles` model in `sources.py`
- Remove all `curated`-related logic in `load_project_sources()` and
  `_read_project_config()`
- Remove `curated` handling in `known_kinds()`

### `_external_profile()` in materialize.py

This function currently checks `if "bio" in curated_profiles` to assign CURIEs
to the bio profile. Replace with ontology-based assignment: check if the CURIE
prefix matches any declared ontology's `curie_prefixes`.

---

## 6. Affected Files

### New files

```
science-model/src/science_model/ontologies/__init__.py    # load functions
science-model/src/science_model/ontologies/schema.py      # Pydantic models
science-model/src/science_model/ontologies/registry.yaml  # built-in registry
science-model/src/science_model/ontologies/biolink/       # biolink catalog
  catalog.yaml
science-model/tests/test_ontologies.py                    # ontology loading tests
science-tool/tests/test_ontology_suggest.py               # suggestion tests
```

### Deleted files

```
science-model/src/science_model/profiles/bio.py
```

### Modified files

```
science-model/src/science_model/profiles/__init__.py     # remove BIO_PROFILE
science-model/src/science_model/__init__.py              # update exports
science-model/tests/test_profile_manifests.py            # remove bio tests

science-tool/src/science_tool/graph/sources.py           # remove curated, add ontologies
science-tool/src/science_tool/graph/materialize.py       # update _external_profile, layer URIs
science-tool/src/science_tool/cli.py                     # add suggestion output in graph build

commands/create-project.md                               # update science.yaml template
commands/create-graph.md                                 # update for ontologies
commands/status.md                                       # add ontology suggestion guidance
commands/next-steps.md                                   # add ontology suggestion guidance
```

### Per-project migration

For each of `seq-feats`, `3d-attention-bias`, `natural-systems`, `cats`:
1. Update `science.yaml`: remove `curated`, add `ontologies` where appropriate
2. Rebuild graph with `science-tool graph build`

---

## 7. Known Limitations (v1)

- **No ontology hierarchy** — term catalog is flat (no `is_a` / subclass
  reasoning). Entity type `biolink:Protein` is not automatically recognized as a
  subtype of `biolink:GeneProduct`. This can be added later.
- **No runtime fetching** — ontologies must be bundled in `science-model`.
  Adding a new ontology requires a release.
- **No external KG import** — external knowledge graph assertions are not
  consumed. This is intentional for v1 and will be a separate effort.
- **Single `layer/domain`** — all ontology-typed entities share one layer. If
  fine-grained layer separation is needed per-ontology in the future, it can be
  re-introduced based on actual usage patterns.

---

## 8. Future Direction

1. **Ontology hierarchy (v2)** — parse `is_a` relationships for type
   compatibility reasoning.
2. **Runtime fetching (v2)** — fetch ontology catalogs from Bioregistry/OBO
   Foundry for ontologies not bundled in the package.
3. **External KG consumption (v3)** — import and query external knowledge
   graphs (e.g., from KG Hub) as separate, read-only reference graphs alongside
   the user's project graph. Clear delineation between user knowledge and
   community knowledge.
4. **More bundled ontologies** — GO (Gene Ontology), EDAM, Disease Ontology,
   Sequence Ontology based on user demand.
