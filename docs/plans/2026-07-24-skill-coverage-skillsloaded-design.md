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
  - `DatasetUsageRecord` dataclass (`:34`) with `payload()` (`:44-53`);
  - deterministic URI `usage_node_uri(record)` (`:240-243`): JSON-canonicalize `payload()` →
    SHA-256 → `PROJECT_NS["dataset-usage/{digest}"]`;
  - `add_usage_record_to_graph(record, graph)` (`:254-263`) emits the reified triples;
  - predicates registered in `PREDICATE_REGISTRY` (`graph/store/constants.py:202-226`) all at
    layer `graph/provenance`; the literal predicates whitelisted in
    `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (`constants.py:75-77`);
  - materialized by a dedicated pass `_add_dataset_usage_edges` (`materialize.py:1446-1456`),
    a sibling of the generic `_add_entity` pass (`materialize.py:652`, called at `:372`).
- **Layer `graph/provenance` already exists** (`graph/store/constants.py:32`) and is *not* in
  `GRAPH_EXPORT_VISIBLE_LAYERS` (internal/non-exported by default) — the correct destination.
- **No skill-id alias table / canonicalization exists** anywhere in `science_tool` or
  `science-model`. `sci:usageSource` is already a registered predicate (reusable);
  `sci:hasSkillLoad`, `sci:skill`, `sci:loadReason` are new.

## Design

### 1. Scope and boundaries

Toolkit machinery only, exercised by **synthetic in-repo fixtures**. Independent of sub-plan 3
(no packaged skill inventory is consulted). The `analysis-plan → plan` + `skills_loaded`
migration of the 16 downstream plans is **deferred to the release-coordinated external
migration**, matching the 1b / Tasks-13-14 precedent. Before any bespoke migrator is written
later, check whether existing kind/field migration machinery already covers the flip.

### 2. Typed `skills_loaded` shape + generation-aware structural validator

`skills_loaded` stays **preserved-raw** on `Entity` (`extra="allow"`) — it is **not** a typed
field on the base model and `plan` does **not** join `PROJECT_MIXIN_NAMES` or the mixin
matrix. This matches the parent design's decision for the capability fields and the standing
"no strict plan mixin in v1" invariant, and it puts the generation gating in exactly one
place.

A **generation-aware structural validator**, scoped to `kind: plan`, enforces **only under
generation 3** that `skills_loaded` (when present) is a list of `{id, reason}` objects, each
with both keys present and string-valued. Violations are **structural errors** raised at the
plan validation gate:

- **malformed shape** — not a list, an item missing `id`/`reason`, a non-string value;
- **duplicate canonical load** — two entries resolving (after alias canonicalization) to the
  same canonical skill id under one `(plan, source)`, whether a literal repeat or two distinct
  aliases converging. Load-record identity excludes `reason`, so an un-rejected duplicate
  would silently collapse into one node bearing multiple `sci:loadReason` literals.

Under generation ≤ 2, `skills_loaded` is preserved-raw and **ignored** — no validation, no
emission. Coverage and skill-reference findings (`unmapped-skill-reference`, the coverage
states) are **WARN diagnostics owned by sub-plan 4**, deliberately distinct in severity from
these structural errors, and out of scope here.

`plan_kind` remains free-form frontmatter, untyped; emission (below) is gated on
`skills_loaded` **presence**, never on `plan_kind`.

### 3. Skill-id alias table

A new YAML resource shipped inside `science_tool` (co-located with the reification code under
`graph/`, and the natural sibling of the sub-plan-3 packaged inventory that will also live in
`science_tool`), loaded via `importlib.resources`. It is a flat `retired-id → canonical-id`
string map, **validated at load**:

- values (and keys) are **bare skill names** (no path separators / URI syntax);
- **no cycles** and no chains that fail to resolve to a terminal canonical id (a key may not
  also appear as a value in a way that forms a loop);
- duplicate keys rejected.

Canonicalization is: if a raw id is a key, resolve to its target; otherwise treat the raw id
as already canonical. The table is used **only** to canonicalize (for record identity + URI)
and to detect convergence collisions — it **never** checks whether a canonical id names a real
corpus skill (that requires the packaged inventory and is deferred to sub-plan 4). Seeded
minimal; real retired→canonical entries ride along with the deferred downstream migration.

### 4. Reified RDF contract

A `SkillLoadRecord` mirroring `DatasetUsageRecord`:

- `payload()` carries `(plan_id, canonical_skill_id, reason, source)`, where `source` is the
  plan's source-file path (single-source-per-plan, stable);
- **identity hash excludes `reason`**: the digest is over `(plan_id, canonical_skill_id,
  source)` only, JSON-canonicalized → SHA-256 → `PROJECT_NS["skill-load/{digest}"]`. Excluding
  `reason` is what makes the duplicate-canonical collision (§2) a real collision to reject
  rather than two distinct nodes.

`add_skill_load_record_to_graph(record, graph)` emits into layer `graph/provenance`:

```text
(plan,  sci:hasSkillLoad, node)
(node,  RDF.type,         sci:SkillLoad)
(node,  sci:skill,        sci:skill/<canonical-name>)   # stable global skill URI
(node,  sci:loadReason,   Literal(reason))
(node,  sci:usageSource,  Literal(source))              # reuses the dataset-usage predicate
```

The skill URI uses the stable global scheme `sci:skill/<canonical-name>` (identical across
projects — the skills corpus is toolkit-global). **Naming note:** the predicate `sci:skill`
and the URI namespace `sci:skill/<name>` are visually close but are distinct terms; the parent
design adopted both as the stable public graph API, so this design keeps them rather than
renaming.

New predicates registered in `PREDICATE_REGISTRY` (layer `graph/provenance`): `sci:hasSkillLoad`,
`sci:skill`, `sci:loadReason`. `sci:usageSource` is reused (already registered). The literal
predicates are added to `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` alongside the dataset-usage
ones, matching precedent.

Emission is a **dedicated materialization pass** (`_add_skill_load_edges`) mirroring
`_add_dataset_usage_edges`: iterate `sources.entities`, select gen-3 plans carrying
`skills_loaded`, build records, add them to the provenance graph. The §2 structural checks
(malformed shape, duplicate-canonical) are raised **at the plan validation gate**, so
materialization operates on already-validated plans and does not re-raise; both the validator
and this pass canonicalize ids through the **one shared helper** (§3), keeping a single truth
path. Deterministic record identity ⇒ **idempotent** re-materialization.

## Testing approach

- **Reification:** a synthetic gen-3 plan with `skills_loaded` materializes a reified record in
  `graph/provenance` carrying `sci:hasSkillLoad` / `RDF.type sci:SkillLoad` / `sci:skill` (URI)
  / `sci:loadReason` / `sci:usageSource`; re-materializing identical inputs yields byte-identical
  records (idempotence via deterministic identity).
- **Alias canonicalization:** a plan loading a retired id materializes a record whose skill URI
  is the **canonical** `sci:skill/<canonical-name>`.
- **Structural errors (gen 3):** malformed `skills_loaded` (non-list; item missing `id` or
  `reason`; non-string value) is a **hard error** at the plan validation gate; a duplicate
  canonical load — both a literal repeat **and** two distinct aliases converging on one
  canonical id under a single `(plan, source)` — is a **hard error**, not a single record with
  two reasons.
- **Generation gating:** a **gen-2** plan carrying `skills_loaded` loads clean, raises nothing,
  and emits **no** skill-load record.
- **Alias-table load:** a table with a cycle, a non-bare-name target, or a duplicate key is
  rejected at load.

Verification gate: full `science` and `science/model` suites, `ruff check`, `pyright`.

## Out of scope (documented boundaries)

- **The `unmapped-skill-reference` diagnostic, the coverage states, and the packaged skill
  inventory** — sub-plans 3/4. Sub-plan 2 canonicalizes and reifies; it never asks whether a
  canonical id names a real corpus skill.
- **Real alias-table seeding and the downstream data migration** of the 16 legacy plans — the
  release-coordinated external migration.
- **Typing `plan_kind`** — remains free-form frontmatter; not required for reification.
- **A `science skills coverage` command** — sub-plan 4.
