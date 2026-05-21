# Multi-project Science: shared entity store + unified schema

> **Status:** Design. Captures the brainstorm of 2026-05-13. Implementation plan to follow via `superpowers:writing-plans`.
>
> **Scope:** Foundational pair — unified entity schema (Frictionless-inspired base + mixins) AND the shared-store directory layout/registry. Together they unblock the rest of the multi-project roadmap (extension model details, dashboard pivot, recipes, migration tooling).

## 1. Goal & guiding principle

Make Science **multi-project at its core** by introducing a shared store for high-reuse entities (datasets, papers, topics, themes) plus a unified Frictionless-inspired schema. Projects consume shared entities through lightweight **overlays** that add project-specific context. Bulk data lives outside the synced metadata tree, content-addressed by hash, with recipes as canonical regeneration.

**Guiding principle:** *Metadata is small, versioned, and shared; bulk data is large, hashed, and out-of-tree; the recipe is canonical.*

### Problems this solves

1. **Duplicated paper / topic / dataset summaries** across projects. Each project re-summarizes Adams2025; insights don't compound.
2. **Metadata exclusion via symlink habit.** Current pattern symlinks `<project>/data/processed/<slug>/` into `/data/...`, which moves the Frictionless `datapackage.json` out of Dropbox/git alongside the bulk data, even though the metadata should have been versioned.
3. **"Taped on" cross-project tooling.** `~/.config/science/config.yaml` role/parent + `/science:sync` + external dashboard scanning are workarounds rather than a real multi-project model.
4. **No clean reuse story for cross-project work.** Once a project does a careful preprocessing pass on a public dataset, no other project can adopt it without re-running or hand-copying.

### Relation to prior in-flight work

This spec builds **on top of**, not parallel to, two recent designs:

- [`2026-05-12-science-entity-inventory-and-identity-design.md`](./2026-05-12-science-entity-inventory-and-identity-design.md) — makes Science the single authority for project entity discovery, validation, and identity. Introduces the `science_model.contracts.inventory_v1` payload as a versioned export contract.
- [`2026-05-12-science-entity-inventory-and-dashboard-consumption.md`](./2026-05-12-science-entity-inventory-and-dashboard-consumption.md) — implementation plan that ports dashboard scanning over to consume `inventory_v1`.

This spec adds a **shared-entity tier** above the per-project entity system those designs formalize. Concretely:

- A new `inventory_v2` payload (sibling to v1) carries shared entities via the existing `entities[]` list with `scope: "cross-project"`, plus a new top-level `overlays[]` list. v1 is unchanged and remains supported during migration. See §6.2.
- A new `SharedEntityAdapter` handles the shared store; it composes `entity.md` + `datapackage.yaml` pairs for datasets and reads single-file entities for papers / topics / themes. It reuses `MarkdownAdapter`'s frontmatter machinery and `DatapackageAdapter`'s YAML parsing internally rather than duplicating them, but it is a new adapter with its own scan roots — not a re-pointing of the existing project-side adapters. See §2.1.
- Identity rules (`<type>:<slug>` form, alias handling) are unchanged. Shared store reserves slugs globally within a type; project-local entities with colliding IDs warn.

A reader who has read the two 2026-05-12 docs should treat this spec as "what shared/ looks like, how projects consume it, and how to migrate to it."

---

## 2. Architecture

```
~/d/                                       # Dropbox-rooted tree
├── science/                               # tool repo — skills, templates, code
│   └── schemas/                           # JSON Schema definitions (NEW)
│       ├── base.schema.json
│       ├── mixins/{dataset,paper,topic,theme}.schema.json
│       └── extensions/bio/{rnaseq,scrna,cna,...}.schema.json
├── science-shared/                        # NEW — shared entities (its OWN git repo)
│   ├── datasets/<slug>/
│   │   ├── entity.md                      # entity surface (frontmatter + body)
│   │   ├── datapackage.yaml               # Frictionless descriptor (sibling; carries resources[] + hashes)
│   │   └── recipe/                        # Snakefile / marimo / config (required for both origins)
│   ├── papers/<bibkey>.md                 # single-file entity (no datapackage)
│   ├── topics/<slug>.md                   # single-file entity
│   ├── themes/<slug>.md                   # single-file entity
│   ├── registry.sqlite                    # regenerable index (gitignored)
│   ├── .migrations/                       # audit log for `science promote`
│   └── .git/                              # versioned independently from the science tool repo
├── protein-landscape/                     # a project (overlays only)
│   └── doc/{datasets,papers,topics,themes}/<slug>.md
└── cancer/...                             # other projects, same shape

$SCIENCE_DATA_ROOT/                        # NOT Dropbox-synced
└── <dataset-slug>/...                     # bulk data, hash-verified
                                           # default: /data/science-shared/
```

Three components, each independently testable:

- **Schema layer** (`~/d/science/schemas/`). JSON Schema definitions for base + mixins + bio extensions. Used by the validator and the CLI.
- **Shared store** (`~/d/science-shared/`). Dropbox-resident, **its own git repo** (history independent from the science tool repo). The filesystem is the source of truth; `registry.sqlite` is a regenerable index, never authoritative. The git history is what makes `pin_version:` resolvable (see §7).
- **Data resolver** (in-process library + CLI). Maps `(dataset-id, resource-path) → local filesystem path` via `$SCIENCE_DATA_ROOT` + hash verification + recipe-driven regeneration as fallback.

### 2.1 Relation to existing adapters

This design **reuses** the existing storage adapters (`MarkdownAdapter`, `DatapackageAdapter`, `AggregateAdapter`, `TaskAdapter`) rather than replacing them. Concretely:

- **A new `SharedEntityAdapter`** walks `~/d/science-shared/{datasets,papers,topics,themes}/`. For papers / topics / themes, it reads the single `.md` file directly into the existing `science_model.Entity` model with `scope = EntityScope.SHARED` (existing enum value, `science/model/src/science_model/identity.py:14`). The inventory builder maps `EntityScope.SHARED` to the export string `"cross-project"` (`science/src/science_tool/entities_inventory.py:187`) — the model uses the internal name, the contract uses the external label. For datasets, it reads `<slug>/entity.md` into the same `Entity` model — populating the existing `datapackage`, `origin`, `access`, `derivation`, `accessions`, `consumed_by`, `parent_dataset`, `siblings` fields (all already in the model per `entities.py:270-279`). The sibling `datapackage.yaml` is **not** materialized into the `Entity` model — there is no `resources` field. Resource access goes through the data resolver (§4), which reads `datapackage.yaml` on demand using the `Entity.datapackage` pointer. Surface parsing reuses `MarkdownAdapter`'s frontmatter machinery; the only new logic is locating sibling files and asserting the `entity.md` + `datapackage.yaml` pair invariant.
- **`inventory_v2` projection of resources**: when the inventory builder exports a shared dataset entity, resources are projected into `InventoryEntity.data["resources"]` (using the existing `data: dict[str, Any]` extension field on `InventoryEntity`, `inventory_v1.py:90`). This gives the dashboard a flat, self-contained view without forcing the entity model itself to grow a `resources` field. Strict structural shape of the projected payload is fixed in the v2 contract.
- **A new `OverlayAdapter`** discovers project overlay files (§5). Overlays do **not** enter the entity identity table — they are scoped to a separate `overlays` collection and merged with their canonical entity only at query time (see §5 and §6.2). This sidesteps the duplicate-`canonical_id` failure in `load_project_sources`.
- **The existing `DatapackageAdapter`** is unchanged — it continues to handle the project-side pattern of `data/*/datapackage.yaml` with the `science-pkg-entity-1.0` profile. Shared-store datapackages are reached via `SharedEntityAdapter`, which knows their canonical location and pairs them with `entity.md`.

---

## 3. Entity schema

### 3.1 Base profile

Every **shared canonical entity** satisfies the base profile (+ its type mixin + any domain extensions). **Project overlays** satisfy a separate, stricter `overlay.schema.json` (see §5.3) and do NOT need to provide base-required fields like `title`, `version`, `created`, etc. — those come from the canonical entity.

```yaml
id: "<type>:<slug>"                # globally unique within type
type: "dataset|paper|topic|theme"
title: ""
version: "1.0.0"                   # semver; required from v1
schema_profile: "science-entity-base/1.0+<mixin>/1.0[+<ext>/<ver>...]"
description: ""
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
sources: []                        # URIs, DOIs, cite keys (Frictionless-compatible)
licenses: []                       # SPDX strings or {name,path,title}
contributors: []                   # [{name, email, role}]
ontology_terms: []                 # CURIEs
tags: []
```

Slug rules are per-type:

| Type | Regex | Notes |
| --- | --- | --- |
| `dataset` | `^[a-z0-9][a-z0-9-]{1,63}$` | lowercase-kebab |
| `topic` | `^[a-z0-9][a-z0-9-]{1,63}$` | lowercase-kebab |
| `theme` | `^[a-z0-9][a-z0-9-]{1,63}$` | lowercase-kebab |
| `paper` | `^[A-Za-z][A-Za-z0-9]{1,63}$` | bibkey form (`Adams2025`, `BarrioHernandez2023`) — preserves existing convention; matches BibTeX |

Slug **uniqueness is case-sensitive within type**. The shared store reserves slugs globally within a type; project-local entities with colliding IDs warn at `science health` time.

### 3.2 Dataset mixin

A shared dataset is **two paired files**, mirroring the current dataset template (which deliberately keeps resources out of the entity surface):

- `~/d/science-shared/datasets/<slug>/entity.md` — entity surface. Governed by base + dataset mixin schemas. **Does NOT contain `resources[]`**.
- `~/d/science-shared/datasets/<slug>/datapackage.yaml` — Frictionless descriptor (carries `resources[]`, hashes, schemas). Standard Frictionless, no science-specific frontmatter.

The `datapackage:` field in entity frontmatter points to the sibling descriptor (relative path; conventionally `datapackage.yaml`). `SharedEntityAdapter` (§2.1) composes the pair into a single in-memory entity record.

**Entity surface** (`entity.md` frontmatter — dataset mixin fields):

```yaml
# Inherited from base: id, type, title, version, schema_profile, description, created, updated,
# sources, licenses, contributors, ontology_terms, tags
datapackage: "datapackage.yaml"    # pointer to sibling Frictionless descriptor (required)
origin: "external|derived"
tier: "use-now|evaluate-next|track"
update_cadence: ""
accessions: []                     # external IDs (origin: external)
access:                            # current `access:` block, unchanged
  level: "public|registration|controlled|commercial|mixed"
  availability: "available|embargoed|withdrawn"
  ...
derivation:                        # current `derivation:` block (origin: derived)
  workflow_recipe: "recipe/Snakefile"     # relative path within this dataset dir
  recipe_lockfile: "recipe/lockfile.yaml"
  inputs: ["dataset:<upstream-slug>", ...]
parent_dataset: ""
siblings: []
consumed_by: []                    # backlinks (populated by promotion + register-run)
```

**Frictionless sidecar** (`datapackage.yaml` — pure Frictionless, no overlap with entity surface):

```yaml
# Standard Frictionless v2 Data Package; no science-* extensions.
name: <slug>                       # matches entity slug
profile: "data-package"
resources:
  - name: <resource-id>
    path: <logical relative path>  # NOT resolved to filesystem here — see §4
    hash: "sha256:..."             # REQUIRED from v1
    bytes: 123456789               # REQUIRED from v1
    schema: { ... }                # optional Frictionless table schema
    format: "parquet|csv|h5ad|..."
    mediatype: ""
```

**Why split**: the existing `DatapackageAdapter` already pairs profile-marked datapackages with entities; the existing `dataset.md` template comments explicitly say "entity surface does NOT carry resources[]" (`science/model/src/science_model/templates/dataset.md:13`). Preserving the split keeps backward compatibility with the adapter ecosystem and keeps `datapackage.yaml` round-trippable through standard Frictionless tooling.

Note: there is no `data_path:` field on the shared entity. Per-machine path overrides live exclusively in `~/.config/science/data.yaml` (§4.1 step 2) — a single mechanism, not two.

### 3.3 Paper mixin

```yaml
bibkey: ""
authors: []
year: 0
journal: ""
doi: ""
url: ""
datasets: []                       # [dataset:<slug>, ...]
key_findings: []                   # short string list (full text in body)
methods_summary: ""
limitations: []
model_or_tool_availability: ""     # if applicable
```

### 3.4 Topic mixin

Lift fields directly from the current `topic.md` template (scope, key concepts, methods, open questions, related papers) and declare them in JSON Schema.

### 3.5 Theme mixin

Lift fields directly from the current `theme.md` template (`theme_kind`, `theme_scope`, boundaries, guardrails, downstream-work, update-triggers). Note that `theme_scope` becomes meaningful at the shared tier — a shared theme's scope can be `cross-project`.

### 3.6 Domain extensions

Stack via the `+` syntax in `schema_profile:`. Example for a single-cell RNA-seq dataset:

```yaml
schema_profile: "science-entity-base/1.0+dataset/1.0+bio.scrna/1.0"
```

`bio.scrna` adds fields like `n_cells`, `n_genes`, `assay_protocol`, `species`, `tissue`, `preprocessing_version`. Bio extensions live in `~/d/science/schemas/extensions/bio/`. Other domains can be added without touching the base.

### 3.6.1 Naming and migration vs. existing fields

The new `schema_profile:` field is intentionally renamed to avoid collision with two existing fields that already use the word "profile":

- `Entity.profile: str` (`science/model/src/science_model/entities.py:214`) — singular, denotes knowledge-profile ownership (`"core"` etc.). Unchanged by this design.
- `profiles: ["science-pkg-entity-1.0"]` (current `dataset.md` template, Frictionless-style profile list in entity frontmatter) — also unchanged on existing project-side entities. Shared-store `datapackage.yaml` sidecars use Frictionless's native `profile: "data-package"` field, untouched.

`schema_profile:` is a new, additive field that names the JSON Schema composition. Migration for existing entities promoted to the shared store: `science promote` writes `schema_profile:` derived from the entity's `type` and any detected domain (e.g. an RNA-seq dataset becomes `science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0`). Existing `profiles: [...]` lists are preserved on the entity surface for backward compatibility with the current adapter ecosystem; they are NOT removed.

### 3.7 Validator implementation

**JSON Schema (Draft 2020-12)** via Python `jsonschema`. Profile strings parse to an ordered list of schema IDs; the validator composes them with `allOf` at runtime. Thin Pydantic wrapper layer for in-code ergonomic access (lazy, optional — `jsonschema` is the source of truth).

### 3.8 Field-level merge policy

Each schema field carries a `science:merge` annotation. The validator + overlay resolver use this to determine read-time composition.

```json
{
  "hypothesis_links": {
    "type": "array",
    "items": {"type": "string"},
    "science:merge": "project_only"
  },
  "tags": {
    "type": "array",
    "items": {"type": "string"},
    "science:merge": "append"
  },
  "hash": {
    "type": "string",
    "science:merge": "forbidden"
  },
  "title": {
    "type": "string",
    "science:merge": "replace"
  }
}
```

Merge modes:
- `replace` (default) — overlay value overrides shared value.
- `append` — overlay value concatenated with shared (deduplicated for arrays of primitives).
- `forbidden` — overlay must not set this field (validation error if it does).
- `project_only` — field exists only in overlays; shared schema does not allow it.

---

## 4. Bulk data resolution

### 4.1 Lookup order

For `(dataset-id, logical_path)`:

1. **Per-dataset directory** at `$SCIENCE_DATA_ROOT/<slug>/<logical_path>` — if present, verify hash, return absolute path. *(v1 primary path.)*
2. **Per-machine override** at `~/.config/science/data.yaml` — `<dataset-slug>: <absolute-path>` mapping for legacy data already laid out somewhere specific. (Useful for migration.)
3. **Recipe-driven regeneration** — run `~/d/science-shared/datasets/<slug>/recipe/Snakefile` (or marimo equivalent) with pinned commit and config; output into `$SCIENCE_DATA_ROOT/<slug>/`; verify hash; return path.
4. *(v2)* **Local CAS** at `$SCIENCE_DATA_ROOT/objects/<hash[0:2]>/<hash[2:]>` — content-addressed cache shared across datasets. Out of scope for v1.
5. *(v2)* **Remote object store** (S3-compatible, rsync target) — pluggable backend. Out of scope for v1.

### 4.2 Hash verification

Hash verification on every path-resolution call. Failure raises `DataIntegrityError`. Loud failure is the right default for reproducibility — silent fall-through to recipe regeneration would mask data corruption.

`hash:` algorithm is `sha256` by default; the field carries the algo prefix to allow future migration (`sha256:abc...`).

### 4.3 `$SCIENCE_DATA_ROOT` configuration

Resolution order:
1. Env var `$SCIENCE_DATA_ROOT`.
2. `data_root:` field in `~/.config/science/config.yaml`.
3. Default `/data/science-shared/` (matches the user's current `/data/` symlink habit).

### 4.4 Recipes for both origins

Every shared dataset has a `recipe/` directory, regardless of `origin:`:

- `origin: external` — recipe is the acquisition script (curl/aria2 against a stable URL, bioconductor download, dbGaP fetcher, etc.) plus any deterministic preprocessing that produces the hash-verified resources. The recipe ensures any machine can reconstruct the dataset from the upstream source.
- `origin: derived` — recipe is the workflow that consumes upstream `dataset:<slug>` inputs and produces this dataset's resources.

### 4.5 Recipe pinning

Each `~/d/science-shared/datasets/<slug>/recipe/` directory contains a `lockfile.yaml`:

```yaml
recipe_version: "1.0.0"
git_commit: "<sha>"               # commit of science-shared at time of run
config_hash: "sha256:..."         # hash of recipe/config.yaml
tools:
  - {name: snakemake, version: "8.10.0"}
  - {name: pyroe, version: "0.9.3"}
expected_outputs:
  - {name: cath_domains, hash: "sha256:..."}
```

Recipe re-runs must produce hashes matching `expected_outputs[].hash`, or promotion / regeneration fails with `RecipeMismatchError`.

---

## 5. Project overlays

### 5.1 Overlay file format

`<project>/doc/<type>/<slug>.md`:

```yaml
---
id: "paper:Adams2025"
overlay_of: "paper:Adams2025"        # explicit; same ID
pin_version: ""                       # optional; empty = always latest
relevance: "H2 — supports homology-split argument"
hypothesis_links: ["H2", "H4"]
task_links: ["t087"]
project_tags: ["high-priority"]
---

## Project-Specific Notes

<free text — appended to the canonical body at read time>
```

### 5.2 Identity & read-time resolution

**Overlays are not entities.** They share the canonical entity's `id` value for human/reference convenience, but they are loaded by `OverlayAdapter` into a separate `overlays` collection — they never enter the entity identity table (`canonical_id` map in `load_project_sources`). This avoids the `EntityIdentityCollisionError` raised at `science/src/science_tool/graph/sources.py:279`.

Resolution:

- `science show paper:Adams2025 --project protein-landscape`:
  1. Read canonical entity from `~/d/science-shared/papers/Adams2025.md` (via `SharedEntityAdapter`).
  2. If `--project` set: read overlay from `~/d/protein-landscape/doc/papers/Adams2025.md` (via `OverlayAdapter`, indexed by `(project, overlay_of)`).
  3. Validate both against their respective schemas (canonical against base+mixin; overlay against an overlay-specific schema permitting only `merge: project_only`, `merge: append`, and ID/version fields).
  4. Apply per-field merge per the schema annotations.
  5. Body sections: shared body verbatim, then overlay sections appended.
- Python API: `science.entity("paper:Adams2025", project="protein-landscape")` returns a Pydantic model with merge already applied.

No materialized merged file. Merge is a read-time operation.

### 5.3 Overlay schema constraint

A separate `overlay.schema.json` permits exactly:
- `id` (matching the canonical entity).
- `overlay_of` (required; same as `id`).
- `pin_version` (optional).
- `pin_effective_version` (optional; see §5.4).
- Fields whose mixin schema declares `science:merge: project_only` or `science:merge: append`.

Overlay validation fails fast if it sets a `merge: replace` or `merge: forbidden` field. This makes overlays cheap to read and impossible to drift far from canonical content.

### 5.4 Version pinning

`pin_version: "1.2.0"` makes the overlay pin to a specific entity version. If the shared entity has moved past the pin, `science health` and `science index rebuild` warn. There is no automatic bump — pin updates are explicit human decisions.

**For papers / topics / themes**, the entity is a single `.md` file; reading at the tagged commit gives the exact pinned content trivially.

**For datasets**, the pinned commit is read across the entire dataset directory: `entity.md`, `datapackage.yaml`, AND `recipe/lockfile.yaml`. Concretely, when an overlay sets `pin_version: "1.2.0"`, resolving `science show dataset:cath-domains --project foo` reads all three files from `git show dataset/cath-domains/1.2.0:datasets/cath-domains/entity.md` (and the sibling `datapackage.yaml` + `recipe/lockfile.yaml` from the same commit), so the surface metadata, the resource hashes (in `datapackage.yaml.resources[].hash`), and the recipe pin (in `lockfile.yaml`) all come from the same historical commit. The data resolver (§4) then verifies on-disk bytes against the *pinned* hashes, not current hashes.

A separate `pin_effective_version: "1.2.0+abc1234"` field is available as an escape hatch for the paranoid case where a user wants to additionally assert the exact short-hash component of `effective_version` (§7) even if `version:` didn't change. Rarely needed; mainly useful in cross-project published findings.

**Versioning discipline for shared datasets**: any change to `entity.md` OR `datapackage.yaml` requires bumping `version:` and re-tagging. This is the rule that makes pinning meaningful — without it, `datapackage.yaml` could drift within a version. Documented in §7.

### 5.5 Fork (escape hatch)

`science fork <type>:<slug> --into <project> [--as <new-slug>]` copies the canonical content into the project tree as a project-local entity (no `overlay_of:`, new slug, `forked_from:` field recording origin + version). Used when a project needs to diverge from the canonical entity. Rare by design.

---

## 6. Discovery, CLI, and inventory integration

### 6.1 Registry

`~/d/science-shared/registry.sqlite` is a regenerable index built by walking the store and parsing entity frontmatter. Filesystem is the source of truth; the cache auto-rebuilds when any source file is newer.

### 6.2 inventory contract: v2

`inventory_v1` (`science_model.contracts.inventory_v1.InventoryPayload`) uses `extra="forbid"` and pins `schema_version: Literal["1"]`, so adding fields would break existing strict consumers. Therefore:

- **Introduce `inventory_v2`** as a sibling module (`science_model.contracts.inventory_v2`). Producers emit v2 once available; consumers must opt in.
- **Reuse the existing `scope` field**: shared entities appear in the same `entities:` list, distinguished by `scope: "cross-project"` (which is already a permitted value on `InventoryEntity`, `science/model/src/science_model/contracts/inventory_v1.py:82`). No new entity model needed for them.
- **Add a top-level `overlays: list[InventoryOverlay]`** in v2. Each overlay carries `(overlay_of_id, project_id, pin_version, pin_effective_version, project_only_fields, append_fields, body_sections)` — a minimal projection sufficient for the dashboard to render the merged view without re-reading project files. Both `pin_version` and `pin_effective_version` are optional (see §5.4). Overlays are NOT entities (see §5.2).
- v1 stays alive for the duration of the inventory-consumer migration; the inventory builder can emit either contract via a `--schema-version` flag. Drop v1 after dashboard + downstream consumers are on v2.

The v2 contract module exports `SCHEMA_VERSION = "2"` and otherwise mirrors v1's structure + content-hash machinery.

### 6.3 Core commands

```
science index rebuild
science find dataset --tag scrna --ontology UBERON:0000178
science find paper --topic single-cell-foundation-models --year 2024..
science show <type>:<slug> [--project <name>] [--json]
science promote <type>:<slug> --from <project> [--apply]
science promote --type <type> [--filter <glob>] [--apply]
science fork <type>:<slug> --into <project> [--as <new-slug>]
science data resolve <type>:<slug>/<resource>
science data fetch <type>:<slug>
science validate [--type <t>] [--slug <s>]
```

All `promote` operations default to dry-run; `--apply` executes. All file mutations are recorded in `~/d/science-shared/.migrations/`.

### 6.4 Dashboard pivot

The dashboard (`~/d/dashboard/`) currently scans projects directly. Once the 2026-05-12 inventory plan lands AND this spec is implemented, the dashboard migrates from `inventory_v1` to `inventory_v2` and gains cross-project / shared-entity views without bespoke code. Dashboard integration is a follow-on slice; not in this design's implementation scope, but the registry and contract shape are chosen to make it straightforward.

---

## 7. Versioning & reproducibility

Three independent version axes, all required for shared datasets:

- **Entity version** — semver in `entity.md` frontmatter (`version: 1.2.0`). For shared datasets, **`version:` bumps on ANY change to either `entity.md` OR `datapackage.yaml`** (resource hashes change → version bumps). This is the discipline that makes `pin_version:` meaningful at the dataset granularity. For papers / topics / themes, `version:` bumps on any meaningful content change to the single `.md` file.
- **Resource hashes** — required from v1 in `datapackage.yaml` `resources[].hash`. Computed automatically on `science promote` and `science data fetch` post-recipe. Hash changes always co-occur with a `version:` bump per the rule above.
- **Git history of `~/d/science-shared/`** — `~/d/science-shared/` is its own git repo. Every entity change is a commit; every `version:` bump is tagged `<type>/<slug>/<semver>` (e.g. `paper/Adams2025/1.2.0`). Each tagged commit captures the entire dataset directory atomically — entity surface, descriptor, and recipe lockfile.

**Pin resolution**: an overlay's `pin_version: "1.2.0"` resolves by checking out the tagged commit `paper/Adams2025/1.2.0` from `~/d/science-shared/`'s history (or via `git show <tag>:papers/Adams2025.md` for in-process reads — no working-tree checkout needed). Without the git repo, pinning would only warn; with it, pinning resolves to the actual historical metadata.

**Recipe `git_commit:`** in `lockfile.yaml` (§4.5) refers to a commit in the `~/d/science-shared/` git repo — it's now a meaningful reproducibility anchor.

**Effective version** for downstream pinning: `<entity.version>+<short_hash(sorted(resource.hash))>`. Exposed as `dataset.effective_version` in the Python API.

**Reproducibility teeth**: hash mismatch on resolution → `DataIntegrityError`. Recipe re-run with mismatched output hash → `RecipeMismatchError`. Both are loud failures — there is no silent fall-through.

---

## 8. Migration tooling

### 8.1 `science promote` shape

Per-entity, opt-in, dry-run by default, reversible via audit log.

```
science promote <type>:<slug> --from <project>       # single entity
science promote --type <type> [--filter <glob>]      # discover + dedup across projects
```

### 8.2 Single-entity workflow

1. Read canonical-candidate file from `<project>/doc/<type>/<slug>.md`.
2. For datasets only: locate data via current symlink chain or descriptor; compute resource hashes; build `datapackage.yaml` with hashes + `bytes`.
3. Write the canonical location:
   - Datasets: `~/d/science-shared/datasets/<slug>/entity.md` (surface) + `datapackage.yaml` (Frictionless, with hashes) + `recipe/`.
   - Papers / topics / themes: `~/d/science-shared/<type>/<slug>.md` (single file).
   Content = canonical fields only; project-specific (`merge: project_only`) fields stripped from the surface and preserved in the overlay (step 4). Commit the new files to `~/d/science-shared/` and tag `<type>/<slug>/<entity.version>`.
4. Rewrite project file as minimal overlay: `id`, `overlay_of`, `pin_version`, plus stripped-out project-specific fields and project-specific body sections.
5. Validate both new shared entity and overlay against schemas. Run `science health` to confirm cross-references from hypotheses / questions / tasks still resolve.
6. Append entry to `~/d/science-shared/.migrations/<YYYY-MM-DD-HHMM>-<op-id>.yaml`: before/after paths, hashes, diff.

### 8.3 Dedup workflow (papers / topics across projects)

1. Scan all registered projects for files matching `<type>:<slug>`.
2. If one instance — straightforward promote.
3. If multiple — present an N-way diff in the terminal. Prompt user for:
   - Which instance becomes canonical (or "merge fields from A, B, C with my-pick").
   - Project-specific overlay fields are split per-project automatically.

### 8.4 Data migration policy for datasets

The default migration **does not move bulk data files**. It moves metadata and uses the per-machine override (§4.1 step 2) to map the dataset to its existing on-disk location.

- Descriptor moves: `<project>/data/processed/<slug>/datapackage.json` → `~/d/science-shared/datasets/<slug>/datapackage.yaml`. Hashes computed in place against the existing data files.
- Acquisition / preprocessing scripts (if discoverable) move into `~/d/science-shared/datasets/<slug>/recipe/`. If absent, the migration tool stubs a `recipe/README.md` documenting that the recipe needs back-filling and marks the entity `tier: track` until it's added.
- Per-machine override entry written to `~/.config/science/data.yaml`: `<slug>: <current absolute path>`. No data movement.
- Project's `<project>/data/processed/<slug>/` symlink is removed; references resolve through the data resolver via the overlay's `id`.
- Optional `--relocate` flag moves data to `$SCIENCE_DATA_ROOT/<slug>/` and drops the per-machine override entry. Useful when the user is also tidying their `/data/` layout.
- Promotion fails if any resource is unreadable or — on re-promotion — hash recomputation differs from a pre-existing `hash:` value (suggests data drift).

### 8.5 Phased rollout

1. **Papers first** — no bulk data, often duplicated, dedup gives immediate value, exercises the dedup flow end-to-end.
2. **Topics + themes** — same shape as papers, fewer instances.
3. **Datasets** — last; touches bulk data + recipes + symlinks. Per-dataset, manually verified.

---

## 9. Implementation phases

Each phase is a separate implementation plan / PR series.

**Status as of 2026-05-21:** Phases A-H have landed in `~/d/science`. Phase I is the active downstream focus.

- **A. Schema layer — landed.** JSON Schema files + Python validator + base test fixtures + profile-string parser.
- **B. Shared store scaffolding — landed.** Directory creation, `registry.sqlite` builder, `science commons index rebuild`, `science commons show`, `science commons find`, `science commons validate`, and CLI wiring.
- **C. Data resolver — landed.** `$SCIENCE_DATA_ROOT` configuration, hash verification, and `science commons data resolve` / `fetch` v1 behavior.
- **D. Overlay merge layer + inventory_v2 — landed.** Read-time merge per schema annotations, project-aware commons show, Python API surface, standalone commons inventory, and project `overlays[]` export.
- **E. Migration: papers — landed.** `science commons promote paper` dedup and migration flow with pilot docs.
- **F. Migration: topics, themes — landed.** Topic/theme promote flow with pilot docs.
- **G. Migration: datasets — landed.** Dataset promote flow, descriptor relocation, resource validation, and pilot docs.
- **H. Bio extensions — landed.** `bio.matrix`, `bio.table`, `bio.rnaseq`, `bio.scrna`, and `bio.cna` mixins plus `science commons promote dataset --mixin`.
- **Graph integration — landed as a follow-on.** `science graph build` loads referenced commons entities and overlays into project graphs.
- **I. Dashboard pivot — next.** Dashboard has already started consuming `inventory_v2` and commons overlays in `~/d/dashboard`; remaining work is completion, verification, and rollout hardening.

---

## 10. Non-goals (v1)

- Content-addressed object store (`$SCIENCE_DATA_ROOT/objects/` CAS layout) — deferred to v2.
- Pluggable remote backends (S3, rsync, etc.) — deferred to v2.
- Public / multi-user sharing infrastructure (git remote on `~/d/science-shared/`, public registry) — supported by the shape, not built now.
- Full workflow / workflow-run entity promotion — workflows stay project-local. Recipes travel inside dataset directories only.
- Migrating hypotheses / questions / findings / interpretations to shared — they remain project-local by design (they encode project-specific reasoning).
- Replacing the dashboard — pivot is a follow-on, sequenced after this spec lands.

---

## 11. Open questions

These are deliberately deferred — they can be resolved during implementation without changing the design's load-bearing decisions.

- **Concurrency safety on `registry.sqlite`.** Two processes rebuilding the cache simultaneously. Likely solved with a file lock; details at implementation time.
- **How `overlay_of:` interacts with `forked_from:`.** A forked entity is no longer an overlay; can a fork later become an overlay again? Default answer: no, that's a re-fork in the other direction (`science promote --from <project>` of the fork). Confirm with concrete cases during phase E.
- **Schema versioning across base + mixins.** What happens when `base/2.0` arrives — do `mixin/1.0` definitions auto-upgrade or pin to `base/1.0`? Each profile-string component versions independently; what's open is the validator's handling of unknown combinations. Revisit in phase A.
- **Pin-version resolution under git history rewrites.** `pin_version` resolves via git tag in `~/d/science-shared/`. If history is force-pushed or tags are moved (rare but possible), pins become stale silently. Mitigation: validator records the commit SHA alongside the tag at pin time, warns if they diverge. Confirm at phase D.
- **Recipe execution sandboxing.** `science data fetch` runs arbitrary Snakemake from `recipe/`. For multi-user / public-sharing futures, recipe execution needs sandboxing. Out of scope for single-user v1.
- **Migration of project entities that don't fit any current mixin.** Some project-side records (`finding`, `interpretation`, `bias-audit`) have rich per-project structure. They stay project-local in v1; whether any deserve future shared-tier promotion is a v2 question.
