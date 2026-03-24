# Multi-Project Sync — Design Spec

**Date:** 2026-03-23
**Status:** Draft

## Problem

Science projects develop independently, each building their own knowledge model
extensions on top of the shared core (`science-model`) and optional domain profiles
(`bio`, etc.). When a user works across multiple projects exploring overlapping parts
of a common underlying world model, several problems emerge:

- **Duplicate entities** — the same gene, pathway, or concept gets defined
  independently in multiple projects with inconsistent metadata.
- **Siloed extensions** — project-local entity kinds and relations that would be
  useful across projects stay locked in one project.
- **Missed connections** — a question answered in one project could inform
  hypotheses in another, but there's no mechanism to surface this.

## Goal

Make science "multi-project from the start" — a user's collection of projects
behaves like one interconnected research landscape where progress anywhere enriches
the whole. Focus on single-user, local filesystem for v1; architect for multi-user
later.

## Approach: Registry as Shared Profile

The cross-project registry is a knowledge profile — a `cross-project` profile that
sits alongside `core` and `bio` in the profile hierarchy. Sync promotes shared
entities and relations into this profile. Projects consume it like any other curated
profile.

Three complementary mechanisms:

1. **`/science:sync`** — explicit command for full cross-project alignment and
   content propagation.
2. **Proactive checks** — read-only registry lookups during entity creation to
   prevent drift before it happens.
3. **Stale nudges** — commands like `/science:status` and `/science:next-steps`
   surface when sync is overdue.

---

## 1. Architecture Overview

### Global Config (`~/.config/science/`)

```
~/.config/science/
├── config.yaml              # Global settings + auto-maintained project list
├── sync_state.yaml          # Per-project sync timestamps & entity hashes
└── registry/                # The cross-project shared profile
    ├── manifest.yaml         # ProfileManifest (dynamically populated)
    ├── entities.yaml         # Shared entity index
    └── relations.yaml        # Shared relation index
```

### Profile Hierarchy

```
core (strictness: "core")
  ├── bio (strictness: "curated")
  ├── <other domain profiles> (strictness: "curated")
  └── cross-project (strictness: "curated", dynamically populated)
       └── project_specific (strictness: "typed-extension")
```

The `cross-project` profile has `strictness: "curated"`. Its `entity_kinds` and
`relation_kinds` are populated by sync rather than hand-curated.

**Dynamic profile loading:** Unlike `CORE_PROFILE` and `BIO_PROFILE`, which are
static Python constants, the cross-project profile is loaded at runtime from
`~/.config/science/registry/manifest.yaml`. This requires:

1. A `load_cross_project_profile() -> ProfileManifest | None` function that reads
   the YAML manifest and returns a `ProfileManifest` (or `None` if registry does
   not exist yet).
2. The `_CORE_KINDS` set in `sources.py` (used by `_default_profile_for_kind()`)
   is currently computed once at import time. This must become a function
   `_known_kinds(profiles)` that includes entity kinds from all active profiles
   (core + curated + cross-project) so that cross-project entity kinds are
   correctly routed.
3. Profile resolution in `load_project_sources()` must handle `"cross-project"` in
   `KnowledgeProfiles.curated` by calling the runtime loader rather than looking
   up a Python constant.

### Automatic Project Registration

Any science CLI command that resolves a project root also registers the project in
`~/.config/science/config.yaml`. Registration is implemented as a standalone
function `ensure_registered(project_root, project_name)` called from the CLI
entry-point (not from `_read_project_config()`, which remains a pure reader). This
runs once per CLI invocation — a cheap read + conditional write.

```yaml
# ~/.config/science/config.yaml
sync:
  stale_after_days: 7
projects:
  - path: /home/user/research/aging-clocks
    name: aging-clocks
    registered: 2026-03-15
  - path: /home/user/research/protein-folding
    name: protein-folding
    registered: 2026-03-20
```

### Connection Points

- **Proactive path:** During entity creation or `graph build`, the cross-project
  profile is consulted. If an entity or relation already exists in the registry,
  reuse it rather than re-defining locally.
- **Reactive path (`/sync`):** Reads all registered projects, compares against the
  registry, promotes shared definitions, and propagates relevant content.
- **Nudge path:** `/science:status` and `/science:next-steps` check
  `sync_state.yaml` and mention staleness.

---

## 2. Registry Data Model

### Entity Index (`registry/entities.yaml`)

```yaml
entities:
  - canonical_id: "gene:tp53"
    kind: "gene"
    title: "TP53 (Tumor Protein P53)"
    profile: "bio"
    aliases: ["p53", "tumor-protein-p53", "TP53"]
    ontology_terms: ["NCBIGene:7157", "HGNC:11998"]
    source_projects:
      - project: "aging-clocks"
        status: "active"
        first_seen: "2026-03-15"
      - project: "protein-folding"
        status: "active"
        first_seen: "2026-03-20"
```

Key field: `source_projects` tracks which projects define this entity, when it was
first seen, and its current status.

### Relation Index (`registry/relations.yaml`)

```yaml
relations:
  - subject: "gene:tp53"
    predicate: "biolink:participates_in"
    object: "pathway:apoptosis"
    graph_layer: "layer/domain/bio"
    source_projects: ["aging-clocks", "protein-folding"]
```

### Profile Manifest (`registry/manifest.yaml`)

```yaml
name: "cross-project"
imports: ["core"]
strictness: "curated"
entity_kinds: []      # Populated dynamically — entity kinds seen across 2+ projects
                       # that aren't in core or a curated domain profile
relation_kinds: []    # Same — novel relation kinds shared across projects
```

### Pydantic Models

New models for the registry and sync state:

```python
class SyncSource(BaseModel):
    """Provenance marker for sync-propagated entities."""
    project: str
    entity_id: str
    sync_date: date

class RegistryEntitySource(BaseModel):
    """Per-project presence record in the registry."""
    project: str
    status: str | None = None
    first_seen: date

class RegistryEntity(BaseModel):
    """An entity tracked across projects in the registry."""
    canonical_id: str
    kind: str
    title: str
    profile: str
    aliases: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    source_projects: list[RegistryEntitySource] = Field(default_factory=list)

class RegistryRelation(BaseModel):
    """A relation tracked across projects in the registry."""
    subject: str
    predicate: str
    object: str
    graph_layer: str = "graph/knowledge"
    source_projects: list[str] = Field(default_factory=list)

class RegisteredProject(BaseModel):
    """A project registered in the global config."""
    path: str
    name: str
    registered: date

class GlobalConfig(BaseModel):
    """Global science config at ~/.config/science/config.yaml."""
    sync: SyncSettings = Field(default_factory=lambda: SyncSettings())
    projects: list[RegisteredProject] = Field(default_factory=list)

class SyncSettings(BaseModel):
    stale_after_days: int = 7

class ProjectSyncState(BaseModel):
    last_synced: datetime
    entity_count: int
    entity_hash: str

class SyncState(BaseModel):
    """Sync state at ~/.config/science/sync_state.yaml."""
    last_sync: datetime | None = None
    projects: dict[str, ProjectSyncState] = Field(default_factory=dict)
```

### Entity Matching Strategy

When sync or proactive checks determine whether a new entity matches an existing
registry entry, matching is done in tiers:

1. **Exact canonical ID match** — definitive.
2. **Alias match** — new entity's canonical ID or aliases overlap with a registry
   entry's aliases. High confidence.
3. **Ontology term match** — shared ontology terms (e.g., both map to
   `NCBIGene:7157`). High confidence for curated ontologies.
4. **Fuzzy title + kind match** — same entity kind and similar title. Flagged for
   user review rather than auto-merged.

Tiers 1-3 are auto-resolved. Tier 4 is included in the sync report for manual
review.

---

## 3. The `/sync` Command

### Phase 1: Collect

For each registered project in `~/.config/science/config.yaml`:

- Call `load_project_sources()` to get the project's current `ProjectSources`
- Skip projects whose paths no longer exist (with a warning)

### Phase 2: Align — Knowledge Model

Compare each project's entities/relations against the registry:

- **Deduplication:** Entities matching (tiers 1-3) across projects are consolidated
  in the registry. Aliases from all projects are merged, `source_projects` updated.
- **Novel shared types:** If two or more projects independently define entities of a
  kind not in core or curated profiles, that entity *kind* is promoted to the
  cross-project profile manifest (type-level sharing).
- **Drift detection:** If the same entity exists in multiple projects with
  conflicting metadata (different status, different ontology terms), flagged in the
  sync report.

### Phase 3: Propagate — Cross-Project Content

For each entity in the registry that appears in 2+ projects, find content-bearing
entities (questions, claims, hypotheses, evidence) that reference it. If a content
entity exists in project A but not in project B (which also has the shared entity),
propagate it to project B.

**What propagates:**

| Entity type | Propagates? | Rationale |
|---|---|---|
| `question` | Yes | Open questions about shared entities are relevant |
| `claim` | Yes | Claims about shared entities inform other projects |
| `relation_claim` | Yes | Requires adding `RELATION_CLAIM` to the `EntityType` enum (currently only a profile entity kind, not a frontmatter-parseable type) |
| `hypothesis` | Yes | Testable conjectures touching shared entities |
| `evidence` | Yes | Evidence about shared entities strengthens other projects |
| `task` | Selectively | Only tasks with `tags: [cross-project]` |
| `experiment` / `workflow` / `workflow-run` | No | Implementation-specific |
| `model` / `variable` / `parameter` | No | Project-local structure |
| `dataset` / `method` | Selectively | Only with `tags: [cross-project]` — some methods/datasets about shared entities have cross-project value |
| `concept` / `topic` / `paper` | No | Background material, not actionable. Fuzzy matches between these types across projects are surfaced in the sync report for manual reconciliation. |

**Propagation algorithm:**

```
for each shared_entity in registry where len(source_projects) >= 2:
    for each project that has shared_entity:
        find content_entities where shared_entity in content_entity.related
        for each other_project that also has shared_entity:
            if content_entity not already in other_project (by ID or alias):
                propagate content_entity → other_project
```

**Propagated entity format:**

Written to `doc/sync/` subdirectory with provenance metadata. Note: `doc/sync/`
is a subdirectory of `doc/`, which is already scanned by
`_load_markdown_entities()` via `rglob("*.md")`. No separate loading path is
needed — propagated entities participate in graph materialization automatically.

Propagated files should be committed to version control (they are project
artifacts, not ephemeral).

```yaml
---
id: "question:q-tp53-methylation-age"
type: question
title: "Does TP53 methylation correlate with biological age?"
status: open
tags: [sync-propagated]
related:
  - "gene:tp53"
source_refs: []
sync_source:
  project: "aging-clocks"
  entity_id: "question:q4-tp53-methylation-age"
  sync_date: "2026-03-23"
---

*Propagated from aging-clocks on 2026-03-23.*

Does TP53 methylation status serve as a reliable indicator of biological
age across tissue types?
```

**Idempotency:** If a propagated entity already exists in the target (matched by
canonical ID or `sync_source.entity_id`), it is not overwritten. The local version
is authoritative.

**Preventing sync storms:** Entities with a `sync_source` field never propagate
further. This prevents A→B→A cycles.

### Phase 4: Report

```
Cross-project sync complete (2026-03-23)

Registry:
  Entities: 142 (+8 new, 3 updated)
  Relations: 89 (+5 new)
  Shared entity kinds promoted: 1 (protein-complex)

Alignment:
  Deduplicated: 4 entities across projects
  Drift detected: 1 (gene:brca1 — status differs)

Propagated:
  aging-clocks → protein-folding: 2 questions, 1 claim
  protein-folding → aging-clocks: 1 question

Fuzzy matches for review:
  concept:apoptosis (aging-clocks) ↔ topic:programmed-cell-death (protein-folding)
```

### Phase 5: Update State

```yaml
# ~/.config/science/sync_state.yaml
last_sync: "2026-03-23T14:30:00"
projects:
  aging-clocks:
    last_synced: "2026-03-23T14:30:00"
    entity_count: 87
    entity_hash: "abc123"
  protein-folding:
    last_synced: "2026-03-23T14:30:00"
    entity_count: 55
    entity_hash: "def456"
```

**Entity hash:** SHA-256 of the sorted, newline-joined canonical IDs of all
`SourceEntity` records in the project. Used for quick staleness detection without
re-loading full project sources.

---

## 4. Proactive Checks

### When they fire

- During `graph build`
- During entity creation in commands (`/science:add-hypothesis`, etc.)

### How they work

1. Load `~/.config/science/registry/entities.yaml` (cached in-memory for session)
2. Run new entity through tiered matching (canonical ID → aliases → ontology terms)
3. If match found:
   - **Exact match:** suggest reusing existing canonical ID and aliases
   - **Alias/ontology match:** inform user of potential overlap
4. If no match: proceed normally

### Design constraints

- Read-only — proactive checks never write to the registry
- Advisory — they don't block entity creation
- Lightweight — one YAML file read per session, cached
- Only fire during explicit science commands, not on every file save

### Implementation

A `check_registry(canonical_id, aliases, ontology_terms) -> list[RegistryMatch]`
function that commands can call.

---

## 5. Stale Sync Nudges

### Where they appear

- `/science:status` — project orientation command
- `/science:next-steps` — gap analysis

### How they work

1. Read `~/.config/science/sync_state.yaml`
2. If days since last sync > `stale_after_days` threshold (default: 7):
   ```
   Cross-project sync is 12 days stale. Run /science:sync to align
   with 3 other registered projects.
   ```
3. If current project's entity hash differs from last sync:
   ```
   This project has 6 new entities since last sync.
   ```

---

## 6. Changes to Existing Code

### science-model

- **`profiles/__init__.py`** — add `load_cross_project_profile()` for runtime YAML
  loading
- **`entities.py`** — add `RELATION_CLAIM = "relation_claim"` to `EntityType`
  enum (currently only a profile entity kind, not a parseable type). Add optional
  `sync_source: SyncSource | None` field to `Entity`, with `SyncSource` model
  (`project`, `entity_id`, `sync_date`).
- **`frontmatter.py`** — parse `sync_source` from frontmatter

### science-tool

- **`graph/sources.py`** — extend `_read_project_config` and
  `load_project_sources` to include `cross-project` in resolved profiles when
  registry exists. Add `check_registry()` function.
- **`cli.py`** — new `sync` command group: `sync run` (with `--dry-run` flag to
  preview without writing), `sync status`, `sync projects`, `sync rebuild`
- **`cli.py`** — modify `graph build` to call proactive checks

### New module: `science-tool/src/science_tool/registry/`

```
registry/
├── __init__.py
├── config.py          # Global config read/write
├── index.py           # Registry entity/relation index read/write
├── registration.py    # Auto-registration logic
├── sync.py            # Sync orchestrator (phases 1-5)
├── matching.py        # Tiered entity matching
└── propagation.py     # Cross-project content propagation
```

### Commands

- **New:** `/science:sync` command prompt
- **Modified:** `/science:status` — add sync staleness check
- **Modified:** `/science:next-steps` — add sync staleness nudge
- **Modified:** `/science:create-graph`, `/science:update-graph` — add proactive
  registry check guidance

### Unchanged

- Graph materialization pipeline (`materialize.py`) — already consumes whatever
  profiles are configured
- TriG storage format
- Existing domain profiles (`bio`, `core`, `project_specific`)
- Aspects
- Templates (minor: may add `sync_source` to relevant templates)

---

## 7. Explicit Non-Goals (v1)

- **Composite graph** — no merged/federated graph across projects. Downstream
  concern for the dashboard.
- **Multi-user** — single-user, local filesystem only. Architecture supports
  extension to shared/remote registries later.
- **Conflict resolution** — drift is reported, not auto-resolved. User decides.
- **Real-time sync** — no file watchers or background processes. Explicit `/sync`
  with passive nudges.
- **Registry as source of truth** — the registry is an index, not authoritative.
  Projects own their entities. Registry can be rebuilt from scratch:
  `science-tool sync rebuild`.

---

## 8. Edge Cases & Bootstrap

- **Zero registered projects:** `/sync` is a no-op (nothing to sync). The registry
  is not created until at least one project is registered.
- **One registered project:** `/sync` populates the registry from that project's
  entities/relations but performs no propagation (no other project to propagate to).
  This is useful: the next project registered will immediately benefit from the
  pre-populated registry.
- **Project path no longer exists:** Sync warns and skips it. The project remains
  in `config.yaml` (user can remove with `sync projects remove`).
- **Registry does not exist yet:** Proactive checks gracefully return empty results.
  `load_cross_project_profile()` returns `None`. No profile is added to the
  project's active profiles.
