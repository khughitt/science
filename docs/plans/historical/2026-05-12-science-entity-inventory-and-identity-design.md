# Science Entity Inventory And Identity Design

## Context

Science project entities are currently surfaced through two different systems:

- `science` has a structured entity loader, graph materializer, profile manifests, task parser, storage adapters, and health checks.
- `dashboard` independently scans project files and also synthesizes attention findings from project-specific artifacts such as DAG edge YAML.

This split makes the dashboard responsible for understanding science project layout, entity validation, and project-specific conventions. It also causes inconsistent UI surfaces: some records are validated Science entities, while others are dashboard-generated read models with no durable Science identity.

The long-term boundary should be:

- `science` owns entity discovery, parsing, validation, identity, source locations, aliases, health checks, and migration helpers.
- `dashboard` consumes an exported Science entity inventory and graph payload. It does not discover or parse Science project files directly.

The inventory export is a durable interface. It must be schema-versioned, cacheable, and stable enough for dashboard to consume without knowing the project filesystem layout.

## Audit Findings

Two representative projects were audited: `~/d/cancer/cancer-types/multiple-myeloma` and `~/d/natural-systems`.

### Multiple Myeloma

`science_tool.graph.sources.load_project_sources()` sees:

- `1873` entities across `36` kinds.
- `662` tasks.
- `36` structured relations.
- `93` manual aliases.
- Entity sources include markdown frontmatter, `knowledge/sources/local/*.yaml`, ontology-backed terms, and task files.

The dashboard scanner sees:

- `986` markdown/result entities.
- `662` tasks.
- It does not see many structured-source records that Science already loads.
- It accepts unregistered frontmatter kinds such as `critique`, `review`, `audit`, `bias-audit`, and `rq` because `science_model.frontmatter.parse_entity_file()` is permissive when used directly.

The dashboard attention system also creates `323` synthetic findings from `doc/figures/dags/*.edges.yaml`. These are not Science entities. They are dashboard read models derived from DAG edges.

### Natural Systems

`science_tool.graph.sources.load_project_sources()` sees:

- `2555` entities across `23` kinds.
- `515` tasks.
- `1540` structured relations.
- `1003` bindings.
- Major structured-source kinds include `canonical_parameter`, `model`, `limit-relation`, `morphism-edge`, and aggregate `finding` records.

The dashboard scanner sees:

- `802` markdown entities.
- `515` tasks.
- It misses the structured source inventory that carries much of the project semantics.

### Existing Science Entity Surfaces

Science already recognizes or loads entities from:

- Markdown frontmatter through `MarkdownAdapter` and `science_model.frontmatter`.
- Aggregate YAML through `AggregateAdapter`, including `knowledge/sources/<profile>/entities.yaml`, `terms.yaml`, and `doc/<plural>/<plural>.yaml`.
- Datapackage YAML through `DatapackageAdapter`.
- Task files through `TaskAdapter`.
- Local profile manifests under `knowledge/sources/<profile>/manifest.yaml`.
- Structured local-source files such as `models.yaml`, `parameters.yaml`, `bindings.yaml`, and `relations.yaml`.

Dashboard currently identifies additional entity-like records from:

- `results/**/datapackage.json` as `workflow-run` entities.
- `doc/figures/dags/*.edges.yaml` as synthetic attention findings.

These dashboard-only detections should move upstream into Science.

## Design Goals

1. Make Science the only authority for project entity inventory.
2. Give every dashboard-visible entity or entity-like record a stable Science identity or stable Science address.
3. Preserve useful human shorthand such as `t123`, `h01`, and `q54` without forcing every entity kind into a single-letter prefix scheme.
4. Separate graph structure from epistemic interpretation.
5. Provide migration tooling and health warnings so existing projects can converge without silent fallbacks.
6. Avoid compatibility layers in the dashboard. The dashboard should move to the new export contract and remove local scanners once the upstream command exists.

## Entity Model

### Canonical ID

Every Science entity has a canonical ID:

```text
<kind>:<local-id>
```

Examples:

- `task:t123`
- `hypothesis:h04-attractor-convergence`
- `question:q54-level2-temporal-profile-validation`
- `model:hodgkin-huxley`
- `canonical_parameter:sodium-conductance`
- `finding:f123-h4-topology-terminal`

The canonical ID is project-local unless the entity declares shared scope or an external identity. Cross-project references use namespace-first form:

```text
<project>:<kind>:<local-id>
```

For v1, `<project>` is the configured `id` in `science.yaml`. If `id` is absent, Science may fall back to the project root directory name for inventory generation, but `science health` must warn that cross-project references are unstable until `science.yaml:id` is set. The project display name is not an identity key.

### Local ID

The local ID should be human-readable and kind-scoped. It must match a conservative token/slug pattern:

```text
[A-Za-z0-9][A-Za-z0-9_.-]*
```

The pattern deliberately allows current Science IDs while rejecting whitespace, empty IDs, path fragments, and prose strings.

`.` is allowed only as a token character for existing IDs and external accession-like local IDs. Science code must not infer hierarchy or version semantics by splitting canonical IDs on `.`; semantic version/accession handling belongs in typed identity fields such as `primary_external_id.version`.

### Aliases

Aliases are secondary lookup keys, not canonical identities.

Supported shorthand aliases:

- Tasks: `t123` maps to `task:t123`.
- Hypotheses: `h04` maps to the one matching `hypothesis:h04-*` or `hypothesis:h04`.
- Questions: `q54` maps to the one matching `question:q54-*` or `question:q54`.
- Propositions may use `pNN` if a project already follows that convention.

Aliases must be unique within a project. `science health` should fail or warn on collisions depending on severity.

Alias matching is case-insensitive for shorthand aliases. `T123` and `t123` collide and resolve to the same canonical task if registered. Canonical IDs remain case-preserving in storage, but new project-local canonical IDs should use lowercase kinds and lowercase slug-style local IDs unless the local ID is an external symbol where case is meaningful.

### UUIDs

UUIDs should not be the default primary ID. They are stable but make prose, graph debugging, source review, and manual references worse. UUIDs may be allowed as an implementation detail for generated opaque records, but the exported canonical ID should still be `<kind>:<local-id>` whenever possible.

### Numbered IDs

The system should not require global IDs like `task-123` or `entity-123`. They create unnecessary migration churn and erase meaningful kind prefixes. Numbering remains useful inside local IDs for selected kinds:

- `task:t123`
- `hypothesis:h04-attractor-convergence`
- `question:q54-level2-temporal-profile-validation`
- `finding:f123-h4-topology-terminal`

For kinds without a natural short prefix, use slugs:

- `model:hodgkin-huxley`
- `canonical_parameter:membrane-capacitance`
- `limit-relation:darcy-to-diffusion-low-reynolds`

## DAG Edges And Findings

DAG edges are graph relations, not Science findings.

A graph edge may be addressable for provenance, review, and linking:

```text
dag-edge:<dag-slug>:e<edge-number>
```

Example:

```text
dag-edge:h4-attractor-convergence:e007
```

That address names a graph statement. It should not be displayed as a finding by itself.

The `<edge-number>` component is derived from the edge's declared YAML `id`, not from array position. Reordering an `edges.yaml` file must not change any DAG edge address. `science dag` migration should populate missing edge IDs from the current order once, and after that `science health` should warn on missing IDs and error on duplicate IDs within the same DAG.

A `finding` is a separate epistemic entity that interprets evidence about one or more targets. Targets can include:

- A single DAG edge.
- A path through a DAG.
- A subgraph.
- A workflow result.
- A dataset comparison.
- A relation between multiple entities.

Example finding:

```yaml
id: "finding:f123-h4-topology-terminal-structural"
kind: finding
title: "Landscape topology structurally determines the terminal attractor definition, but empirical topology proxies remain unresolved"
targets:
  - type: dag-edge
    ref: "dag-edge:h4-attractor-convergence:e007"
status: unknown
identification_strength: structural
related:
  - inquiry:h4-attractor-convergence
source_refs:
  - task:t219
  - task:t234
  - task:t280
  - paper:TaherianFard2017
  - paper:Huang2013
```

Longer narrative work remains `interpretation`, `report`, or `synthesis`. A finding is the compact ledger-friendly epistemic unit that can be ranked, reviewed, and linked to graph targets.

Migration rule:

1. Assign stable addresses to all DAG edges.
2. Add optional `finding_ref` to claim-bearing edges.
3. Move rich evidence/status fields from DAG edge YAML into authored or generated `finding` entities.
4. Make `science health` warn when a DAG edge has claim-like fields but no linked finding.

During migration, Science should also emit `finding_candidate` records for claim-bearing DAG edges that do not yet have `finding_ref`. These are inventory read models, not canonical entities. Dashboard may render them in attention surfaces with a candidate/provisional marker, but it must not mint its own finding IDs from DAG YAML.

Claim-like DAG fields include:

- `edge_status`
- `identification`
- `data_support`
- `lit_support`
- `caveats`
- `posterior`
- `last_reviewed`

## Science Export Contract

Add a Science-owned command:

```bash
science entities inventory --format json
```

The command exports a project inventory for dashboard and other consumers.

The JSON payload should include:

- `schema_version`, starting at `"1"`.
- `generated_at`.
- `project_id`, derived from `science.yaml:id` when present.
- `content_hash`, computed from canonicalized entity records, aliases, addresses, finding candidates, and graph-statement addresses.
- `audit_hash`, computed from canonicalized warnings and migration diagnostics.
- Project identity and path.
- Entity records from all Science adapters.
- Canonical ID.
- Kind.
- Profile.
- Entity class where available: `epistemic`, `operational`, or `reference`.
- Title.
- Status.
- Source location.
- Created/updated/activity dates.
- Aliases.
- Related refs.
- Source refs.
- Target refs for findings.
- Review state.
- Scope.
- Registration state for kind/profile.
- Migration warnings.
- `finding_candidates` for claim-bearing records that are not yet backed by canonical finding entities.
- `watch_paths`, declared by Science as project-root-relative paths that should trigger inventory refresh when changed.

Hash canonicalization uses RFC 8785 JSON Canonicalization Scheme semantics: UTF-8 JSON, deterministic object member ordering, deterministic array ordering from the inventory producer, and no insignificant whitespace. If the implementation does not import an RFC 8785 library, it must document and test an equivalent canonical serializer. `generated_at` is excluded from both hashes.

The command should also include stable addresses for non-entity graph statements when useful:

- DAG edges.
- Relation rows.
- Bindings.

These addresses are not entities unless backed by an entity record.

### Transport And Refresh

The v1 transport is a CLI JSON export. This is an explicit runtime dependency: dashboard requires the compatible `science` package or executable to be installed and importable in the backend environment. Dashboard already depends on Science packages for graph loading, so v1 keeps one process model and avoids adding a daemon. A future v2 may replace CLI transport with an in-process API or long-running service without changing the inventory schema.

Dashboard backend code may invoke:

```bash
science entities inventory --format json --project <path>
```

Dashboard must not shell out on every browser render. It should refresh the inventory only during backend startup, explicit rescan, or a change under one of the Science-provided `watch_paths`. The loaded payload should be cached in the dashboard store together with `content_hash`, `audit_hash`, and `generated_at`.

Dashboard must not hard-code watched roots such as `doc/`, `knowledge/`, or `results/`. Science declares the watch set in the inventory payload. For v1, `watch_paths` may be conservative, but it must be Science-owned.

The inventory command should also support:

```bash
science entities inventory --format json --project <path> --output <path>
```

This allows later workflows to precompute inventories without changing the dashboard contract.

The payload is expected to be multi-MB for large projects. V1 does not require streaming; it does require bounded runtime and deterministic ordering so cache invalidation is reliable.

### Schema Policy

Dashboard must reject inventory payloads with an unsupported major `schema_version`. Additive fields are allowed within the same major version. Removing or renaming fields requires a new major version.

Every inventory payload should be validated against a Science-owned contract model before dashboard consumes it. The canonical import path is:

```python
science_model.contracts.inventory_v1
```

That module should expose Pydantic models for runtime validation and a generated JSON Schema for CLI consumers. Dashboard validates against the installed Science package, not a copied schema file.

## Dashboard Boundary

Dashboard should stop scanning Science project files directly.

Replace these dashboard responsibilities:

- Markdown directory scans.
- `results/**/datapackage.json` entity synthesis.
- Task parsing.
- DAG edge finding synthesis.
- Direct assumptions about project layout.

With:

- Loading `science entities inventory --format json`.
- Loading the Science graph export.
- Rendering entities, findings, tasks, graph nodes, and attention surfaces from the exported payload.
- Rendering Science-provided `finding_candidate` records during DAG migration, rather than parsing DAG files locally.

During the migration, dashboard may retain a single explicit adapter for the new inventory payload. It should not keep parallel local discovery logic once the upstream command is available.

## Health Checks

Extend `science health` with entity identity checks:

- Missing canonical ID.
- Canonical ID not matching `<kind>:<local-id>`.
- Local ID outside the allowed token/slug pattern.
- Frontmatter entity inferred from path without explicit `id`.
- Unknown kind not registered in core, active local profile, or active ontology catalogs.
- Duplicate canonical IDs.
- Duplicate aliases.
- Alias resolving to multiple canonical IDs.
- Entity kind/profile mismatch.
- Dashboard-era synthetic entity candidates, such as DAG edges with claim-like fields but no finding.
- `results/**/datapackage.json` records not represented through a Science-owned adapter.
- Markdown prose references that still point at deprecated, migrated, or unresolved IDs.

Severity should be staged:

- `error`: duplicate canonical IDs, invalid task IDs, invalid canonical ID shape for new records, alias collisions.
- `warning`: path-inferred IDs, unknown kinds, DAG edges with claim-like fields but no finding, legacy result manifests not represented in the inventory, unresolved or deprecated markdown prose references.
- `info`: deprecated aliases and migration suggestions.

### New Versus Existing Records

Science needs an explicit baseline mechanism to distinguish existing legacy records from new records. Add an entity identity baseline file:

```text
knowledge/entity-identity-baseline.yaml
```

The baseline stores known legacy IDs, their source paths, the date they were accepted as legacy, and optional lifecycle fields:

- `accepted_at`: date the legacy identifier was recorded.
- `migrated_at`: date the record was migrated to current identity rules.
- `replacement`: canonical ID that supersedes the legacy ID, when applicable.

`science health` treats records in the baseline without `migrated_at` as migratable warnings. Records not in the baseline must satisfy current identity rules, and invalid new records are errors. The baseline should be append-only by default; migrated entries are marked with `migrated_at` rather than removed, so historical references remain auditable. A separate compaction command may prune entries only when no project text or structured source references them.

The baseline is not a compatibility layer; it is an audit ledger that prevents unbounded silent acceptance of newly introduced invalid IDs.

### Unknown Kind Resolution

Unknown kinds should not remain warning noise. Provide a helper:

```bash
science entities register-kind <kind> --class epistemic|operational|reference --description <text>
```

The helper appends an `entity_kinds` entry to the active local profile manifest and preserves existing records of that kind. It should refuse kinds that collide with core kinds or active ontology kinds. Re-running the command for an already registered local kind with identical metadata is a no-op. Re-running it with a different class, canonical prefix, or description is an error; kind semantics should not mutate silently.

`science entities audit-identifiers --learn-kinds` may propose registration commands, but applying them should remain explicit.

## Migration Helper

Add a migration command family:

```bash
science entities migrate-identifiers
science entities migrate-dag-findings
science entities audit-identifiers
science entities register-kind
```

`migrate-identifiers` should:

- Detect implicit/path-derived IDs.
- Propose canonical IDs.
- Preserve old references as aliases or `deprecated_ids`.
- Rewrite frontmatter IDs when requested.
- Update references in `related`, `source_refs`, task fields, and structured source YAML.
- Update markdown body prose references when they can be resolved unambiguously.
- Report ambiguous prose references with file and line number, without rewriting them.
- Refuse to apply if proposed IDs collide.

`migrate-dag-findings` should:

- Assign stable DAG edge addresses.
- Identify claim-bearing DAG edges.
- Generate candidate `finding` records.
- Add `finding_ref` to DAG edge YAML when applied.
- Preserve task/literature support as `source_refs`.
- Preserve `edge_status` and `identification` as finding metadata.

Both commands should support:

```bash
--dry-run
--apply
--format text|json
```

### Workflow Run Manifests

Add a dedicated `WorkflowRunAdapter` for `results/**/datapackage.json`.

`DatapackageAdapter` should remain responsible for dataset-oriented `datapackage.yaml` records. `WorkflowRunAdapter` owns runtime result manifests and emits `workflow-run` entities with canonical IDs derived from manifest identity fields or, when absent, from a stable path slug. `science health` should warn when a result manifest lacks explicit workflow-run identity.

## Rollout

### Phase 1: Inventory Audit

- Add inventory command in Science.
- Include all currently loaded `load_project_sources()` entities.
- Include task and source metadata.
- Include warnings for unknown kinds and implicit IDs.
- Include `schema_version`, `content_hash`, `audit_hash`, `generated_at`, `watch_paths`, and validated JSON schema.
- Add `WorkflowRunAdapter` coverage for `results/**/datapackage.json`.
- Do not change dashboard behavior yet.

### Phase 2: Dashboard Consumption

- Add dashboard client for the Science inventory export.
- Replace dashboard entity scans with inventory records.
- Keep existing graph loading but match graph nodes against Science canonical IDs from the inventory.
- Remove dashboard DAG edge finding synthesis once Science emits `finding` entities or `finding_candidate` records.
- Render Science-provided `finding_candidate` records so attention surfaces do not go dark before full DAG finding migration.

### Phase 3: DAG Finding Migration

- Add DAG edge stable addresses.
- Generate candidate findings from claim-bearing DAG edges.
- Add `finding_ref` to claim-bearing edges.
- Update attention surfaces to show findings, not raw edges.
- Migrate existing aggregate finding records only when they lack required target/source identity fields; records that already satisfy the finding inventory contract do not need content rewrites.

### Phase 4: Health Enforcement

- Promote identity warnings to stronger checks for new records.
- Keep existing records migratable with explicit warnings.
- Fail on duplicate canonical IDs and alias collisions.

## Non-Goals

- Do not introduce UUIDs as the primary identity scheme.
- Do not require every kind to have a single-letter shorthand.
- Do not make graph edges first-class findings.
- Do not preserve dashboard scanners as compatibility layers after the Science inventory export is available.
- Do not migrate all project files in the first implementation pass.

## Acceptance Criteria

The design is successful when:

- `science entities inventory --format json` can represent the entity inventory for both audited projects.
- Dashboard can render project entities and attention findings without parsing project markdown, task files, result manifests, or DAG edge YAML.
- Science health reports missing, invalid, implicit, unknown, or colliding entity identities.
- DAG edges are addressable graph statements, while findings are separate epistemic entities linked to those graph statements.
- Migration commands can produce a dry-run report for both audited projects without applying changes.
- Inventory generation completes in under 10 seconds on each audited project on a warm local checkout. "Warm" means the second consecutive invocation of `science entities inventory --format json --project <path> --output /tmp/inventory.json` in the same shell session after the first invocation has completed successfully.
- Inventory payloads validate against the v1 schema before dashboard consumes them.
- Dashboard renders both audited projects with zero local filesystem reads of project content outside the Science inventory and graph export paths.
- Reordering a DAG `edges.yaml` file does not change any existing DAG edge address.
