# Graph build × commons overlay integration — design

**Parent design:** `docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` (§2.1 SharedEntityAdapter / OverlayAdapter; §5 Project overlays)
**Predecessors (merged):**
- `docs/plans/2026-05-14-commons-overlay-merge-design.md` (D1 — overlay merge layer)
- `docs/plans/2026-05-14-commons-inventory-v2-design.md` (D2 — inventory_v2 overlay integration)
- `docs/plans/2026-05-16-commons-promote-topics-themes-design.md` (Phase F — topic/theme promote)
**Status:** approved 2026-05-19

---

## 1. Goal

Wire commons-promoted entities (`~/d/science-commons/{datasets,papers,topics,themes}/`) and their per-project overlay files (`<project>/doc/<type>/<slug>.md` with `overlay_of:`) into `science graph build` so that authored references to commons IDs resolve and produce triples in the project's `knowledge/graph.trig`.

mm30 is the integration canary: it is the first project to land Phase F overlays (commit `d4701ff` in mm30) and currently fails `science graph build` with 65 unresolved references to `topic:*` IDs that exist in commons but are invisible to the graph builder.

## 2. Scope

### In scope

- A new commons-loading pass that runs from `load_project_sources` after the existing adapter loop.
- Translation of `CommonsEntityRecord` + optional `OverlayRecord` into `science_model.Entity` instances with `scope = EntityScope.SHARED`, registered in `identity_table` / `entities`, and routed through the existing emission pipeline (`_add_entity`, `_add_relations`, `audit_project_sources`, freshness).
- Strict failure semantics matching today's "unresolved refs are fatal" behavior.
- Provenance triples that record (a) the commons body path and (b) the project-overlay path when present.
- A new `sci:scope` predicate emitted for every entity (`"project"` or `"cross-project"`).
- Test surface: unit tests for the new module, end-to-end `materialize_graph` tests, audit regression test, and an mm30-shaped canary fixture.

### Targeted schema changes (in scope, narrowly)

Two `ThemeEntity` Literal extensions are required to reconcile pre-existing vocabulary drift between `science_model.entities.ThemeEntity` and `schemas/mixin-theme-2.0.json`. Without these, loading a commons theme into the graph fails Entity validation even though the commons-side schema accepted it.

| Field | ThemeEntity (current) | mixin-theme-2.0 (current) | Union (proposed) |
|---|---|---|---|
| `theme_kind` | `methodological`, `biological`, `translational`, `evidence-quality`, `organizational` | `methodological`, `conceptual`, `empirical`, `domain` | `methodological`, `biological`, `translational`, `evidence-quality`, `organizational`, `conceptual`, `empirical`, `domain` (8 values) |
| `theme_scope` | `project`, `federation`, `child` | `project`, `cross-project` | `project`, `federation`, `child`, `cross-project` (4 values) |

Concrete change in `science_model/entities.py`:

```python
# science_model/entities.py:458-465
theme_kind: Literal[
    "methodological", "biological", "translational",
    "evidence-quality", "organizational",
    "conceptual", "empirical", "domain",
] = "methodological"
theme_scope: Literal[
    "project", "federation", "child", "cross-project",
] = "project"
```

Rationale: the union-vocabulary approach lets pre-existing project-local themes (using the original ThemeEntity values) and commons-promoted themes (using the mixin-theme-2.0 values) both validate. Vocabulary harmonization — picking a single canonical set — is a separate task with its own design surface.

Note: commons currently contains zero themes (see `~/d/science-commons/themes/` is empty at design time). The mm30 canary therefore does not stress this code path. But Phase F promoted topics; themes are next, and the model change must land BEFORE any theme is promoted, otherwise the first promoted theme's first graph build will fail. The schema-change test (`test_theme_cross_project_scope_validates` in §7.1) covers the cross-project value; an additional `test_theme_mixin_kind_validates` (added below) covers the kind-vocabulary extension.

No other schema changes. Commons `topic` / `paper` / `dataset` map onto existing kinds in `EntityRegistry.with_core_types()` without modification.

### Out of scope

- `pin_version` enforcement against commons git history. Carried on the overlay record, surfaces as a warning if commons HEAD differs — but no `git show <tag>:…` checkout. Aligns with the overlay-merge design D1 deferral.
- Eager-loading the full commons store. Only commons entities referenced by the project (or overlaid in the project) become entities in the project graph. The rest exist in commons but produce no project-graph triples.
- A separate `commons.trig` cross-project graph. That's a follow-on if/when the dashboard needs it; the project-graph layer is the deliverable here.
- Changes to `commons promote`, `commons validate`, or `commons show`.
- Further schema changes beyond the two `ThemeEntity` Literal extensions above. New ontology terms, new entity kinds, new mixin fields, and vocabulary harmonization across `science_model` and `mixin-theme-2.0` are all deferred.
- Overlay project-only fields (`relevance`, `hypothesis_links`, `task_links`, `project_tags`) entering the graph. They are surfaced by inventory_v2 already; the graph layer drops them in this phase. A future task can add a predicate if a graph consumer needs them.

## 3. Architecture

### 3.1 Integration point

A single new tail-call in `load_project_sources` (`science/src/science_tool/graph/sources.py`), invoked **after** all reference-bearing sources (adapter loop, legacy records, structured relations, legacy nested relations from models/parameters, bindings) have been loaded — so the helper sees every authored `<type>:<slug>` reference, not just those on entities:

```python
# ... existing adapter loop populates identity_table, entities ...
# ... existing _load_legacy_records loop ...

entities.sort(key=lambda e: e.canonical_id)

relations = _load_structured_relations(project_root, local_profile=local_profile)
relations.extend(_entity_nested_relations(entities))
relations.extend(_legacy_nested_relations(..., "models.yaml", ...))
relations.extend(_legacy_nested_relations(..., "parameters.yaml", ...))
bindings = _load_binding_sources(project_root, local_profile=local_profile, ...)

# NEW: commons-loading pass runs LAST, with full visibility into refs from
# entities + relations + bindings.
commons_entities, commons_overlay_paths = _load_commons_referenced_entities(
    project_root,
    project_slug=project_slug,
    project_entities=entities,
    project_relations=relations,
    project_bindings=bindings,
    identity_table=identity_table,
    registry=registry,
    active_kinds=active_kinds,
)
for entity, ref in commons_entities:
    if entity.canonical_id in identity_table:
        raise EntityIdentityCollisionError(entity.canonical_id, identity_table[entity.canonical_id], ref)
    identity_table[entity.canonical_id] = ref
    entities.append(entity)
    entity_source_adapters[entity.canonical_id] = ref.adapter_name

# Re-sort so the returned ProjectSources.entities is fully sorted including
# the commons-derived entries.
entities.sort(key=lambda e: e.canonical_id)
relations.sort(...)

# ProjectSources gains commons_overlay_paths field for §5.5 provenance emission.
```

Two structural points:

1. **Order**: commons load runs LAST, after relations + bindings are in scope. This closes the gap where refs in `knowledge/sources/local/relations.yaml` or in parameter bindings would otherwise be invisible to the commons-need collector.
2. **Re-sort**: `entities` is sorted twice — once before commons load (so existing relations/bindings loaders see a stable list), once after (so the returned `ProjectSources.entities` is fully sorted).

**No second `_entity_nested_relations` call.** A draft of this design called `_entity_nested_relations` a second time on the commons-derived entities, motivated by getting their `related:` lists into the authored-relations stream. That rationale was wrong: `_entity_nested_relations` only flattens an entity's typed `relations:` block (see `sources.py:639` — it checks `entity.relations`, not `entity.related`). The freeform `related:` list is emitted as triples at materialize time by `_add_relations` (`materialize.py:277` walks `entity.related`), which runs uniformly over every Entity in `sources.entities` regardless of origin. Commons topics/papers/themes don't carry typed `relations:` blocks today, so the second call would have been a no-op. Dropping it.

The helper lives in a dedicated module `science/src/science_tool/graph/commons_sources.py`. `sources.py` only gains the one call site plus the import.

### 3.2 Module layout

```
science_tool/graph/
├── sources.py                  ← +1 call site, +1 import
├── commons_sources.py          ← NEW. Whole integration lives here.
│   ├── collect_referenced_commons_ids(entities, relations, bindings) -> set[str]
│   ├── _load_commons_referenced_entities(...)
│   │       -> tuple[list[tuple[Entity, SourceRef]], dict[str, str]]
│   │       # second element is canonical_id -> overlay_path (see §4.5)
│   ├── _materialize_commons_entity(merged, registry, ...) -> Entity
│   └── _commons_source_ref(canonical_id, type_dir, slug) -> SourceRef
```

### 3.3 Dependency direction

`commons_sources.py` imports from `science_tool.commons.{adapter,overlay,query,config}` and from `science_model.entities`. Nothing in `science_tool.commons.*` imports from `graph.*`. One-way arrow: graph → commons. Matches the inventory-v2 precedent (`entities_inventory.py:23`).

### 3.4 No-op for non-Phase-F projects

If `OverlayAdapter(project_root, project).scan()` yields nothing AND no project entity reference targets a `<type>:<slug>` in `{dataset, paper, topic, theme}` that is absent from `identity_table`, the helper returns `[]`. Zero behavior change. The OverlayAdapter walk of `doc/{datasets,papers,topics,themes}/` is bounded and cheap (and short-circuits when the subdir doesn't exist).

### 3.5 Commons-root resolution

Uses the existing `resolve_commons_root()` (env var → global config → `~/d/science-commons`). If the root doesn't exist:

- Project has zero overlays AND zero commons refs → silent no-op (DEBUG log only).
- Project has either → raise `CommonsRootNotFoundError`. Strict semantics, consistent with the failure model in §6.

### 3.6 Caching scope

Per-`load_project_sources` call. `CommonsQuery` is constructed once per build; no cross-call cache. Builds are infrequent enough that this is fine and avoids cache-invalidation bugs across test sessions.

## 4. Data flow

`_load_commons_referenced_entities` runs in four steps.

### 4.1 Collect the "needed" set

```python
referenced = collect_referenced_commons_ids(
    project_entities,
    project_relations=relations,
    project_bindings=bindings,
)
# Walk every <type>:<slug> reference from THREE sources, matching
# the three audit paths in graph/migrate.py:
#   (a) entity fields: related, source_refs, evidence_refs, participants,
#       propositions, derived_from, blocked_by, etc.
#   (b) authored relations: SourceRelation.subject and .object from
#       knowledge/sources/local/relations.yaml and from legacy nested
#       relations in models.yaml / parameters.yaml.
#   (c) parameter bindings: SourceBinding.model, .parameter, AND
#       .source_refs. (graph/migrate.py:_audit_binding audits all three;
#       collection must mirror or commons IDs used only in
#       binding.source_refs fail unresolved.)
# Filter to <type> ∈ {dataset, paper, topic, theme} AND id NOT in identity_table.

overlays_by_id = {}
for rec in OverlayAdapter(project_root, project_slug).scan():
    if isinstance(rec, OverlayValidationError):
        raise rec  # strict mode: malformed overlay aborts build
    overlays_by_id[rec.canonical_id] = rec

needed = referenced | overlays_by_id.keys()
```

Two notes:

- **Union semantics**: an overlay with no inbound ref still produces an entity (the project explicitly carries it), and a ref to a commons ID with no local overlay still resolves.
- **Three-source collection** closes the M3 gap: refs that live only in `relations.yaml` or in `parameter_bindings.yaml` are now visible to the commons loader.

### 4.2 Resolve each needed ID against commons

The behavior on missing canonical depends on whether the ID is anchored by a project overlay:

- **Referenced-only ID, missing in commons**: skip the helper-level load. The ID never enters `identity_table`, so the existing audit path emits an `unresolved_reference` row downstream and graph build aborts via the existing strict-audit failure (see §6.3 for the enriched message). This is the M4-correct path.
- **Overlay-anchored ID, missing in commons**: hard error here. The project carries an overlay file for an entity that doesn't exist in commons — an orphan overlay, which §6.1 classifies as a fatal `OverlayValidationError`.

```python
commons_query = CommonsQuery(resolve_commons_root())
for canonical_id in sorted(needed):
    overlay = overlays_by_id.get(canonical_id)
    try:
        record = commons_query.show(canonical_id)
    except CommonsEntityError as exc:
        if overlay is not None:
            # Orphan overlay — hard error (§6.1).
            raise OverlayValidationError(
                overlay.overlay_path,
                canonical_id=canonical_id,
                cause=exc,
            ) from exc
        # Referenced-only and missing — skip; audit will emit the
        # unresolved_reference row downstream.
        continue
    merge_policy = read_merge_policy(parse_profile(record.schema_profile))
    merged = merge_entity(record, overlay, merge_policy)
```

`merge_entity` is the existing function in `commons/overlay.py`. Reused verbatim.

### 4.3 Translate `MergedEntity` → `science_model.Entity`

**Strategy: pass-through + normalize.** Copy the merged frontmatter into the raw dict verbatim, then apply only the targeted normalizations needed to bridge commons-side naming/shape conventions to the Entity model. This is essential — `DatasetEntity` carries ~10 dataset-mixin fields (`origin`, `access`, `derivation`, `accessions`, `datapackage`, `local_path`, `consumed_by`, `parent_dataset`, `siblings`) plus the access/derivation invariants in `_fill_derived_defaults` / `_validate_kind_type_consistency`. A handwritten subset would silently lose them; pass-through carries them automatically.

```python
def _materialize_commons_entity(merged, registry, project_slug, active_kinds, ontology_catalogs):
    fm = dict(merged.merged_frontmatter)
    kind = _normalize_kind(fm["type"])         # "topic" | "paper" | "dataset" | "theme"
    schema = registry.resolve(kind)             # raises EntityKindNotRegisteredError if not registered

    # Start with the full merged frontmatter — every commons + overlay-policy
    # field flows into the Entity dict.
    raw: dict[str, object] = dict(fm)

    # Normalize the small set of fields that differ in name/shape between
    # commons frontmatter and the Entity model.
    raw["kind"] = kind
    raw["canonical_id"] = fm["id"]              # Entity uses canonical_id; commons uses id
    if "description" in fm and "summary" not in fm:
        raw["summary"] = fm.pop("description")  # commons `description:` -> Entity `summary`
    # `source_refs:` is the field name in commons topic/theme/paper fixtures,
    # in overlay-1.1.json, AND on the Entity model — no rename needed; the
    # pass-through carries it. (The multiproject design's draft `sources:` name
    # was renamed before fixtures shipped; verified no production file uses it.)

    # Commons-derived provenance & display metadata.
    raw["scope"] = "shared"                     # EntityScope.SHARED
    raw["profile"] = "shared"                   # fixed sentinel for downstream display (§5.3)
    raw["file_path"] = str(merged.canonical.body_path)

    # Drop overlay-only fields the graph doesn't carry (per §5.4).
    for overlay_only in ("relevance", "hypothesis_links", "task_links", "project_tags"):
        raw.pop(overlay_only, None)

    # Drop fields the commons schema carries but the Entity model rejects.
    raw.pop("schema_profile", None)             # commons-side metadata; not an Entity field
    raw.pop("id", None)                         # superseded by canonical_id above

    _enrich_raw(raw, kind=kind, project_slug=project_slug,
                local_profile="shared", active_kinds=active_kinds,
                ontology_catalogs=ontology_catalogs)
    return schema.model_validate(raw)
```

**What this changes for each kind:**

- **`topic`** → `ProjectEntity` with `related:` and `source_refs:` populated from commons + overlay-append merge. No dataset/theme-specific fields.
- **`paper`** → `ProjectEntity` with paper-mixin fields (`bibkey`, `authors`, `year`, `journal`, `doi`, `url`, `datasets`, `key_findings`, `methods_summary`) flowing through. These aren't separate Entity fields today — they're carried in the raw dict and silently dropped by pydantic's `extra="ignore"` policy. Future work: promote them to Entity fields if downstream needs them; out of scope here.
- **`theme`** → `ThemeEntity` with `theme_kind:` and `theme_scope:` carried through verbatim. Both `theme_scope: "cross-project"` and `theme_kind ∈ {conceptual, empirical, domain}` now validate because of the §2 ThemeEntity Literal extensions.
- **`dataset`** → `DatasetEntity` with the full dataset-mixin (`origin`, `access`, `derivation`, `accessions`, `datapackage`, `parent_dataset`, `siblings`, `consumed_by`) carried verbatim. The model's `@model_validator` for invariants #7 / #8 (origin ⟺ access vs derivation block) runs unchanged.

**Validation strictness assumption.** Entity / ProjectEntity / ThemeEntity / DatasetEntity use pydantic's default `extra="ignore"` for the base Entity (verified at `science_model/entities.py:_fill_derived_defaults` — no `model_config = ConfigDict(extra="forbid")`). Pass-through extra fields are silently dropped, NOT raised. If a future Entity tightens to `extra="forbid"`, this strategy needs the explicit drop list to grow — easy to spot via the existing test surface.

The translation lives in `commons_sources.py`. The model stays generic; the graph layer owns the commons-shape → Entity-shape mapping. Matches how `MarkdownAdapter` and `TaskAdapter` already produce dicts fed into `schema.model_validate`.

### 4.4 Register

Each translated Entity goes into `identity_table` and `entities`, paired with a synthetic `SourceRef` whose `path` is a human-readable `commons://<type_dir>/<slug>.md` form (used in audit-row messages) and whose `adapter_name` is `"commons-merged"`. The exact `SourceRef` constructor signature is an implementation detail of `science_model.source_ref.SourceRef`; the design's commitment is to the values, not to the API shape.

The `EntityIdentityCollisionError` guard catches the (pathological) case where the project ALSO declares the same canonical_id locally. After Phase F this shouldn't happen; the guard stays as defense in depth.

### 4.5 Carry overlay paths for provenance emission

The translated `Entity.file_path` carries the **commons** body path. The **overlay** path (when an overlay was merged) is needed at materialize time to emit a second `prov:wasDerivedFrom` triple (see §5.5). The Entity model has no field for it, so `_load_commons_referenced_entities` additionally returns a side-table:

```python
commons_overlay_paths: dict[str, str]   # canonical_id -> overlay_path
```

`ProjectSources` gains this field (default `{}` for projects with no overlays). `materialize_graph` threads it into the `_add_entity` call so the second provenance triple can be emitted.

### 4.6 Downstream invariance

Once registration completes, `entities` contains both project-local and commons-derived `Entity` instances. Every downstream consumer — `build_alias_map`, `ReferenceResolver`, `audit_project_sources`, `_build_dataset_from_sources`, `materialize_graph`, freshness — works unchanged. The strict-audit failure path now succeeds for commons IDs because they're in `identity_table`.

## 5. Entity translation details

### 5.1 Kind mapping

All four commons kinds are already registered in `EntityRegistry.with_core_types()`:

| commons type dir | kind label | Entity class | EntityClass |
|---|---|---|---|
| `topics/<slug>.md` | `topic` | `ProjectEntity` | `REFERENCE` |
| `papers/<slug>.md` | `paper` | `ProjectEntity` | `OPERATIONAL` |
| `themes/<slug>.md` | `theme` | `ThemeEntity` | `EPISTEMIC` |
| `datasets/<slug>/entity.md` | `dataset` | `DatasetEntity` | `OPERATIONAL` |

No registry changes. The `CommonsEntityRecord.type` field is the kind label (verified in `commons/adapter.py:_TYPE_DIR_TO_TYPE`).

### 5.2 Scope

Every commons-derived Entity sets `scope = EntityScope.SHARED`. A new predicate `SCI_NS.scope` is registered in `graph/store.py` alongside `SCI_NS.profile` / `SCI_NS.domain`. Every Entity emits a scope triple:

```python
# materialize.py:_add_entity — add ~3 lines after existing identifier/title/summary triples
scope_value = "cross-project" if entity.scope is EntityScope.SHARED else "project"
knowledge.add((uri, SCI_NS.scope, Literal(scope_value)))
```

Project-local entities get `scope="project"` too. Symmetry, and downstream consumers stay explicit about the boundary instead of inferring from absence.

### 5.3 Field mapping

Pass-through-plus-normalize (§4.3). The table below lists every field that gets **explicit** treatment in `_materialize_commons_entity`; all other fields in `merged_frontmatter` flow into the raw dict verbatim and either populate matching Entity fields or are silently dropped by pydantic's `extra="ignore"` policy.

| Entity field | Source / treatment |
|---|---|
| `canonical_id` | merged_frontmatter `id` (renamed) |
| `kind` | merged_frontmatter `type` (run through `_normalize_kind`) |
| `summary` | merged_frontmatter `description` if `summary` not already present (commons uses `description:`, Entity uses `summary`) |
| `source_refs` | pass-through (commons fixtures, overlay 1.1, and Entity all use the same field name `source_refs`) |
| `scope` | hardcoded `"shared"` → `EntityScope.SHARED` |
| `profile` | hardcoded `"shared"` (fixed sentinel; carried for downstream provenance/display; not consulted by `build_alias_map`, which keys off `canonical_id` and `aliases` only) |
| `file_path` | `str(merged.canonical.body_path)` — absolute path into `~/d/science-commons/...` |
| `title`, `tags`, `related`, `aliases`, `domain`, `status`, `confidence` | pass-through (merged in `merge_entity` per overlay policy for the array fields) |
| **dataset-mixin** (`origin`, `access`, `derivation`, `accessions`, `datapackage`, `local_path`, `consumed_by`, `parent_dataset`, `siblings`) | pass-through — `DatasetEntity` invariants #7/#8 run on the populated raw dict |
| **theme-mixin** (`theme_kind`, `theme_scope`) | pass-through — both fields validate after the §2 ThemeEntity Literal extensions (union of model + mixin vocabularies) |
| **paper-mixin** (`bibkey`, `authors`, `year`, `journal`, `doi`, `url`, `datasets`, `key_findings`, `methods_summary`) | pass-through — Entity model doesn't define these fields today, so pydantic drops them silently. Captured as a known gap; promoting them to Entity fields is out of scope here |
| **explicitly dropped** | `schema_profile`, `id` (replaced by `canonical_id`), `relevance`, `hypothesis_links`, `task_links`, `project_tags` (overlay project-only per §5.4) |

For datasets specifically: only `entity.md` becomes the Entity. The sibling `datapackage.yaml` is NOT loaded here; it stays reachable via `science data resolve` per the multiproject design §4.

### 5.4 Overlay-contributed fields

The overlay schema permits `PROJECT_ONLY` and `APPEND` merge policies; `merge_entity` already implements both. Per-field behavior depends on the canonical schema's `science:merge` annotation (for canonical fields) and `read_overlay_merge_policy()` (for overlay-only fields). The graph layer is neutral to which policy applies — it consumes the post-merge `merged_frontmatter` dict that `merge_entity` produces.

Two cases worth being explicit about:

- **Canonical fields the overlay also writes (e.g. `tags:`, `related:`)** — the merged value depends on the canonical schema's policy. APPEND merges the two lists with dedup; PROJECT_ONLY replaces with the overlay value. Either way, the merged Entity emits triples for whatever ends up in the merged list. Most mm30 topic overlays touch `tags:` rather than `related:`, so the canonical's `related:` typically passes through unchanged.

- **Overlay-only fields** (`relevance`, `hypothesis_links`, `task_links`, `project_tags` per `2026-05-13-multiproject-schema-and-shared-store-design.md` §5.1) — these don't map to any current Entity field. **Dropped in this phase.** They're surfaced by inventory_v2 already; the graph doesn't need them. If a future task needs them queryable in trig, it's a one-line addition to `_add_entity`.

### 5.5 Provenance

For commons-derived entities, two `prov:wasDerivedFrom` triples instead of one when an overlay is present. The URIs are produced by the existing `_source_uri()` helper (`materialize.py:811`), which maps a source path to a `PROJECT_NS["source/<slug>"]` URI by lowercasing the path and replacing `/` and spaces with `_`:

```turtle
# Project: mm30 (PROJECT_NS = http://example.org/mm30/)
<http://example.org/mm30/entity/topic/epigenetic-chromatin-mm-progression>
    prov:wasDerivedFrom <http://example.org/mm30/source/_home_keith_d_science-commons_topics_epigenetic-chromatin-mm-progression.md> ,
                       <http://example.org/mm30/source/doc_topics_epigenetic-chromatin-mm-progression.md> .
```

Two notes on the URIs:

- The slugified form preserves enough of the original path that distinct sources produce distinct URIs (a commons body and a project overlay never collide).
- The URIs are project-namespace, not `file://`. This matches how `_source_uri` already emits provenance for project-local entities. No file-URI conversion is in scope for this design — that would be a separate provenance-model change.

The existing `_add_entity` emits the canonical-body triple unchanged (from `entity.file_path`, which we set to `merged.canonical.body_path`). The overlay triple is emitted by extending `_add_entity` with an optional `overlay_paths: dict[str, str]` argument:

```python
def _add_entity(*, entity, knowledge, provenance, overlay_paths=None):
    # ... existing emission ...
    source_uri = _source_uri(entity.file_path)   # commons body
    provenance.add((uri, PROV.wasDerivedFrom, source_uri))
    provenance.add((source_uri, RDF.type, PROV.Entity))
    provenance.add((source_uri, SCHEMA_NS.identifier, Literal(entity.file_path)))

    if overlay_paths and (overlay_path := overlay_paths.get(entity.canonical_id)):
        overlay_uri = _source_uri(overlay_path)
        provenance.add((uri, PROV.wasDerivedFrom, overlay_uri))
        provenance.add((overlay_uri, RDF.type, PROV.Entity))
        provenance.add((overlay_uri, SCHEMA_NS.identifier, Literal(overlay_path)))
```

`overlay_paths` comes from `sources.commons_overlay_paths` (§4.5). For project-local entities or commons entities without an overlay, the dict lookup misses and only the canonical-body triple is emitted. Default `overlay_paths=None` means existing callers don't need to change.

## 6. Failure model

Strict semantics throughout. See §2 in-scope: `commons_sources` matches today's "unresolved refs are fatal" behavior.

### 6.1 Hard errors (graph build aborts)

| Condition | Exception | Where it fires |
|---|---|---|
| Project ref `<type>:X` and no `<type>:X` in commons, no local entity | existing `unresolved_reference` audit row | `audit_project_sources` — the ID was never added to `identity_table`. Existing path. |
| Project has overlay `doc/<type>/X.md` but commons has no `<type>:X` | `OverlayValidationError` re-raised | `commons_sources.py` after `CommonsQuery.show` fails for the overlay's canonical id |
| Overlay frontmatter fails its schema | `OverlayValidationError` (existing) | `OverlayAdapter.scan` |
| Overlay `overlay_of: <type>:Y` doesn't match path-derived `<type>:X` | `OverlayValidationError` (existing) | `OverlayAdapter._build` |
| Commons store root doesn't exist AND project has overlays-or-refs | `CommonsRootNotFoundError` (existing) | first `resolve_commons_root()` call |
| Commons entity declares a `type:` that isn't a registered kind | `EntityKindNotRegisteredError` (existing) | `registry.resolve(kind)` in `_materialize_commons_entity` |
| `merge_entity` hits a field with `REPLACE` or `FORBIDDEN` merge policy that an overlay tried to write | `OverlayMergeError` (existing) | `merge_entity` |
| Two commons entities with the same canonical_id | `EntityIdentityCollisionError` (existing) | identity-table guard in `load_project_sources` |

### 6.2 Warnings (logged, build continues)

| Condition | Why warn-only |
|---|---|
| Overlay sets `pin_version` and commons HEAD `version` differs | `2026-05-14-commons-overlay-merge-design.md` D1 explicitly defers pin enforcement to a later phase. Match that. |
| Overlay sets `pin_effective_version` | Same — escape-hatch field, also deferred. |
| Project has no overlays, no commons refs, AND commons root missing | DEBUG log only; not even a warning. True no-op. |

### 6.3 Audit-row message enrichment

The materialize_graph error path joins audit rows with `"; "` (`materialize.py:168`). For commons-typed unresolved references (where the audit-row `target` is `<type>:<slug>` with `<type>` ∈ {dataset, paper, topic, theme}), the existing `_audit_reference` / `_audit_relation_endpoint` / `_audit_binding_endpoint` templates gain a hint pointing at the commons path that would resolve it:

```
doc/topics/X.md references topic:X — no local entity, no commons canonical at
~/d/science-commons/topics/X.md (run `science commons promote topic --from <project>`
if X should be promoted, or check the ref's spelling)
```

The enrichment is purely informational. It fires whether or not commons even has a directory entry — the goal is to surface the lookup path the resolver attempted. The audit row's `check` value stays `unresolved_reference` (no new check type).

## 7. Test surface

### 7.1 Unit tests — `science/tests/test_graph_commons_sources.py` (NEW)

| Test | Asserts |
|---|---|
| `test_no_overlays_no_refs_is_noop` | Project with no `doc/topics/`, no commons refs → helper returns `[]`, no commons-root resolution attempted |
| `test_commons_root_missing_with_overlays_raises` | Project has overlays, `SCIENCE_COMMONS_ROOT` doesn't exist → `CommonsRootNotFoundError` |
| `test_commons_root_missing_without_anything_silent` | No overlays, no commons refs, missing commons root → no exception, no warning at WARNING level |
| `test_referenced_topic_loads_canonical_only` | Project has `related: topic:X`, commons has `topics/X.md`, no overlay → returns one Entity with `scope=SHARED`, `kind=topic`, fields from commons frontmatter |
| `test_referenced_topic_loads_canonical_plus_overlay` | Same + project has overlay → merged Entity; `related` contains both canonical-curated and overlay-appended items; provenance has two source URIs |
| `test_overlay_without_ref_still_loaded` | Project has overlay, no project entity refs the canonical → still emitted (union semantic from §4.1) |
| `test_referenced_missing_canonical_audits_not_aborts` | Project refs `topic:Z`, commons has no `Z.md`, no overlay → helper SKIPS (does not raise); `audit_project_sources` emits an `unresolved_reference` row; `materialize_graph` aborts via the existing strict-audit path. Pinned to lock the §4.2 referenced-only behavior. |
| `test_orphan_overlay_raises` | Project has overlay `doc/topics/Y.md`, commons has no `topics/Y.md` → `OverlayValidationError` raised from helper at `CommonsQuery.show` time, NOT swallowed |
| `test_commons_ref_only_in_relations_yaml_resolves` | Commons ID appears only in `knowledge/sources/local/relations.yaml` (no entity uses it) → helper still loads the canonical. Locks the §4.1 three-source collection. |
| `test_commons_ref_only_in_binding_endpoint_resolves` | Commons ID appears only in `SourceBinding.model` or `.parameter` → helper still loads the canonical. |
| `test_commons_ref_only_in_binding_source_refs_resolves` | Commons ID appears only in `SourceBinding.source_refs` (not in `.model` / `.parameter`) → helper still loads the canonical. Mirrors `graph/migrate.py:_audit_binding:514` which audits this field. |
| `test_dataset_kind_loads_with_mixin_fields` | Commons `datasets/foo/entity.md` carries `origin: external` + `access:` block → translated Entity is a `DatasetEntity` with `origin`, `access`, `accessions`, `datapackage` all populated. Invariants #7/#8 run on the populated raw dict. |
| `test_theme_cross_project_scope_validates` | Commons theme with `theme_scope: "cross-project"` → `ThemeEntity` validates after the §2 Literal extension. |
| `test_theme_mixin_kind_validates` | Commons theme with `theme_kind: "conceptual"` (or `empirical` / `domain`) → `ThemeEntity` validates after the §2 Literal extension. Pinned as a regression for the kind-vocabulary union. |
| `test_overlay_pin_version_mismatch_warns` | Overlay `pin_version: "0.9.0"`, commons HEAD `version: "1.0.0"` → `logger.warning` containing both versions; build succeeds |
| `test_commons_entity_with_unknown_kind_raises` | Synthetic commons entity with `type: galaxy` → `EntityKindNotRegisteredError` |
| `test_collision_with_local_entity_raises` | Project declares `topic:X` locally AND commons has `topic:X` → `EntityIdentityCollisionError` |

Fixtures reuse the existing `science/tests/fixtures/overlays/` plus a tmp commons-root constructed per test.

### 7.2 End-to-end — extend `test_graph_materialize.py`

- `test_materialize_with_commons_topic_emits_scope_triple` — full pipeline; assert the resulting trig contains `sci:scope "cross-project"` for the commons entity and `sci:scope "project"` for a local entity.
- `test_materialize_with_overlay_emits_dual_provenance` — assert `prov:wasDerivedFrom` triples exist for both commons body and overlay path.

### 7.3 Audit regression — extend `test_graph_migrate.py`

- `test_audit_resolves_commons_referenced_topic` — pre-feature this was an unresolved-ref row; post-feature it resolves. Pinned as a regression test for the bug class.

### 7.4 mm30 canary — `science/tests/test_graph_commons_mm30_canary.py` (NEW)

A small synthetic project that reproduces the four problem patterns observed in mm30:

| Pattern | mm30 example | Canary asserts |
|---|---|---|
| Hypothesis spec references a commons topic | `specs/hypotheses/h4-attractor-convergence.md` related `topic:cancer-as-singular-evolutionary-disease` | One unresolved ref pre-feature; zero post-feature |
| Interpretation references a commons topic | `doc/interpretations/2026-04-23-t650-…md` related `topic:formal-causal-mediation` | Same |
| Task file references a commons topic | `task:t286` related `topic:causal-inference-biology-foundations` | Same |
| Project has overlay AND outbound refs to the same topic | `doc/topics/epigenetic-chromatin-mm-progression.md` is an overlay; `hypothesis:h4-attractor-convergence` refs the same id | Single entity emitted, two provenance sources |

Fixture project lives at `science/tests/fixtures/commons_mm30_canary/` (project tree + commons stub).

### 7.5 Acceptance test (manual, not CI)

Once the test suite passes, run against the live mm30 repo:

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma
uv run science graph build --project-root .
```

Expected: build succeeds. The 65 unresolved references observed pre-feature (16 unique topic IDs + 1 dataset ID) resolve cleanly. Validate-script warning count drops by the corresponding amount.

### 7.6 What's NOT tested in this phase

- `pin_version` actually loading historic commons content (deferred per overlay-merge D1).
- Cross-graph queries (no `commons.trig` in scope).
- Performance regression — adds O(needed-set) commons reads per build; on mm30 that's ~16 reads, well below noise.

## 8. Open questions

None blocking. Documented decisions:

- Overlay project-only fields (`relevance`, `hypothesis_links`, `task_links`, `project_tags`) are dropped from the graph in this phase, surfaced via inventory_v2 only (§5.4).
- `pin_version` is warn-only, no git history checkout (§6.2).
- `sci:scope` is a new predicate emitted for every entity, not just commons-derived ones (§5.2).
- `_load_commons_referenced_entities` is one new function in one new module; no `StorageAdapter` refactor (§3.1).
- Commons reads happen per-build, no cross-build cache (§3.6).
- Two targeted ThemeEntity Literal extensions: `theme_scope` gains `"cross-project"` and `theme_kind` gains `conceptual`/`empirical`/`domain` to match the existing mixin-theme-2.0 vocabulary (§2 "Targeted schema changes"). Vocabulary harmonization is a separate task.
- Commons-entity translation uses pass-through + normalize, not handwritten field subset (§4.3). Dataset/theme/paper mixin fields flow through automatically.
- Reference collection scans entities + structured relations + binding endpoints + binding `source_refs` (§4.1), mirroring the three audit paths in `graph/migrate.py`.
- Missing commons canonical: hard error for orphan overlays, audit-row path for referenced-only (§4.2).
- Paper-mixin fields (`bibkey`, `authors`, …) flow through pydantic's `extra="ignore"` and are NOT emitted as triples. Out of scope to promote them to Entity fields here.
- Provenance URIs use `_source_uri()` (project-namespace, slugified path), not `file://` URIs. Matches existing emission for project-local entities (§5.5).
- No second `_entity_nested_relations` pass — `entity.related` triples are emitted by `_add_relations` at materialize time for all entities uniformly; commons entities don't carry typed `relations:` blocks (§3.1).
