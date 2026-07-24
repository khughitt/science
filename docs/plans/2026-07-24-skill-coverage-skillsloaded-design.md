# `skills_loaded` Truth Path + Reified Materialization (Skill-Coverage sub-plan 2) — Design

> **Status:** design / spec, approved for planning. Part of Plan 2 (the skill-coverage
> layer) of the data-product-vocabulary program. Parent design:
> [`2026-07-23-data-product-vocabulary-and-skill-coverage-design.md`](2026-07-23-data-product-vocabulary-and-skill-coverage-design.md)
> (§"`skills_loaded` absorption (single truth path, reified)" and the RDF identity contract).
> Sibling shipped sub-plans: enrollment
> ([`2026-07-23-skill-coverage-enrollment-implementation.md`](2026-07-23-skill-coverage-enrollment-implementation.md))
> and the gen-3 write-path fix
> ([`2026-07-23-skill-coverage-writepath-implementation.md`](2026-07-23-skill-coverage-writepath-implementation.md)).

## Motivation

The parent design establishes a **single truth path** for the skills an analysis loaded:
migrate legacy plans onto a typed `skills_loaded` field, canonicalize the skill ids, and
materialize a **reified skill-load record** into the project graph so general graph consumers
can query "which analysis loaded which skill." This sub-plan builds that machinery in the
toolkit. The coverage command that *reads* it, the packaged skill inventory it will later be
checked against, and the real downstream data migration are all separate, later slices.

## Grounding findings that shape the design

- **`kind: analysis-plan` is already retired as an entity kind; `plan` is the sole kind**
  (`science-model/profiles/core.py:448`, `entities.py:98`). The current authoring convention
  is `kind: plan` + a **free-form** `plan_kind: analysis-plan` frontmatter string
  (`commands/plan-analysis.md:124`), asserted only by a command-doc test — there is no model
  or schema backing for `plan_kind`.
- **No typed `skills_loaded` field exists** on any Pydantic model or JSON schema. Every hit is
  documentation/command/test (`commands/plan-analysis.md:58,129`; the generated Codex mirror;
  `test_command_docs.py:746`). **No entity in this repo carries `skills_loaded`** — the "16
  legacy sources" cited in the parent design live in downstream consumer projects.
- **`plan` is base `Entity`** — no `PlanEntity` subclass — and `plan` is neither in
  `PROJECT_MIXIN_NAMES` (`{"hypothesis"}` only, `entity_schema/profile.py:24`) nor in the
  generation matrix `_MIXIN_VERSION_BY_GENERATION` (`profile.py:92-95`, which covers
  dataset/paper/topic/theme/hypothesis). There is no existing gen-3 hook for plan entities.
- **A clean reification precedent exists** — `graph/dataset_usage.py`:
  - `DatasetUsageRecord` dataclass (`:34`) carries **both** a categorical `source: UsageSource`
    (`:40`) and a separate `source_path: str` (`:41`); `UsageSource` is a
    `Literal["authored", "derivation.inputs", …]` (`:19-25`) — a **projection-source category**,
    not a file path;
  - deterministic URI `usage_node_uri(record)` (`:240-243`): JSON-canonicalize `payload()` →
    SHA-256 → `PROJECT_NS["dataset-usage/{digest}"]` — the hash covers the **whole** `payload()`;
  - `add_usage_record_to_graph(record, graph)` (`:254-263`) emits the reified triples, and
    `sci:usageSource` carries the **categorical** `source`, never the path;
  - predicates registered in `PREDICATE_REGISTRY` (`graph/store/constants.py:202-226`) all at
    layer `graph/provenance`; the literal predicates whitelisted in
    `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (`constants.py:75-77`);
  - materialized by a dedicated pass `_add_dataset_usage_edges` (`materialize.py:1446-1456`) that
    computes records **fresh** from `sources.entities` (dataset-usage is not generation-gated).
- **The validated generation is available at load but discarded before materialization.**
  During load the generation is in hand as `project_schema._generation` — the gen-3 capability
  hook gates on it (`sources.py:1304-1317`, `project_schema._generation != 3`). But
  `ProjectSources` (`sources.py:186-234`) retains **no** `entity_schema_version`, so a later
  materialization pass over `sources.entities` cannot tell a gen-3 plan from a gen-2 plan with a
  stray `skills_loaded`. Generation-gated emission must therefore be decided at load time.
- **Layer `graph/provenance` already exists** (`graph/store/constants.py:32`) and is *not* in
  `GRAPH_EXPORT_VISIBLE_LAYERS` (internal/non-exported by default) — the correct destination.
- **No skill-id alias table / canonicalization exists** anywhere in `science_tool` or
  `science-model`. `sci:usageSource` is already a registered predicate (reusable);
  `sci:hasSkillLoad`, `sci:skill`, `sci:loadReason` are new. All skill leaf names in the corpus
  are lowercase kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`).

## Design

### 1. Scope and boundaries

Toolkit machinery only, exercised by **synthetic in-repo fixtures**. Independent of sub-plan 3
(no packaged skill inventory is consulted). The `analysis-plan → plan` + `skills_loaded`
migration of the 16 downstream plans is **deferred to the release-coordinated external
migration**, matching the 1b / Tasks-13-14 precedent. Before any bespoke migrator is written
later, check whether existing kind/field migration machinery already covers the flip.

### 2. Load-time validation + record production (one pass, generation in hand)

`skills_loaded` stays **preserved-raw** on `Entity` (`extra="allow"`) — it is **not** a typed
field on the base model and `plan` does **not** join `PROJECT_MIXIN_NAMES` or the mixin
matrix. This matches the parent design's decision for the capability fields and the standing
"no strict plan mixin in v1" invariant, and it puts the generation gating in exactly one place.

Because the validated generation is only available during load (grounding above), validation
and record production are the **same load-time pass**, not two passes. A shared helper
`build_skill_load_records(plan, *, aliases)` runs during the load path — where
`project_schema._generation` is known — for each `kind: plan` entity that both is under
**generation 3** and carries `skills_loaded`. It validates and, on success, returns the
`SkillLoadRecord`s (§4); the records are retained on `ProjectSources` (§4) for the
materialization pass to emit. It raises **structural errors** (at the plan validation gate) for:

- **malformed shape** — `skills_loaded` is not a list, an item is not a `{id, reason}` object,
  or `id`/`reason` is missing or not a string;
- **malformed skill id** — the **post-alias** id (raw-canonical or alias target) does not match
  the canonical skill-name grammar `^[a-z0-9]+(-[a-z0-9]+)*$` (rejects `""`, whitespace,
  path-like, and URI-like ids before they can be minted into `sci:skill/<value>`). Grammar is
  applied **through the one shared canonicalization helper** (§3), so every id — from the alias
  table or not — is checked identically;
- **duplicate canonical load** — two entries resolving (after alias canonicalization) to the
  same canonical skill id under one plan, whether a literal repeat or two distinct aliases
  converging. Identity excludes `reason` (§4), so an un-rejected duplicate would silently
  collapse into one node bearing multiple `sci:loadReason` literals.

Under generation ≤ 2, `skills_loaded` is preserved-raw and **ignored** — no validation, no
record, no emission. Coverage and skill-reference findings (`unmapped-skill-reference`, the
coverage states) are **WARN diagnostics owned by sub-plan 4**, deliberately distinct in severity
from these structural errors, and out of scope here — in particular, whether a well-formed
canonical id names a *real* corpus skill is **not** checked here (that needs the packaged
inventory).

`plan_kind` remains free-form frontmatter, untyped; production is gated on generation 3 +
`skills_loaded` **presence**, never on `plan_kind`.

### 3. Skill-id alias table

A new YAML resource shipped inside `science_tool` (co-located with the reification code under
`graph/`, and the natural sibling of the sub-plan-3 packaged inventory that will also live in
`science_tool`), loaded via `importlib.resources`. It is a flat `retired-id → canonical-id`
string map, **validated at load**:

- every key and value matches the canonical skill-name grammar `^[a-z0-9]+(-[a-z0-9]+)*$`;
- **no chains** — a target (value) may **not** also appear as a key. This makes canonicalization
  exactly **one lookup** and unambiguous: for `a → b`, `a` resolves to `b`; the table can never
  express `a → b → c`, so there is no "one lookup vs terminal resolution" ambiguity to resolve
  and no way for duplicate-detection or record identity to depend on lookup depth. (Cycles are a
  degenerate chain and are rejected by the same rule.)
- duplicate keys rejected.

Canonicalization (the one shared helper): if a raw id is a key, resolve to its single target;
otherwise the raw id is treated as already canonical. **Either way the result is grammar-checked**
(§2). The table is used **only** to canonicalize (for record identity + URI) and to detect
convergence collisions — it **never** checks whether a canonical id names a real corpus skill
(that requires the packaged inventory and is deferred to sub-plan 4). Seeded minimal; real
retired→canonical entries ride along with the deferred downstream migration.

### 4. Reified RDF contract

A `SkillLoadRecord` (frozen dataclass) mirroring `DatasetUsageRecord`:

- fields `plan_id`, `canonical_skill_id`, `reason`, and `source: UsageSource` — where `source`
  is the **categorical** projection-source constant `"authored"` (the `skills_loaded` block is
  author-declared), **not** a file path. This corrects the dataset-usage semantics: the path is
  never carried in `source`, and — since `(plan_id, canonical_skill_id)` already uniquely
  identifies a load — the path is not needed in identity at all.
- a **separate `identity_payload()`** returning `{plan_id, canonical_skill_id, source}` — it
  **excludes `reason`**. The record's URI hashes **`identity_payload()`, never a `payload()`
  that includes `reason`** (avoiding the dataset-usage trap where the whole payload is hashed):
  JSON-canonicalize → SHA-256 → `PROJECT_NS["skill-load/{digest}"]`. Excluding `reason` is what
  makes the duplicate-canonical collision (§2) a real collision to reject rather than two
  distinct nodes, and makes changing only `reason` leave the node URI unchanged.

`add_skill_load_record_to_graph(record, graph)` emits into layer `graph/provenance`:

```text
(plan,  sci:hasSkillLoad, node)
(node,  RDF.type,         sci:SkillLoad)
(node,  sci:skill,        sci:skill/<canonical-name>)   # stable global skill URI
(node,  sci:loadReason,   Literal(reason))
(node,  sci:usageSource,  Literal("authored"))          # categorical, reuses the dataset-usage predicate
```

The skill URI uses the stable global scheme `sci:skill/<canonical-name>` (identical across
projects — the skills corpus is toolkit-global). **Naming note:** the predicate `sci:skill`
and the URI namespace `sci:skill/<name>` are visually close but are distinct terms; the parent
design adopted both as the stable public graph API, so this design keeps them rather than
renaming.

New predicates registered in `PREDICATE_REGISTRY` (layer `graph/provenance`): `sci:hasSkillLoad`,
`sci:skill`, `sci:loadReason`. `sci:usageSource` is reused (already registered) and keeps its
documented categorical contract. The literal predicates are added to
`GRAPH_EXPORT_EDGE_METADATA_PREDICATES` alongside the dataset-usage ones, matching precedent.

**Retention + emission.** The load-time pass (§2) stashes the produced records on a new
`ProjectSources` field `skill_loads: list[SkillLoadRecord]` (default empty) — the analogue of
the other prevalidated collections `ProjectSources` already carries (`dataset_parents`,
`identity_declarations`). Emission is then a **dedicated materialization pass**
(`_add_skill_load_edges`) mirroring `_add_dataset_usage_edges`: iterate `sources.skill_loads`
and `add_skill_load_record_to_graph(record, provenance)`. Materialization needs no generation
and does **no** re-validation — the structural errors were raised at the load-time validation
gate, and canonicalization ran once there through the one shared helper (§3), keeping a single
truth path. Deterministic record identity ⇒ **idempotent** re-materialization.

## Testing approach

- **Reification:** a synthetic gen-3 plan with `skills_loaded` materializes a reified record in
  `graph/provenance` carrying `sci:hasSkillLoad` / `RDF.type sci:SkillLoad` / `sci:skill` (URI)
  / `sci:loadReason` / `sci:usageSource = "authored"`; re-materializing identical inputs yields
  byte-identical records (idempotence via deterministic identity).
- **`reason` excluded from identity:** two records identical except for `reason` share the same
  node URI (`identity_payload()` excludes `reason`); the emitted `sci:usageSource` is the
  categorical `"authored"`, never a file path.
- **Alias canonicalization:** a plan loading a retired id materializes a record whose skill URI
  is the **canonical** `sci:skill/<canonical-name>`.
- **Malformed skill id (gen 3):** a `skills_loaded` id that is `""`, whitespace, path-like
  (`a/b`), or URI-like — whether present in the alias table or not (i.e. both a raw-canonical id
  and an alias target) — is a **hard error** at the plan validation gate, never minted into a
  `sci:skill/<value>` URI.
- **Structural errors (gen 3):** malformed `skills_loaded` (non-list; item not an object;
  missing `id`/`reason`; non-string value) is a **hard error**; a duplicate canonical load —
  both a literal repeat **and** two distinct aliases converging on one canonical id under a
  single plan — is a **hard error**, not a single record with two reasons.
- **Generation gating:** a **gen-2** plan carrying `skills_loaded` loads clean, raises nothing,
  and emits **no** skill-load record (and stashes none on `ProjectSources.skill_loads`).
- **Alias-table load:** a table with a **chain** (a target that is also a key), a duplicate key,
  or a non-grammar-conforming key/value is rejected at load.

Verification gate: full `science` and `science/model` suites, `ruff check`, `pyright`.

## Out of scope (documented boundaries)

- **The `unmapped-skill-reference` diagnostic, the coverage states, and the packaged skill
  inventory** — sub-plans 3/4. Sub-plan 2 canonicalizes and reifies; it never asks whether a
  canonical id names a real corpus skill.
- **Real alias-table seeding and the downstream data migration** of the 16 legacy plans — the
  release-coordinated external migration.
- **Typing `plan_kind`** — remains free-form frontmatter; not required for reification.
- **A `science skills coverage` command** — sub-plan 4.
