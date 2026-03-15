# Knowledge Graph Layering And Canonical Model Design

**Date:** 2026-03-12
**Status:** Approved

## Problem

The current Science knowledge graph stack has drifted across four authorities:

1. Project markdown frontmatter
2. Task markdown files
3. RDF materialized graph files (`knowledge/graph.trig`)
4. Consumer assumptions in `science-web`

This drift shows up as disconnected graph components, orphaned questions and claims, missing task nodes, inconsistent identity schemes, and stale provenance pointing at legacy source files.

In `seq-feats`, for example, the graph currently splits into a literature/concept cluster and a hypothesis/claim cluster, while many questions, claims, and named-entity concepts remain isolated. Tasks carry rich `related:` links in project files but are not represented as first-class graph nodes in the current dashboard design.

## Goals

1. Define one canonical, shared knowledge model for Science-native entities and relations.
2. Support curated optional domain semantics such as biology and physics.
3. Support project-local extensions with the same structural rules as curated profiles.
4. Allow explicit cross-layer relations and on-demand union graphs.
5. Eliminate document/RDF/UI identity drift.
6. Make `science-tool`, `science-web`, commands, and skills operate against the same formal model.

## Non-Goals

1. Mirror full upstream ontologies inside Science.
2. Make raw RDF the only authoring interface.
3. Collapse all layers into one permanent graph.
4. Preserve legacy short-form IDs as long-term canonical identifiers.

Refactor prep docs for this design live in
`docs/plans/2026-03-12-knowledge-graph-layering-desired-file-structure.md` and
`docs/plans/2026-03-12-knowledge-graph-layering-files-to-remove.md`.

## Model Library Structure

`science-model` becomes a layered model library:

1. `science-model/core`
   - Mandatory for all projects.
   - Defines canonical Science-native entity kinds, relation kinds, ID rules, validation rules, and layer semantics.
2. `science-model/bio`
   - Optional curated biology profile built on `core`.
   - Reuses and maps the most useful subset of external bio ontologies such as Biolink, GO, Disease Ontology, MeSH, Sequence Ontology, and related sources.
3. Additional curated domain profiles
   - Same pattern as `bio`, e.g. `physics`, `chemistry`, `neuro`, `materials`.
4. Project-local extension profile
   - One per project.
   - Uses a generalized extension schema such as `project_specific` or `custom`.
   - Must follow the same structural rules as curated profiles.

Conceptually, every project composes:

`core` -> zero or more curated domain profiles -> one project-local extension profile

Example:

```yaml
knowledge_profiles:
  curated: [bio, physics]
  local: project_specific
```

## Profile System

Each profile must declare:

1. Entity kinds it introduces or reuses
2. Relation kinds it introduces or reuses
3. Allowed source and target kinds for each relation
4. Preferred RDF predicates and namespaces
5. Canonical ID namespace and ID format rules
6. Validation rules and strictness level
7. Bridge and mapping rules to `core` and other enabled profiles
8. Domain assignment rules for UI-facing summaries and graph coloring

This profile system is the main contract that tooling consumes. `science-tool`, `science-web`, project validation, and skills should stop hardcoding entity semantics and instead resolve them through `science-model`.

## Core Model

`science-model/core` should define the base Science graph used by all projects.

Core entity kinds should include at least:

1. `hypothesis`
2. `question`
3. `task`
4. `claim`
5. `discussion`
6. `interpretation`
7. `pre-registration`
8. `bias-audit`
9. `comparison`
10. `dataset`
11. `method`
12. `plan`
13. `inquiry`
14. `variable`
15. `assumption`
16. `transformation`
17. `paper`
18. `article`
19. `topic`
20. `evidence`

Core relation kinds should include at least:

1. `addresses`
2. `tests`
3. `supports`
4. `disputes`
5. `about`
6. `relates_to`
7. `depends_on`
8. `blocked_by`
9. `derived_from`
10. `produces`
11. `uses_dataset`
12. `uses_method`
13. `motivates`
14. `resolves`
15. `raises`

The exact RDF predicate used for each relation can reuse existing vocabularies where appropriate, such as `cito:*`, `skos:*`, `prov:*`, `schema:*`, or project-specific `sci:*` and `scic:*` terms.

## Canonical IDs

`science-model` must define one canonical ID scheme used everywhere:

1. Markdown frontmatter
2. Task `related:` references
3. Project-local extension artifacts
4. Materialized RDF node identities
5. API payloads
6. `science-web` routing and filtering

Legacy short forms such as `H01`, `Q05`, or RDF-only nodes like `hypothesis/h01` may exist temporarily as migration aliases, but they are not canonical.

Canonical IDs should be stable, typed, and human-readable, for example:

1. `hypothesis:h01-raw-feature-embedding-informativeness`
2. `question:q60-does-formalized-pipeline-reproduce-phase3b-results`
3. `task:t127-domain-t3-control-calibration`

Aliases should be explicit migration metadata, not hidden heuristics.

## Layer Semantics

The runtime KG should remain layered.

Recommended named graph layout:

1. `layer/core`
   - Science-native project entities and relations from `core`
2. `layer/domain/<profile>`
   - Curated domain profile content such as `layer/domain/bio`
3. `layer/project_specific`
   - Project-local entities and relations
4. `layer/bridge`
   - Explicit cross-layer mapping and bridge relations
5. `layer/provenance`
   - Provenance, confidence, evidence metadata
6. `layer/causal`
   - Causal semantics where applicable
7. `layer/datasets`
   - Dataset linkage and coverage metadata

The union graph is assembled on demand from selected layers. It is a view, not a separate authority.

The model must keep three concepts distinct:

1. `profile` — which schema bundle introduced or governs the semantics
2. `graph_layer` — which named graph stores the statement
3. `domain` — the stable UI-facing topical grouping used for graph coloring and project summaries

This allows:

1. Queries on a single layer
2. Queries on selected layer combinations
3. UI filtering by layer
4. Explicit inspection of cross-layer bridge edges

## Curated Domain Profiles

Curated profiles such as `bio` should be practical and selective. They should:

1. Provide commonly used entity and relation bundles out of the box
2. Reuse a curated subset of external ontology semantics
3. Map external semantics into the Science profile system cleanly
4. Avoid dumping entire external ontologies into every project

For `bio`, the goal is not to clone Biolink, GO, MeSH, Disease Ontology, or Sequence Ontology wholesale. The goal is to expose the most useful and interoperable subset for biology-heavy projects.

Curated profiles alone are not sufficient as the dashboard's domain signal. A project with `bio` enabled should still be able to expose multiple per-node domains such as `genomics`, `proteomics`, `causal-inference`, or `evaluation` when the upstream model supports them. `science-web` should consume those explicit node/entity domains rather than collapsing everything into the enabled profile name.

## Project-Local Extension Profile

Every project should define one local extension profile that follows the same formal schema as curated profiles.

This profile:

1. Introduces project-local entity kinds when necessary
2. Introduces project-local relation kinds when necessary
3. Uses canonical IDs and namespaces
4. Carries provenance and validation metadata
5. Defines mappings to `core` and enabled domain profiles when possible

This prevents project-specific layers from becoming untyped free-for-alls and keeps cross-project tooling effective.

## Tasks As First-Class KG Nodes

Tasks must become first-class graph nodes in the canonical model.

Reasons:

1. Tasks already encode explicit project knowledge through `related:` and `blocked-by`
2. Tasks connect hypotheses, questions, datasets, and methods operationally
3. Excluding tasks from the KG hides project state and creates a fake split between reasoning and execution
4. `science-web` and Science commands need task-aware graph operations

Tasks remain operational objects, but they are also first-class graph entities in `core`.

## Upstream Sources And Graph Materialization

`knowledge/graph.trig` should be treated as a generated/materialized artifact, not a hand-edited source of truth.

Manual curation is still allowed, but it must happen through structured upstream artifacts with schema and validation, for example:

1. Frontmatter-backed entity documents
2. Task markdown files
3. Profile manifests in `science-model`
4. Curated project assertion files under a structured `knowledge/sources/` or `knowledge/assertions/` tree
5. External import manifests for curated ontology subsets

This avoids silent drift between prose, tasks, and RDF.

If a user feels compelled to edit `graph.trig` directly, that is usually a sign that an upstream canonical source is missing and should be added.

### Canonical Structured Source Contracts

The structured `knowledge/sources/<local-profile>/` tree needs to be a real authoring contract, not just a catch-all folder.

At minimum, the contract should support:

1. `entities.yaml`
   - Simple project-local entities that do not need a specialized schema
   - Canonical IDs, titles, aliases, provenance-facing source paths, related refs, source refs, ontology terms, optional `profile`, and optional `domain`
2. `relations.yaml`
   - Authored project assertions that need explicit predicates rather than generic `related`
   - `subject`, `predicate`, `object`, `graph_layer`, `source_path`
   - Relation endpoints may point at canonical project IDs, external CURIEs, URLs, or bare controlled vocabulary tokens when those are the canonical authored form
3. `mappings.yaml`
   - Explicit alias and migration metadata
   - Legacy short IDs, malformed historic refs, and promoted canonical rewrites
4. `models.yaml`
   - Canonical model entities and model-to-model relations
   - Required fields should include `canonical_id`, `title`, `profile`, `source_path`
   - Optional fields should include `domain`, `aliases`, `source_refs`, `related`, and a structured `relations` list
5. `parameters.yaml`
   - Canonical parameter entities and parameter-to-parameter relations
   - Required fields should include `canonical_id`, `title`, `symbol`, `source_path`
   - Optional fields should include `aliases`, `domain`, `source_refs`, `ontology_terms`, physical metadata such as units and quantity grouping, and a structured `relations` list
6. `bindings.yaml`
   - Model-parameter binding assertions and binding metadata
   - Required fields should include `model`, `parameter`, `source_path`
   - Optional fields should include symbol override, role override, units override, confidence, match tier, default value, typical range, provenance/evidence refs, and notes

Illustrative examples:

```yaml
# knowledge/sources/project_specific/models.yaml
models:
  - canonical_id: model:navier-stokes
    title: Navier-Stokes equations
    profile: project_specific
    domain: fluid-dynamics
    source_path: knowledge/sources/project_specific/models.yaml
    aliases: [NavierStokes]
    source_refs: [paper:legatiuk2021]
    related: [question:q01-model-granularity]
    relations:
      - predicate: sci:approximates
        target: model:stokes
```

```yaml
# knowledge/sources/project_specific/parameters.yaml
parameters:
  - canonical_id: parameter:kinematic-viscosity
    title: Kinematic viscosity
    symbol: ν
    profile: project_specific
    domain: transport
    units: m^2/s
    quantity_group: velocity
    source_path: knowledge/sources/project_specific/parameters.yaml
    source_refs: [paper:legatiuk2021]
    relations:
      - predicate: prov:wasDerivedFrom
        target: parameter:dynamic-viscosity
```

```yaml
# knowledge/sources/project_specific/bindings.yaml
bindings:
  - model: model:navier-stokes
    parameter: parameter:kinematic-viscosity
    symbol: ν
    role: viscosity
    confidence: 1.0
    match_tier: canonical
    source_path: knowledge/sources/project_specific/bindings.yaml
```

These contracts are the long-term inputs that `science-tool graph build` should read directly.

### Canonical Sources Vs Application Internals

Project application internals such as generated JSON, TypeScript registries, notebooks, or UI-specific caches are not part of the long-term KG authoring contract.

They may be used as migration/import inputs, but only through explicit importers that write canonical source files under `knowledge/sources/<local-profile>/`.

This boundary matters for projects like `natural-systems-guide`, where the current model layer lives in app-specific files. The correct end state is:

1. canonical source files become the source of truth for model-layer knowledge
2. `science-tool` materializes RDF from those canonical source files
3. project applications either read those canonical files directly or regenerate their own internal artifacts from them

`science-tool` should not permanently depend on project-specific TypeScript or generated JSON layouts to build the KG.

Implementation reminder:
After the typed canonical source contracts are implemented, return to `natural-systems-guide` and complete the model-layer cutover by replacing the remaining app-internal KG inputs with generated canonical source files.

## Runtime Responsibilities

### `science-model`

Owns:

1. Profile schema
2. Canonical entity and relation declarations
3. ID rules
4. Validation rules
5. Graph payload structures shared by other systems
6. The shared distinction between `profile`, `graph_layer`, and `domain`

### `science-tool`

Owns:

1. Parsing structured upstream sources
2. Resolving canonical IDs and aliases
3. Materializing RDF layers deterministically
4. Rebuilding and validating the graph
5. Providing CLI commands for profile-aware graph operations
6. Assigning explicit `domain` values to canonical entities and materialized graph nodes using upstream rules
7. Computing project-level domain summaries such as top domain counts when needed by downstream consumers
8. Treating project-specific importers as migration helpers that write canonical source files rather than as permanent materialization dependencies

### `science-web`

Owns:

1. Reading graph payloads and profile metadata
2. Rendering per-layer and union views
3. Treating tasks and other core entities consistently
4. Avoiding hardcoded semantic assumptions that duplicate `science-model`
5. Consuming upstream `domain` metadata for graph coloring and dashboard summaries rather than inferring domains locally

### `science-web` Consumer Contract

The current `science-web` backend already understands profile manifests and task nodes at a basic level.
The next implementation slice should finish the richer consumer contract exposed by the layered graph model.

`science-web` should treat the following as first-class graph payload concepts:

1. `Task` nodes from project task files
2. `Model` nodes from typed canonical model sources
3. `CanonicalParameter` nodes from typed canonical parameter sources
4. `ParameterBinding` provenance nodes that explain why a model/parameter association exists

The shared API/UI contract should make these distinctions explicit rather than forcing the frontend to reverse-engineer them from RDF details.

Minimum node payload expectations:

```python
class GraphNode(BaseModel):
    id: str
    canonical_id: str
    label: str
    type: str
    profile: str
    domain: str | None
    graph_layer: str
    aliases: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    status: str | None = None
    confidence: float | None = None
    symbol: str | None = None
    role: str | None = None
    match_tier: str | None = None
```

Not every field is populated for every node type.
The important rule is that `science-web` should receive explicit metadata where it exists upstream, especially for model-layer provenance nodes.

Dashboard and graph-view behavior should follow these rules:

1. Color by explicit `domain` values from the graph payload
2. Shape or otherwise distinguish major node kinds such as `Task`, `Model`, `CanonicalParameter`, and `ParameterBinding`
3. Show `profile`, `graph_layer`, and `domain` as separate concepts in inspectors and filters
4. Expose project-level `top_domains` from actual graph content rather than leaving them empty
5. Degrade gracefully for smaller projects that only contain `core` entities and task/question graphs

Implementation reminder:
After the typed model-layer source contracts and project migrations are in place, return to `science-web` and finish the consumer work against both a task-heavy project such as `seq-feats` and a model-heavy project such as `natural-systems-guide`.

## Migration Strategy

Migration should be staged:

1. Define the profile system and canonical IDs in `science-model`
2. Update `science-tool` to materialize graphs from canonical upstream sources
3. Update `science-web` to consume model/profile metadata and include tasks as graph entities
4. Migrate `seq-feats` to `core + bio + project_specific`
5. Define typed canonical source contracts for richer project-local semantics such as models, parameters, and bindings
6. Migrate projects with app-internal graph semantics, such as `natural-systems-guide`, by writing canonical source files from importer scripts
7. Finish `science-web` consumer alignment for richer model-layer nodes, provenance payloads, and domain summaries
8. Backfill aliases and mapping metadata for legacy IDs
9. Remove obsolete assumptions and migration shims after validation

## Validation Requirements

Validation should operate at three levels:

1. Model validation
   - Profiles are well-formed and internally consistent
2. Project validation
   - All canonical IDs resolve
   - All `related:` and `blocked-by` references resolve
   - All structured relation endpoints resolve
   - All bridge relations point to valid entities
   - External term assertions accept the authored canonical form, whether that is a URL, CURIE, or bare controlled vocabulary token
   - Required provenance exists
   - First-class entities are not silently orphaned
3. Runtime validation
   - Union graph assembly is deterministic
   - Layer filters behave correctly
   - API/UI payloads remain stable
   - `profile`, `graph_layer`, and `domain` remain distinct in shared payloads
   - Nodes/entities intended for the dashboard expose explicit `domain` values when available
   - Model-layer projects surface `Model`, `CanonicalParameter`, and `ParameterBinding` nodes without frontend-specific RDF parsing
   - Project summaries expose non-empty `top_domains` when the graph contains domain-tagged nodes

## Key Decisions

Approved decisions from this design round:

1. `science-model` is a layered model library, not a single monolithic model
2. `core` is required for all projects
3. Curated domain profiles are optional and composable, e.g. `[bio, physics]`
4. Every project uses one formal project-local extension profile
5. Canonical IDs are shared across documents, tasks, RDF, APIs, and UI
6. Tasks are first-class graph entities in `core`
7. `graph.trig` is a generated/materialized artifact
8. Manual graph curation must happen through structured upstream sources, not direct TriG editing
9. Application-internal registries are migration inputs, not permanent KG build inputs
10. Rich project-local semantics such as models, parameters, and bindings need typed canonical source contracts, not ad hoc parsing

## Remaining Implementation Questions

These are implementation details to resolve in the plan, not open architecture questions:

1. Final package/module layout under `science-model`
2. Exact naming of layer URIs in the materialized RDF
3. Exact profile manifest file format
4. Exact location of project assertion and mapping source files
5. Promotion workflow for moving stable project-local semantics into curated profiles
6. Exact upstream precedence rules for assigning `domain` (for example explicit source field, curated mapping, otherwise `None`)
7. Exact contract for project-level domain summaries such as `top_domains`
8. Whether typed source contracts live in a dedicated `science-model` module or remain schema-validated within `science-tool`
