# C2 Gene Crosswalk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Pillar C sub-phase **C2 — gene identity**: a pinned HGNC gene crosswalk as a reference collection keyed by an opaque composite `gene_key`, a pure provenance-carrying resolver (`to_canonical`), and `science validate` check 2 (gene namespace + declared-registry resolvability, declaration-level only) — flipping `identity_context.molecular_ids.gene` from `declared_unresolved` (C1) to resolved.

**Architecture:** Three layers, mirroring C1. (1) **science-model**: a minimal `bio.gene_crosswalk/1.0` collection extension (`member_key_column: gene_key`), plus an additive extension of the existing `bio.identity_context/1.0` so a `molecular_ids.<tier>` declaration may name its `registry` and `resolution_status`. (2) **commons data**: the `dataset:gene-crosswalk-hgnc` reference collection (entity + datapackage) and a no-network-at-resolve recipe that fetches the pinned dated HGNC complete-set + withdrawn release files and builds `crosswalk.csv`. (3) **science-tool**: pure HGNC parsing helpers, a pure resolver over the crosswalk rows (`to_canonical` returning a discriminated `ResolvedGeneMatch | AmbiguousGeneMatch | None`), and check 2 appended to the existing `validate/checks/identity_context.py`. Implements C-D1 (species-aware `{taxon, namespace, id}` gene identity, HGNC anchor) and §5 check 2 of `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md`; the crosswalk is the **third instance** of the foundation primitive (`docs/plans/2026-05-26-reference-collection-member-promotion-design.md`), after gene-sets (D) and the assembly registry (C1).

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, `pytest`, `uv` (`uv run --frozen`), the `science-model` and `science` (`science_tool`) packages, `httpx` (already a science-tool dep, build-time fetch only), `pyyaml` (recipe). No new pinned dependency (HGNC files are plain TSV; parsing is stdlib `csv`). All repo paths are relative to `~/d/science`; the commons lives at `~/d/science-commons`.

---

## Background the implementer must read first

- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C. **C-D1** (gene canonical = species-aware `{taxon, namespace, id}`, human anchor HGNC id; accepted inputs HGNC symbol / Entrez / Ensembl gene; Entrez is **not** canonical). **C-D3** (gene crosswalk = HGNC complete set, a commons `reference` dataset with a recipe + hash-verified artifact; dated/immutable handles, `latest` discovery-only). **§5 check 2** (declared keys resolve against the pinned crosswalk for their declared namespace; deprecated/merged/withdrawn ids mapped-through-with-provenance, never dropped/guessed — check 4). **§8** locks C2 = gene crosswalk + resolver + checks 2 & 4.
- `docs/plans/2026-05-26-reference-collection-member-promotion-design.md` — the primitive. RCM-D1 (collection = a `dataset` with a mechanism-specific key column), RCM-D2 (resolve-or-`declared_unresolved`), RCM-D6 (**exact key equality is identity; a crosswalk many-to-one or a deprecated/merged/withdrawn map relates two *distinct* canonical ids with provenance — never a key collapse**). The gene crosswalk is the **third instance**; its `member_of` promotion (a gene promoted to its own `dataset`) is inherited but **unused in C2 v1** (no evidence-bearing gene yet).
- `docs/plans/2026-05-26-c1-assembly-identity-plan.md` — **C1 (the sibling this plan mirrors)**, already merged. It shipped `bio.identity_context/1.0`, `bio.assembly_registry/1.0`, `commons/assembly.py` (the resolver template), `commons/assembly_registry_build.py` (the build-helper template), and `validate/checks/identity_context.py` (the check module this plan **extends**). Read `science/src/science_tool/commons/assembly.py` and `science/src/science_tool/validate/checks/identity_context.py` before writing — C2's resolver and check follow their exact shape and idioms.

### Brainstorm decisions locked for this plan (do not relitigate)

1. **v1 source = HGNC "complete set" + "withdrawn" only.** The complete set already carries `symbol`, `entrez_id`, `ensembl_gene_id`, `alias_symbol`, `prev_symbol`, `status`; the withdrawn file carries merged/split forward pointers. One authority (HGNC), two release files, human-only data. NCBI/Ensembl/BioMart joins are a later increment. (HGNC's archive confirms dated monthly/quarterly complete-set + withdrawn files and the `MERGED_INTO_REPORT(S)` replacement format: https://www.genenames.org/download/archive/)
2. **Namespaces are split and explicit (no `hgnc` overload).** `to_canonical` accepts `namespace ∈ {hgnc_id, hgnc_symbol, entrez, ensembl}`. HGNC stable ids and HGNC symbols are distinct input spaces. The species-aware API carries `taxon` + `namespace` on every call — never a bare gene id (C-D1, §7 d6).
3. **Member key = an opaque composite `"<taxon>|hgnc|<hgnc_id>"`** (e.g. `9606|hgnc|HGNC:5`), constructed only by `make_gene_key`. The `|` field delimiter never collides with the `HGNC:` CURIE inside the id field; the key is **opaque** — byte-equality is identity (RCM-D6) and **nothing downstream splits it** (the resolver gates on a `taxon` parameter / `_HUMAN_TAXON`, never by parsing the key; multi-species will add an explicit `taxon` *column*, not derive it from the key). Multi-value columns in `crosswalk.csv` (`alias_symbol`, `prev_symbol`, `replacement_gene_keys`) use **`;`** within a cell, *not* `|`, because `replacement_gene_keys` holds whole `gene_key`s that themselves contain `|`.
4. **`to_canonical` returns a discriminated result**: `ResolvedGeneMatch | AmbiguousGeneMatch | None`. `ResolvedGeneMatch` carries lifecycle `status` (`approved|withdrawn|merged|split`) and an optional `replacement_gene_key` (the resolver **surfaces, never auto-follows** a merge). `AmbiguousGeneMatch` carries `candidates` (≥2) and **has no `gene_key`** — a caller cannot misuse an unresolved identity (a shared symbol/id, or a split entry's forward targets). `None` = genuinely not found.
5. **Check 2 is declaration-level only** (a fast static gate; no data-payload reading). It validates that the declared gene `namespace` is crosswalk-supported and that the declared `registry` resolves to a `bio.gene_crosswalk/1.0` collection with `member_key_column: gene_key`. A loaded registry of the **wrong type → ERROR** (a wrong registry must not quietly pass); an unloadable/unknown registry → INFO (cannot verify), mirroring C1's `identity.registry-unavailable`. Payload-level id-column resolution + unresolved counts live in the resolver library / downstream ingestion tests, **not** in `science validate` (this is where check 4's "map-through-with-provenance" is realized — as the resolver contract, not a validate check).

### Two grounding facts (verified against the codebase; carried from C1)

1. **The graph `Entity` is a closed pydantic model** that drops extension fields, so the check reads **raw frontmatter**. The check module `identity_context.py` already gathers it via **tolerant `DatapackageAdapter().discover(ctx.project_root)`** in `_dataset_frontmatters` (NOT `load_project_sources`, which strict-validates and can crash the run). Check 2 **reuses** `_dataset_frontmatters`, `_raw_frontmatter`, and the `_result` helper already in that module.
2. **Profile composition is `allOf` over profile-string components; there is no cross-file `$ref`.** `_filename_for` is `name.replace(".", "-")`, so `bio.gene_crosswalk` → `extension-bio-gene_crosswalk-1.0.json` (underscore preserved). The `science-entity-base` `schema_profile` pattern was already widened in C1 to permit `_` in component names — **no base-schema change is needed** for `gene_crosswalk`.

### Codebase anchors (read before writing code)

- Schemas dir: `science/model/src/science_model/schemas/` — `extension-bio-assembly_registry-1.0.json` is the minimal-collection template; `extension-bio-identity_context-1.0.json` is the file Task 2 edits. Model test template: `science/model/tests/test_bio_extension_assembly_registry.py`.
- Data resolver: `science/src/science_tool/commons/resolver.py::resolve(dataset_id, logical_path, *, commons_root=None, data_root=None) -> ResolvedDataResource` (sha256-verified `.path`; data lives at `<data_root>/<slug>/<logical_path>`; slug derives from the `dataset:<slug>` id). Errors subclass `CommonsError` in `commons/errors.py`.
- Resolver template: `science/src/science_tool/commons/assembly.py` (`AssemblyEntry`, `_parse_registry_rows` with blank/dup/missing-column guards, `load_*`, `available_*_keys`, `resolve_*`). Build template: `science/src/science_tool/commons/assembly_registry_build.py`.
- Check module to EXTEND: `science/src/science_tool/validate/checks/identity_context.py` — `@Check(section=, order=)`, `Result(severity, path, line, message, rule, task)` via the local `_result`, `Severity{ERROR,WARN,INFO}`, `_dataset_frontmatters(ctx)`, `_raw_frontmatter(path)`. `identity_context` is **already registered** in `_load_canonical_checks()` (no `__init__.py` change needed). Commons entity loading: `CommonsEntityAdapter(root).load(dataset_id)` → record with `.body_path`, `.slug`; `resolve_commons_root()` in `commons/config.py`.
- In-use check `order=` values: 0–14, 16–30 (15 is the only gap). Duplicate orders are an established pattern (`evidence_lines` shares 24/25/26 with other modules). `test_checks_basic.py` asserts only the first 6 checks, so **order=27 for the gene check is safe and needs no inventory update**. C1 took 25 & 26 in this same module.
- Commons exemplar: `~/d/science-commons/datasets/assembly-registry/` (entity + datapackage + `recipe/`), created by C1 — copy its structure.

### Task dependency order

Tasks are numbered in dependency order; execute (or dispatch) them in order:
- **1, 2** (the two schemas) are independent.
- **3** (commons dataset + fixture) needs Task 1's schema (the entity validates against `bio.gene_crosswalk`).
- **4** (resolver) needs Task 3's fixture (its tests read the fixture `crosswalk.csv`).
- **5** (build helpers) needs Task 4's resolver module (it imports `make_gene_key`).
- **6** (check 2) needs Task 2 (the declaration fields) and Task 4 (the resolver constants).
- **7** (migration + verification) is last.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `science/model/src/science_model/schemas/extension-bio-gene_crosswalk-1.0.json` | Create | Minimal collection extension: `member_key_column: gene_key`, optional `gene_count`. |
| `science/model/tests/test_bio_extension_gene_crosswalk.py` | Create | Schema tests for `bio.gene_crosswalk`. |
| `science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json` | Modify | Add optional `registry` + `resolution_status` to each `molecular_ids.<tier>`. |
| `science/model/tests/test_bio_extension_identity_context.py` | Modify | Add tests for the new `molecular_ids.gene.registry`/`resolution_status` fields. |
| `~/d/science-commons/datasets/gene-crosswalk-hgnc/entity.md` | Create | The reference-collection dataset entity (unbuilt: `gene_count: 0`). |
| `~/d/science-commons/datasets/gene-crosswalk-hgnc/datapackage.yaml` | Create | The `crosswalk.csv` resource + sha256 (placeholder until built). |
| `~/d/science-commons/datasets/gene-crosswalk-hgnc/recipe/{build.py,sources.yaml,README.md}` | Create | Operator-run recipe: fetch pinned HGNC files, build `crosswalk.csv`. |
| `science/tests/fixtures/commons/gene-crosswalk/datasets/gene-crosswalk-hgnc/{entity.md,datapackage.yaml}` | Create | Hermetic fixture entity store (4-row crosswalk). |
| `science/tests/fixtures/commons/gene-crosswalk-data/gene-crosswalk-hgnc/crosswalk.csv` | Create | Hermetic fixture data file + sha256. |
| `science/src/science_tool/commons/gene_crosswalk.py` | Create | Pure resolver: `CrosswalkRow`, `ResolvedGeneMatch`, `AmbiguousGeneMatch`, `load_gene_crosswalk`, `available_gene_keys`, `to_canonical`, `make_gene_key`; constants. |
| `science/tests/test_commons_gene_crosswalk.py` | Create | Resolver tests against a hermetic fixture crosswalk. |
| `science/src/science_tool/commons/gene_crosswalk_build.py` | Create | Pure HGNC parsing (`parse_complete_set`, `parse_withdrawn`, `build_rows`) + build-time `fetch_text`. |
| `science/tests/test_gene_crosswalk_build.py` | Create | Parsing tests (in-memory TSV; merged/split/withdrawn; `|`→`;` recode; round-trip). |
| `science/src/science_tool/validate/checks/identity_context.py` | Modify | Append check 2 (`order=27`): `evaluate_gene_identity` + `check_gene_identity` + helpers. |
| `science/tests/validate/test_checks_identity_context.py` | Modify | Add tests for the pure `evaluate_gene_identity` evaluator. |
| `docs/migration/2026-05-27-gene-crosswalk-identity.md` | Create | How to declare gene identity; `molecular_ids.gene` flips to resolved. |

---

## Task 1: `bio.gene_crosswalk/1.0` collection extension schema

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-gene_crosswalk-1.0.json`
- Test: `science/model/tests/test_bio_extension_gene_crosswalk.py`

The gene crosswalk is the collection dataset (third primitive instance). Its only extension-specific facts: the member-key column is `gene_key` (a `const`, machine-checkable that this collection is gene_key-keyed) and an optional `gene_count`. Mirrors `bio.assembly_registry`.

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_bio_extension_gene_crosswalk.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_crosswalk_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
        "id": "dataset:gene-crosswalk-hgnc",
        "type": "dataset",
        "title": "HGNC gene crosswalk (gene_key-keyed reference collection)",
        "version": "1.0.0",
        "created": "2026-05-27",
        "updated": "2026-05-27",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "member_key_column": "gene_key",
        "gene_count": 4,
    }


def test_loader_resolves_gene_crosswalk_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.gene_crosswalk", version="1.0"))
    assert schema["$id"].endswith("extension-bio-gene_crosswalk-1.0.json")


def test_minimal_valid_crosswalk_passes(base_crosswalk_entity: dict) -> None:
    EntityValidator().validate(base_crosswalk_entity)


def test_member_key_column_required(base_crosswalk_entity: dict) -> None:
    del base_crosswalk_entity["member_key_column"]
    with pytest.raises(EntityValidationError, match="member_key_column"):
        EntityValidator().validate(base_crosswalk_entity)


def test_member_key_column_must_be_gene_key(base_crosswalk_entity: dict) -> None:
    base_crosswalk_entity["member_key_column"] = "hgnc_id"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_crosswalk_entity)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_gene_crosswalk.py -v`
Expected: FAIL (schema file missing).

- [ ] **Step 3: Create the schema**

Create `science/model/src/science_model/schemas/extension-bio-gene_crosswalk-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-gene_crosswalk-1.0.json",
  "title": "science entity bio.gene_crosswalk extension",
  "type": "object",
  "required": ["member_key_column"],
  "properties": {
    "member_key_column": {"const": "gene_key"},
    "gene_count": {"type": "integer", "minimum": 0}
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_gene_crosswalk.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/schemas/extension-bio-gene_crosswalk-1.0.json science/model/tests/test_bio_extension_gene_crosswalk.py
git commit -m "feat(bio): bio.gene_crosswalk/1.0 collection extension (gene_key-keyed)"
```

---

## Task 2: Extend `bio.identity_context` — registry & resolution_status on `molecular_ids`

**Files:**
- Modify: `science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json`
- Test: `science/model/tests/test_bio_extension_identity_context.py`

C1 left a `molecular_ids.<tier>` entry as `{namespace, canonical}`. Check 2 needs each tier to optionally name the `registry` it resolves against and a `resolution_status` (so a gene tier can declare `declared_unresolved`, or assert `resolved`). Both additions are **additive and backward-compatible** (existing declarations without these keys stay valid).

- [ ] **Step 1: Add the failing tests**

Append to `science/model/tests/test_bio_extension_identity_context.py`:

```python
def test_molecular_ids_gene_accepts_registry_and_resolution_status(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "canonical": True,
        "registry": "dataset:gene-crosswalk-hgnc",
        "resolution_status": "resolved",
    }
    EntityValidator().validate(base_idc_entity)


def test_molecular_ids_gene_registry_must_be_dataset_ref(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "registry": "gene-crosswalk-hgnc",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_molecular_ids_gene_rejects_unknown_resolution_status(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "resolution_status": "maybe",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_molecular_ids_gene_declared_unresolved_passes(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["molecular_ids"]["gene"] = {
        "namespace": "hgnc_id",
        "resolution_status": "declared_unresolved",
    }
    EntityValidator().validate(base_idc_entity)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_identity_context.py -k "registry or resolution_status or declared_unresolved" -v`
Expected: `test_molecular_ids_gene_registry_must_be_dataset_ref` and `..._rejects_unknown_resolution_status` FAIL (the fields are currently unconstrained `additionalProperties`, so an invalid value is wrongly accepted). The two "accepts/passes" tests already pass (extra keys are currently allowed) — they guard against a future regression once the fields are explicit.

- [ ] **Step 3: Edit the schema**

In `science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json`, add `registry` and `resolution_status` to the `molecular_ids.additionalProperties` tier sub-schema. The file becomes:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-identity_context-1.0.json",
  "title": "science entity bio.identity_context extension",
  "type": "object",
  "required": ["identity_context"],
  "properties": {
    "identity_context": {
      "type": "object",
      "additionalProperties": true,
      "required": ["taxon"],
      "properties": {
        "taxon": {"type": "integer", "minimum": 1},
        "molecular_ids": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "required": ["namespace"],
            "properties": {
              "namespace": {"type": "string", "minLength": 1},
              "canonical": {"type": "boolean"},
              "registry": {"type": "string", "pattern": "^dataset:"},
              "resolution_status": {"enum": ["resolved", "declared_unresolved"]}
            }
          }
        },
        "assembly": {"$ref": "#/$defs/assembly_identity"}
      }
    }
  },
  "$defs": {
    "assembly_identity": {
      "type": "object",
      "additionalProperties": false,
      "required": ["seqcol_digest", "registry", "resolution_status"],
      "properties": {
        "seqcol_digest": {"type": "string", "minLength": 1},
        "label": {"type": "string", "minLength": 1},
        "registry": {"type": "string", "pattern": "^dataset:"},
        "resolution_status": {"enum": ["resolved", "declared_unresolved"]}
      }
    }
  }
}
```

The tier still leaves `additionalProperties` at its default (open) so a tier may carry forward-compatible extra keys; only `registry` and `resolution_status` gain validation. `namespace` stays required; nothing else about C1 changes.

- [ ] **Step 4: Run the identity_context schema tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_identity_context.py -v`
Expected: all PASS (the C1 tests + the four new ones).

- [ ] **Step 5: Run the full model suite (no regression)**

Run: `cd ~/d/science/science/model && uv run --frozen pytest -q`
Expected: PASS (additive change).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json science/model/tests/test_bio_extension_identity_context.py
git commit -m "feat(bio): identity_context molecular_ids tiers carry registry + resolution_status (C2)"
```

---

## Task 3: Gene crosswalk commons dataset + recipe + hermetic fixture

**Files:**
- Create: `~/d/science-commons/datasets/gene-crosswalk-hgnc/{entity.md,datapackage.yaml,recipe/build.py,recipe/sources.yaml,recipe/README.md}`
- Create: `science/tests/fixtures/commons/gene-crosswalk/datasets/gene-crosswalk-hgnc/{entity.md,datapackage.yaml}`
- Create: `science/tests/fixtures/commons/gene-crosswalk-data/gene-crosswalk-hgnc/crosswalk.csv`

Creates (a) the real commons reference-collection dataset + its operator-run recipe (committed **unbuilt** — placeholder hash, `gene_count: 0`, no `crosswalk.csv` — exactly like C1's assembly-registry), and (b) a **hermetic 4-row fixture** (no network) used by Task 4 (resolver) and Task 6 (check). The acceptance gate is the hermetic fixture + green tests, not the populated real rows. The recipe's `build.py` imports the build helpers created in **Task 5**; the unbuilt dataset committed here does not run it, so this task does not depend on Task 5.

- [ ] **Step 1: Create the real commons dataset entity**

`~/d/science-commons/datasets/gene-crosswalk-hgnc/entity.md`:

```markdown
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0
id: dataset:gene-crosswalk-hgnc
type: dataset
title: "HGNC gene crosswalk — gene_key-keyed reference collection (human)"
version: "1.0.0"
created: "2026-05-27"
updated: "2026-05-27"
tags: []
access:
  level: public
  availability: available
  verified: true
  verification_method: retrieved
  source_url: https://www.genenames.org/download/archive/
datapackage: datapackage.yaml
origin: external
status: active
tier: use-now
update_cadence: quarterly
member_key_column: gene_key
gene_count: 0
---

# HGNC gene crosswalk

A reference collection (foundation primitive, third instance) whose member rows
are addressed by an opaque composite `gene_key` `"<taxon>|hgnc|<hgnc_id>"`
(e.g. `9606|hgnc|HGNC:5`). Built from pinned, dated HGNC complete-set + withdrawn
release files; see `recipe/`. The HGNC id is the canonical human gene anchor
(C-D1); symbol / Entrez / Ensembl are accepted inputs resolved *to* it. Deprecated
/ merged / split entries are retained with forward pointers (`replacement_gene_keys`).
Individual genes are promoted to their own `dataset` (`derivation.kind: member_of`,
`member_key` = the `gene_key`) only on demand.
```

(Set `gene_count` to the real row count after the recipe runs.)

- [ ] **Step 2: Create the datapackage (hash filled when built)**

`~/d/science-commons/datasets/gene-crosswalk-hgnc/datapackage.yaml`:

```yaml
name: gene-crosswalk-hgnc
profile: data-package
title: "HGNC gene crosswalk — gene_key -> symbol/entrez/ensembl + lifecycle"
version: "1.0.0"
licenses:
  - name: CC0-1.0
    path: https://creativecommons.org/publicdomain/zero/1.0/
    title: Creative Commons Zero v1.0 Universal
provenance:
  - action: build
    tool: recipe/build.py
resources:
  - name: crosswalk
    path: crosswalk.csv
    format: csv
    mediatype: text/csv
    description: "One row per HGNC entry: gene_key (member key), symbol, entrez_id, ensembl_gene_id, alias_symbol, prev_symbol, status, replacement_gene_keys."
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 0
```

- [ ] **Step 3: Create the pinned recipe inputs**

`~/d/science-commons/datasets/gene-crosswalk-hgnc/recipe/sources.yaml`:

```yaml
# Pinned, dated HGNC release files (immutable; the 'latest'/'current' alias is
# discovery-only, C-D3). Discover the current dated quarterly handle from
# https://www.genenames.org/download/archive/ and pin it here before building.
# build.py verifies nothing about the URL beyond a successful fetch; the
# datapackage sha256 (Step 6) is the integrity gate on the built artifact.
complete_set_url: "https://storage.googleapis.com/public-download-files/hgnc/archive/archive/quarterly/tsv/hgnc_complete_set_2025-04-01.txt"
withdrawn_url: "https://storage.googleapis.com/public-download-files/hgnc/archive/archive/quarterly/tsv/withdrawn_2025-04-01.txt"
```

- [ ] **Step 4: Create the recipe runner**

`~/d/science-commons/datasets/gene-crosswalk-hgnc/recipe/build.py`:

```python
"""Operator-run build of the HGNC gene crosswalk's crosswalk.csv.

Run from the dataset directory:  uv run --with httpx --with pyyaml python recipe/build.py
Network fetches the pinned dated HGNC release files; output is a few-MB CSV.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from science_tool.commons.gene_crosswalk_build import build_rows, fetch_text

_HERE = Path(__file__).resolve().parent
_OUT = _HERE.parent / "crosswalk.csv"
_FIELDS = [
    "gene_key",
    "symbol",
    "entrez_id",
    "ensembl_gene_id",
    "alias_symbol",
    "prev_symbol",
    "status",
    "replacement_gene_keys",
]


def main() -> None:
    src = yaml.safe_load((_HERE / "sources.yaml").read_text(encoding="utf-8"))
    complete = fetch_text(src["complete_set_url"])
    withdrawn = fetch_text(src["withdrawn_url"])
    rows = build_rows(complete_set_text=complete, withdrawn_text=withdrawn)
    with _OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {_OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Write the recipe README**

`~/d/science-commons/datasets/gene-crosswalk-hgnc/recipe/README.md`:

```markdown
# HGNC gene crosswalk build

1. Pin the current dated quarterly handles in `sources.yaml`. Discover them at
   https://www.genenames.org/download/archive/ (the `quarterly/tsv/` directory).
   Use a dated file (`hgnc_complete_set_<date>.txt`, `withdrawn_<date>.txt`),
   never the `latest`/`current` alias (C-D3).
2. Build: `uv run --with httpx --with pyyaml python recipe/build.py` (writes `../crosswalk.csv`).
3. Pin the artifact hash + size into `datapackage.yaml`:
   `python - <<'PY'\nimport hashlib,os;p="crosswalk.csv";print("sha256:"+hashlib.sha256(open(p,'rb').read()).hexdigest(),os.path.getsize(p))\nPY`
4. Update `entity.md` `gene_count` to the row count.

The member key is an opaque composite `"<taxon>|hgnc|<hgnc_id>"`. Within-cell
multi-values use `;` (never `|`, which is the gene_key field delimiter).
```

- [ ] **Step 6: (Operator step — network) Populate the real crosswalk**

If network is available:

```bash
cd ~/d/science-commons/datasets/gene-crosswalk-hgnc
uv run --with httpx --with pyyaml python recipe/build.py
python - <<'PY'
import hashlib, os
b = open("crosswalk.csv", "rb").read()
print("sha256:" + hashlib.sha256(b).hexdigest(), len(b))
PY
# paste the printed hash + bytes into datapackage.yaml; set entity.md gene_count
```

If network is unavailable, leave the placeholder hash and `gene_count: 0`; the machinery + hermetic tests below still stand, and the rows are added when the recipe is next run. **Do not commit `crosswalk.csv` with a placeholder hash** — either populate it fully or leave it unbuilt.

- [ ] **Step 7: Create the hermetic synthetic fixture (no network)**

`science/tests/fixtures/commons/gene-crosswalk/datasets/gene-crosswalk-hgnc/entity.md`:

```markdown
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0
id: dataset:gene-crosswalk-hgnc
type: dataset
title: "HGNC gene crosswalk (test fixture)"
version: "1.0.0"
created: "2026-05-27"
updated: "2026-05-27"
datapackage: datapackage.yaml
origin: external
status: active
tier: use-now
access:
  level: public
  verified: true
member_key_column: gene_key
gene_count: 4
---

# HGNC gene crosswalk (test fixture)
```

`science/tests/fixtures/commons/gene-crosswalk-data/gene-crosswalk-hgnc/crosswalk.csv` (data lives under the data-root layout `<data_root>/<slug>/<logical_path>`; `XYZ` is an alias shared by both approved rows to exercise ambiguity):

```csv
gene_key,symbol,entrez_id,ensembl_gene_id,alias_symbol,prev_symbol,status,replacement_gene_keys
9606|hgnc|HGNC:5,A1BG,1,ENSG00000121410,XYZ,,approved,
9606|hgnc|HGNC:37133,A1BG-AS1,503538,ENSG00000268895,FLJ23569;XYZ,NCRNA00181;A1BGAS,approved,
9606|hgnc|HGNC:99991,OLDA,,,,,merged,9606|hgnc|HGNC:5
9606|hgnc|HGNC:99992,SPLITME,,,,,split,9606|hgnc|HGNC:5;9606|hgnc|HGNC:37133
```

`science/tests/fixtures/commons/gene-crosswalk/datasets/gene-crosswalk-hgnc/datapackage.yaml` (fill the hash in Step 8):

```yaml
name: gene-crosswalk-hgnc
profile: data-package
resources:
  - name: crosswalk
    path: crosswalk.csv
    format: csv
    mediatype: text/csv
    hash: "sha256:REPLACE_WITH_FIXTURE_CSV_SHA256"
    bytes: 0
```

- [ ] **Step 8: Pin the fixture CSV hash**

```bash
cd ~/d/science
python - <<'PY'
import hashlib
p = "science/tests/fixtures/commons/gene-crosswalk-data/gene-crosswalk-hgnc/crosswalk.csv"
b = open(p, "rb").read()
print("sha256:" + hashlib.sha256(b).hexdigest(), len(b))
PY
# paste the hash into the fixture datapackage.yaml `hash:` and the byte count into `bytes:`
```

- [ ] **Step 9: Commit**

```bash
cd ~/d/science
# Stage BOTH the entity-store fixture AND the data-root fixture (the resolver
# tests in Task 4 read the CSV under gene-crosswalk-data) — never leave the data
# file untracked.
git add science/tests/fixtures/commons/gene-crosswalk science/tests/fixtures/commons/gene-crosswalk-data
git commit -m "feat(commons): gene-crosswalk reference collection + recipe + test fixture"
# Commit the real commons dataset separately in ~/d/science-commons (unbuilt is fine).
```

(The `~/d/science-commons` dataset is committed in that repo; only the in-`science` test fixtures are committed here.)

---

## Task 4: Gene crosswalk resolver

**Files:**
- Create: `science/src/science_tool/commons/gene_crosswalk.py`
- Test: `science/tests/test_commons_gene_crosswalk.py`

A pure resolver over the crosswalk rows. Reads the data resource through the sha256-verified `resolve()`, exposes the `gene_key` set, and resolves a `(taxon, namespace, gene_id)` to a discriminated result. **Exact `gene_key` equality is identity (RCM-D6);** deprecated rows are surfaced with provenance (never auto-followed); ambiguous inputs return a type with no `gene_key`. The opaque key is **never split** — taxon scoping is done with the `taxon` parameter against `_HUMAN_TAXON`, not by parsing the key. Mirrors `commons/assembly.py`. (Imported by Task 5's build helpers and Task 6's check; its tests read Task 3's fixture.)

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_gene_crosswalk.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.gene_crosswalk import (
    AmbiguousGeneMatch,
    GeneCrosswalkError,
    ResolvedGeneMatch,
    available_gene_keys,
    to_canonical,
)

_FIX = Path(__file__).parent / "fixtures" / "commons" / "gene-crosswalk"
_DATA = Path(__file__).parent / "fixtures" / "commons" / "gene-crosswalk-data"


def _kw() -> dict:
    return {"commons_root": _FIX, "data_root": _DATA}


def test_available_keys_are_the_gene_keys() -> None:
    keys = available_gene_keys(**_kw())
    assert keys == {
        "9606|hgnc|HGNC:5",
        "9606|hgnc|HGNC:37133",
        "9606|hgnc|HGNC:99991",
        "9606|hgnc|HGNC:99992",
    }


def test_resolve_by_hgnc_id_exact() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_id", gene_id="HGNC:5", **_kw())
    assert isinstance(m, ResolvedGeneMatch)
    assert m.gene_key == "9606|hgnc|HGNC:5"
    assert m.symbol == "A1BG"
    assert m.entrez_id == "1"
    assert m.ensembl_gene_id == "ENSG00000121410"
    assert m.match_type == "exact"
    assert m.status == "approved"
    assert m.replacement_gene_key is None


def test_resolve_by_current_symbol() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="A1BG", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:5"
    assert m.match_type == "exact"


def test_resolve_by_prev_symbol() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="A1BGAS", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:37133"
    assert m.match_type == "prev_symbol"


def test_resolve_by_unique_alias() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="FLJ23569", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:37133"
    assert m.match_type == "alias_symbol"


def test_shared_alias_is_ambiguous_with_no_gene_key() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="XYZ", **_kw())
    assert isinstance(m, AmbiguousGeneMatch)
    assert set(m.candidates) == {"9606|hgnc|HGNC:5", "9606|hgnc|HGNC:37133"}
    assert not hasattr(m, "gene_key")


def test_resolve_by_entrez() -> None:
    m = to_canonical(taxon=9606, namespace="entrez", gene_id="503538", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:37133"


def test_resolve_by_ensembl() -> None:
    m = to_canonical(taxon=9606, namespace="ensembl", gene_id="ENSG00000121410", **_kw())
    assert isinstance(m, ResolvedGeneMatch) and m.gene_key == "9606|hgnc|HGNC:5"


def test_merged_id_surfaces_status_and_forward_pointer_not_auto_followed() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_id", gene_id="HGNC:99991", **_kw())
    assert isinstance(m, ResolvedGeneMatch)
    assert m.gene_key == "9606|hgnc|HGNC:99991"  # the matched (merged) row, NOT the target
    assert m.status == "merged"
    assert m.replacement_gene_key == "9606|hgnc|HGNC:5"


def test_split_id_is_ambiguous_over_forward_targets() -> None:
    m = to_canonical(taxon=9606, namespace="hgnc_id", gene_id="HGNC:99992", **_kw())
    assert isinstance(m, AmbiguousGeneMatch)
    assert set(m.candidates) == {"9606|hgnc|HGNC:5", "9606|hgnc|HGNC:37133"}


def test_unknown_id_returns_none() -> None:
    assert to_canonical(taxon=9606, namespace="hgnc_id", gene_id="HGNC:00000", **_kw()) is None


def test_other_taxon_returns_none() -> None:
    # v1 crosswalk is human-only; a non-human taxon resolves nothing (and the
    # resolver does NOT parse the taxon out of the opaque gene_key).
    assert to_canonical(taxon=10090, namespace="hgnc_id", gene_id="HGNC:5", **_kw()) is None


def test_unsupported_namespace_raises() -> None:
    with pytest.raises(GeneCrosswalkError, match="unsupported gene namespace"):
        to_canonical(taxon=9606, namespace="refseq", gene_id="NM_000014", **_kw())


# --- pure row validation (no I/O) ---


def test_parse_rejects_duplicate_member_key() -> None:
    from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows

    rows = [
        {"gene_key": "9606|hgnc|HGNC:5", "status": "approved"},
        {"gene_key": "9606|hgnc|HGNC:5", "status": "approved"},
    ]
    with pytest.raises(GeneCrosswalkError, match="duplicate member key"):
        _parse_crosswalk_rows(rows)


def test_parse_rejects_blank_key() -> None:
    from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows

    with pytest.raises(GeneCrosswalkError, match="blank gene_key"):
        _parse_crosswalk_rows([{"gene_key": "  ", "status": "approved"}])


def test_parse_rejects_missing_column() -> None:
    from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows

    with pytest.raises(GeneCrosswalkError, match="missing required column"):
        _parse_crosswalk_rows([{"symbol": "A1BG", "status": "approved"}])


def test_parse_rejects_unknown_status() -> None:
    from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows

    with pytest.raises(GeneCrosswalkError, match="invalid status"):
        _parse_crosswalk_rows([{"gene_key": "9606|hgnc|HGNC:5", "status": "bogus"}])


def test_make_gene_key_is_pipe_delimited_opaque_composite() -> None:
    from science_tool.commons.gene_crosswalk import make_gene_key

    assert make_gene_key(9606, "HGNC:5") == "9606|hgnc|HGNC:5"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_gene_crosswalk.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.gene_crosswalk'`.

- [ ] **Step 3: Implement the resolver**

Create `science/src/science_tool/commons/gene_crosswalk.py`:

```python
"""Resolver over the gene_key-keyed HGNC gene crosswalk (Pillar C, sub-phase C2).

Third instance of the reference-collection primitive (after gene-sets D and the
assembly registry C1): a ``dataset`` whose member rows are keyed by an opaque
composite ``gene_key`` ``"<taxon>|<namespace>|<id>"`` (e.g. ``9606|hgnc|HGNC:5``).
The key uses ``|`` as its field delimiter so the id field keeps its native CURIE
(``HGNC:5``) intact; **the key is opaque — never split — by everything except**
``make_gene_key`` (RCM-D6: byte-equality is identity). Taxon scoping is done with
the ``taxon`` parameter (``_HUMAN_TAXON``), never by parsing the key; multi-species
support will add an explicit ``taxon`` column rather than derive it from the key.
Pure over pinned, sha256-verified inputs (no network). The public API is
species-aware and namespace-explicit (taxon + namespace on every call; no bare
gene id, C-D1 d6). Deprecated/merged/withdrawn rows are mapped through WITH
provenance (``status`` + ``replacement_gene_key``), never silently returned as
canonical; an ambiguous input returns a distinct ``AmbiguousGeneMatch`` with no
``gene_key`` so a caller cannot misuse an unresolved identity (RCM-D6: never
collapse distinct keys). See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D1/§5).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.resolver import resolve

GENE_CROSSWALK_ID = "dataset:gene-crosswalk-hgnc"
GENE_CROSSWALK_RESOURCE = "crosswalk.csv"
MEMBER_KEY_COLUMN = "gene_key"
SUPPORTED_GENE_NAMESPACES = frozenset({"hgnc_id", "hgnc_symbol", "entrez", "ensembl"})

_HUMAN_TAXON = 9606  # v1 crosswalk is human-only
_VALID_STATUS = frozenset({"approved", "withdrawn", "merged", "split"})
_MULTIVALUE_SEP = ";"  # within-cell separator; NOT '|' (gene_key uses '|' internally)


class GeneCrosswalkError(ValueError):
    """A crosswalk row violates the reference-collection contract, or an
    unsupported namespace was requested (fail early; RCM-D1/D6)."""


def make_gene_key(taxon: int, hgnc_id: str) -> str:
    """Construct the opaque composite member key ``"<taxon>|hgnc|<hgnc_id>"``.

    The single canonical builder. ``hgnc_id`` keeps its native ``HGNC:`` CURIE; the
    ``|`` field delimiter never collides with it. The result is opaque downstream.
    """
    hgnc_id = hgnc_id.strip()
    if not hgnc_id.startswith("HGNC:"):
        raise GeneCrosswalkError(f"hgnc_id must be a 'HGNC:' CURIE, got {hgnc_id!r}")
    return f"{taxon}|hgnc|{hgnc_id}"


@dataclass(frozen=True, slots=True)
class CrosswalkRow:
    """One crosswalk row. Multi-value fields are already split on ';'."""

    gene_key: str
    symbol: str
    entrez_id: str
    ensembl_gene_id: str
    alias_symbol: tuple[str, ...]
    prev_symbol: tuple[str, ...]
    status: str
    replacement_gene_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedGeneMatch:
    """An input that resolves to exactly one canonical gene, with lifecycle
    provenance. ``status != 'approved'`` means the row is deprecated; follow
    ``replacement_gene_key`` explicitly (the resolver never auto-follows)."""

    gene_key: str
    symbol: str
    entrez_id: str | None
    ensembl_gene_id: str | None
    match_type: str  # how the input matched: exact | prev_symbol | alias_symbol
    status: str  # row lifecycle: approved | withdrawn | merged | split
    replacement_gene_key: str | None


@dataclass(frozen=True, slots=True)
class AmbiguousGeneMatch:
    """An input mapping to >1 candidate (a shared symbol/id, or a split entry's
    forward targets). It deliberately has NO ``gene_key``: the caller must not
    pick one (RCM-D6 — never collapse distinct identities)."""

    query: str
    candidates: tuple[str, ...]


GeneMatch = ResolvedGeneMatch | AmbiguousGeneMatch


def _split_multi(cell: str) -> tuple[str, ...]:
    return tuple(part for part in (cell or "").split(_MULTIVALUE_SEP) if part)


def _parse_crosswalk_rows(rows: Iterable[dict[str, Any]]) -> list[CrosswalkRow]:
    """Validate + parse raw CSV rows; fail early on a broken collection (RCM-D1/D6).

    Every row needs a present, non-blank, UNIQUE ``gene_key`` (a duplicate key is
    two rows claiming one identity) and a known ``status``. Pure (no I/O).
    """
    out: list[CrosswalkRow] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if MEMBER_KEY_COLUMN not in row:
            raise GeneCrosswalkError(f"row {i}: missing required column {MEMBER_KEY_COLUMN!r}")
        key = (row.get(MEMBER_KEY_COLUMN) or "").strip()
        if not key:
            raise GeneCrosswalkError(f"row {i}: blank {MEMBER_KEY_COLUMN} (member key)")
        if key in seen:
            raise GeneCrosswalkError(f"duplicate member key {MEMBER_KEY_COLUMN}={key!r}")
        seen.add(key)
        status = (row.get("status") or "").strip()
        if status not in _VALID_STATUS:
            raise GeneCrosswalkError(f"row {i}: invalid status {status!r} (expected one of {sorted(_VALID_STATUS)})")
        out.append(
            CrosswalkRow(
                gene_key=key,
                symbol=(row.get("symbol") or "").strip(),
                entrez_id=(row.get("entrez_id") or "").strip(),
                ensembl_gene_id=(row.get("ensembl_gene_id") or "").strip(),
                alias_symbol=_split_multi(row.get("alias_symbol", "")),
                prev_symbol=_split_multi(row.get("prev_symbol", "")),
                status=status,
                replacement_gene_keys=_split_multi(row.get("replacement_gene_keys", "")),
            )
        )
    return out


def load_gene_crosswalk(
    *,
    registry_id: str = GENE_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[CrosswalkRow]:
    """Load + sha256-verify the crosswalk rows. Raises CommonsError if absent,
    GeneCrosswalkError if a row violates the collection contract."""
    resolved = resolve(registry_id, GENE_CROSSWALK_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as fh:
        return _parse_crosswalk_rows(csv.DictReader(fh))


def available_gene_keys(
    *,
    registry_id: str = GENE_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> set[str]:
    """The set of gene_key member keys for `registry_id` (used by downstream
    payload-resolution audits; check 2 does not call this)."""
    return {
        r.gene_key
        for r in load_gene_crosswalk(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    }


def _match_rows(rows: list[CrosswalkRow], taxon: int, namespace: str, gene_id: str) -> tuple[list[CrosswalkRow], str]:
    """Return (matched_rows, match_type). Pure; `namespace` already validated.

    The v1 crosswalk is human-only; a non-human taxon matches nothing. We gate on
    the `taxon` parameter rather than parse it out of the opaque gene_key.
    """
    if taxon != _HUMAN_TAXON:
        return [], "exact"
    if namespace == "hgnc_id":
        target = make_gene_key(taxon, gene_id)
        return [r for r in rows if r.gene_key == target], "exact"
    if namespace == "entrez":
        return [r for r in rows if r.entrez_id and r.entrez_id == gene_id], "exact"
    if namespace == "ensembl":
        return [r for r in rows if r.ensembl_gene_id and r.ensembl_gene_id == gene_id], "exact"
    # hgnc_symbol: current symbol, then prev_symbol, then alias_symbol (staged).
    by_symbol = [r for r in rows if r.symbol and r.symbol == gene_id]
    if by_symbol:
        return by_symbol, "exact"
    by_prev = [r for r in rows if gene_id in r.prev_symbol]
    if by_prev:
        return by_prev, "prev_symbol"
    return [r for r in rows if gene_id in r.alias_symbol], "alias_symbol"


def to_canonical(
    *,
    taxon: int,
    namespace: str,
    gene_id: str,
    registry_id: str = GENE_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> GeneMatch | None:
    """Resolve a gene id in `namespace` to its canonical gene (RCM-D6).

    Returns ``ResolvedGeneMatch`` for a unique hit (carrying lifecycle ``status``
    + ``replacement_gene_key`` provenance), ``AmbiguousGeneMatch`` when the input
    maps to >1 candidate or to a split entry's forward targets (no ``gene_key`` —
    the caller must not guess), or ``None`` when nothing matches. Raises
    ``GeneCrosswalkError`` for an unsupported namespace (fail early). `gene_id` is
    named to avoid shadowing the ``id`` builtin (ruff A002)."""
    if namespace not in SUPPORTED_GENE_NAMESPACES:
        raise GeneCrosswalkError(
            f"unsupported gene namespace {namespace!r}; expected one of {sorted(SUPPORTED_GENE_NAMESPACES)}"
        )
    rows = load_gene_crosswalk(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    matched, match_type = _match_rows(rows, taxon, namespace, gene_id)
    if not matched:
        return None
    if len(matched) > 1:
        return AmbiguousGeneMatch(query=gene_id, candidates=tuple(sorted(r.gene_key for r in matched)))
    row = matched[0]
    if row.status == "split" and len(row.replacement_gene_keys) >= 2:
        return AmbiguousGeneMatch(query=gene_id, candidates=row.replacement_gene_keys)
    return ResolvedGeneMatch(
        gene_key=row.gene_key,
        symbol=row.symbol,
        entrez_id=row.entrez_id or None,
        ensembl_gene_id=row.ensembl_gene_id or None,
        match_type=match_type,
        status=row.status,
        replacement_gene_key=(row.replacement_gene_keys[0] if row.replacement_gene_keys else None),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_gene_crosswalk.py -v`
Expected: all PASS. (If a `DataIntegrityError` fires, the fixture CSV hash in Task 3 Step 8 was not pinned correctly — re-run the sha256 step.)

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/commons/gene_crosswalk.py science/tests/test_commons_gene_crosswalk.py
git commit -m "feat(commons): HGNC gene crosswalk resolver (discriminated result, RCM-D6)"
```

---

## Task 5: HGNC parsing build helpers

**Files:**
- Create: `science/src/science_tool/commons/gene_crosswalk_build.py`
- Test: `science/tests/test_gene_crosswalk_build.py`

Pure parsing of the two HGNC release files into crosswalk rows. HGNC's native within-cell `|` separators are re-emitted as `;` so they never collide with the `|` inside a `gene_key`. The only network is `fetch_text` (build-time). The single canonical key builder `make_gene_key` lives in `gene_crosswalk.py` (Task 4) — one source of truth — and this module imports it; the round-trip test also imports the resolver's `_parse_crosswalk_rows` to assert the build output and the resolver share one contract.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_gene_crosswalk_build.py`:

```python
from __future__ import annotations

import csv
import io

from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows, make_gene_key
from science_tool.commons.gene_crosswalk_build import (
    build_rows,
    fetch_text,
    parse_complete_set,
    parse_withdrawn,
)

_COMPLETE = (
    "hgnc_id\tsymbol\tstatus\talias_symbol\tprev_symbol\tentrez_id\tensembl_gene_id\n"
    "HGNC:5\tA1BG\tApproved\t\t\t1\tENSG00000121410\n"
    "HGNC:37133\tA1BG-AS1\tApproved\tFLJ23569|XYZ\tNCRNA00181|A1BGAS\t503538\tENSG00000268895\n"
)

_WITHDRAWN = (
    "HGNC_ID\tSTATUS\tWITHDRAWN_SYMBOL\tMERGED_INTO_REPORT(S)\n"
    "HGNC:99991\tMerged/Split\tOLDA\tHGNC:5|A1BG|Approved\n"
    "HGNC:99992\tMerged/Split\tSPLITME\tHGNC:5|A1BG|Approved, HGNC:37133|A1BG-AS1|Approved\n"
    "HGNC:99993\tEntry Withdrawn\tGONE\t\n"
)


def test_make_gene_key_is_pipe_delimited_opaque_composite() -> None:
    assert make_gene_key(9606, "HGNC:5") == "9606|hgnc|HGNC:5"


def test_parse_complete_set_recodes_multivalue_to_semicolon() -> None:
    rows = parse_complete_set(_COMPLETE)
    a1bgas = next(r for r in rows if r["gene_key"] == "9606|hgnc|HGNC:37133")
    assert a1bgas["symbol"] == "A1BG-AS1"
    assert a1bgas["entrez_id"] == "503538"
    assert a1bgas["alias_symbol"] == "FLJ23569;XYZ"  # HGNC '|' re-coded to ';'
    assert a1bgas["prev_symbol"] == "NCRNA00181;A1BGAS"
    assert a1bgas["status"] == "approved"


def test_parse_withdrawn_merged_has_single_forward_pointer() -> None:
    rows = parse_withdrawn(_WITHDRAWN)
    merged = next(r for r in rows if r["gene_key"] == "9606|hgnc|HGNC:99991")
    assert merged["status"] == "merged"
    assert merged["replacement_gene_keys"] == "9606|hgnc|HGNC:5"


def test_parse_withdrawn_split_has_multiple_forward_pointers() -> None:
    rows = parse_withdrawn(_WITHDRAWN)
    split = next(r for r in rows if r["gene_key"] == "9606|hgnc|HGNC:99992")
    assert split["status"] == "split"
    assert split["replacement_gene_keys"] == "9606|hgnc|HGNC:5;9606|hgnc|HGNC:37133"


def test_parse_withdrawn_entry_withdrawn_has_no_replacement() -> None:
    rows = parse_withdrawn(_WITHDRAWN)
    gone = next(r for r in rows if r["gene_key"] == "9606|hgnc|HGNC:99993")
    assert gone["status"] == "withdrawn"
    assert gone["replacement_gene_keys"] == ""


def test_build_rows_round_trips_through_the_resolver_parser() -> None:
    # The build output must parse cleanly back through the resolver's row parser
    # (same gene_key column, same ';' multi-value separator) — they share a contract.
    rows = build_rows(complete_set_text=_COMPLETE, withdrawn_text=_WITHDRAWN)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    parsed = _parse_crosswalk_rows(csv.DictReader(buf))
    assert len(parsed) == len(rows) == 5


def test_fetch_text_is_callable_without_network() -> None:
    # Importing the module does not require a network call.
    assert callable(fetch_text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_gene_crosswalk_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.gene_crosswalk_build'`.

- [ ] **Step 3: Implement the build helpers**

Create `science/src/science_tool/commons/gene_crosswalk_build.py`:

```python
"""No-FASTA, mostly-no-network HGNC parsing for the gene crosswalk (Pillar C, C2).

Parses the HGNC 'complete set' (approved genes) and 'withdrawn' (withdrawn /
merged / split entries) release files into crosswalk rows keyed by the opaque
composite ``gene_key`` (see ``gene_crosswalk.make_gene_key``). HGNC's native
within-cell ``|`` separators are re-emitted as ``;`` so they never collide with
the ``|`` inside a ``gene_key``. ``fetch_text`` is the only network call
(build-time only); all parsing is pure. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D1/C-D3).
"""

from __future__ import annotations

import csv
import io
from typing import Any

from science_tool.commons.gene_crosswalk import make_gene_key

_HUMAN_TAXON = 9606
_OUT_SEP = ";"  # within-cell multi-value separator; NOT '|' (gene_key uses '|')


def _recode(cell: str) -> str:
    """HGNC separates within-cell multi-values with '|'; re-emit as ';' so the
    crosswalk never reuses the gene_key field delimiter."""
    return _OUT_SEP.join(part for part in (cell or "").split("|") if part)


def parse_complete_set(tsv_text: str) -> list[dict[str, Any]]:
    """Parse hgnc_complete_set.txt (tab-separated) into approved crosswalk rows."""
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    rows: list[dict[str, Any]] = []
    for rec in reader:
        hgnc_id = (rec.get("hgnc_id") or "").strip()
        if not hgnc_id:
            continue
        rows.append(
            {
                "gene_key": make_gene_key(_HUMAN_TAXON, hgnc_id),
                "symbol": (rec.get("symbol") or "").strip(),
                "entrez_id": (rec.get("entrez_id") or "").strip(),
                "ensembl_gene_id": (rec.get("ensembl_gene_id") or "").strip(),
                "alias_symbol": _recode(rec.get("alias_symbol", "")),
                "prev_symbol": _recode(rec.get("prev_symbol", "")),
                "status": "approved",
                "replacement_gene_keys": "",
            }
        )
    return rows


def parse_withdrawn(tsv_text: str) -> list[dict[str, Any]]:
    """Parse withdrawn.txt into withdrawn/merged/split rows with forward pointers.

    ``MERGED_INTO_REPORT(S)`` is a comma-separated list of ``HGNC_ID|SYMBOL|STATUS``
    entries; we keep each target's HGNC id and build its gene_key.
    ``STATUS == 'Entry Withdrawn'`` -> ``withdrawn`` (no replacement);
    ``'Merged/Split'`` -> ``merged`` (one target) or ``split`` (>1 target).
    """
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    rows: list[dict[str, Any]] = []
    for rec in reader:
        hgnc_id = (rec.get("HGNC_ID") or "").strip()
        if not hgnc_id:
            continue
        raw_status = (rec.get("STATUS") or "").strip()
        targets: list[str] = []
        for entry in (rec.get("MERGED_INTO_REPORT(S)") or "").split(","):
            entry = entry.strip()
            if not entry:
                continue
            target_id = entry.split("|")[0].strip()
            if target_id.startswith("HGNC:"):
                targets.append(make_gene_key(_HUMAN_TAXON, target_id))
        if raw_status == "Entry Withdrawn":
            status = "withdrawn"
        elif len(targets) >= 2:
            status = "split"
        else:
            status = "merged"
        rows.append(
            {
                "gene_key": make_gene_key(_HUMAN_TAXON, hgnc_id),
                "symbol": (rec.get("WITHDRAWN_SYMBOL") or "").strip(),
                "entrez_id": "",
                "ensembl_gene_id": "",
                "alias_symbol": "",
                "prev_symbol": "",
                "status": status,
                "replacement_gene_keys": _OUT_SEP.join(targets),
            }
        )
    return rows


def build_rows(*, complete_set_text: str, withdrawn_text: str) -> list[dict[str, Any]]:
    """Merge approved + withdrawn rows into the full crosswalk row list."""
    return parse_complete_set(complete_set_text) + parse_withdrawn(withdrawn_text)


def fetch_text(url: str) -> str:
    """Fetch a text release file (build-time only; never called at resolve time)."""
    import httpx

    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_gene_crosswalk_build.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/commons/gene_crosswalk_build.py science/tests/test_gene_crosswalk_build.py
git commit -m "feat(commons): HGNC gene-crosswalk parsing helpers (C-D1/C-D3)"
```

---

## Task 6: Check 2 — gene namespace & registry resolvability (declaration-level)

**Files:**
- Modify: `science/src/science_tool/validate/checks/identity_context.py`
- Test: `science/tests/validate/test_checks_identity_context.py`

Append check 2 to the existing identity check module. For each dataset declaring `identity_context.molecular_ids.gene`, verify the declared `namespace` is crosswalk-supported and the declared `registry` (default `dataset:gene-crosswalk-hgnc`) resolves to a `bio.gene_crosswalk/1.0` collection with `member_key_column: gene_key`. **Declaration-level only — no data payload is read** (decisions §5). Unlike C1's check 1, this does **not** call `evaluate_key_resolution`: a gene declaration names a *namespace*, not a single member key. It mirrors C1's per-declared-registry pattern, but with a registry-*metadata* map instead of a key-set map.

Evaluation order + severity (structural defects first; namespace support is validated **before** the `declared_unresolved` escape, because for the *gene* tier every gene namespace is in C2's scope, so an unsupported gene namespace is a real declaration error that `declared_unresolved` must not excuse — that escape is for non-gene sibling tiers):
1. gene tier not an object, missing/blank `namespace`, a `registry` that is not a `dataset:` reference, or a `resolution_status` outside `{resolved, declared_unresolved}` → ERROR `identity.gene-malformed`. Raw authored frontmatter bypasses the JSON schema (the closed graph `Entity` drops extension fields), so these schema-critical fields are re-enforced here via `_gene_defect`, mirroring C1's `_assembly_defect` — otherwise `resolution_status: maybe` would pass silently and a non-`dataset:` `registry` would degrade to a misleading INFO;
2. `namespace` not in `{hgnc_id, hgnc_symbol, entrez, ensembl}` → ERROR `identity.gene-namespace-unsupported`;
3. `resolution_status: declared_unresolved` → INFO `identity.gene-declared-unresolved` (honoured, RCM-D2), skip;
4. declared registry loads but is **not** a `bio.gene_crosswalk` collection (wrong type) → ERROR `identity.gene-registry-invalid` (a wrong registry must not quietly pass);
5. declared registry unloadable/unknown → INFO `identity.gene-registry-unavailable` (cannot verify), never a false ERROR;
6. supported namespace + valid registry → pass silently.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/validate/test_checks_identity_context.py`:

```python
from science_tool.validate.checks.identity_context import evaluate_gene_identity

_GENE_REGISTRY = "dataset:gene-crosswalk-hgnc"
_VALID_GENE_META = {
    "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
    "member_key_column": "gene_key",
}
_GENE_META_BY_ID = {_GENE_REGISTRY: _VALID_GENE_META}


def _gene_ds(gene, id_="dataset:g") -> dict:
    return {
        "type": "dataset",
        "id": id_,
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0",
        "_path": "data/g/entity.md",
        "identity_context": {"taxon": 9606, "molecular_ids": {"gene": gene}},
    }


def test_gene_supported_namespace_with_valid_registry_passes_silently() -> None:
    ds = _gene_ds({"namespace": "hgnc_id", "canonical": True})
    assert list(evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID)) == []


def test_gene_default_registry_used_when_unspecified() -> None:
    ds = _gene_ds({"namespace": "entrez"})  # no explicit registry -> default
    assert list(evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID)) == []


def test_gene_unsupported_namespace_errors() -> None:
    ds = _gene_ds({"namespace": "refseq"})
    errs = [r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-namespace-unsupported"


def test_gene_declared_unresolved_infos() -> None:
    ds = _gene_ds({"namespace": "hgnc_id", "resolution_status": "declared_unresolved"})
    res = list(evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID))
    assert not [r for r in res if r.severity is Severity.ERROR]
    assert [r for r in res if r.rule == "identity.gene-declared-unresolved"]


def test_gene_declared_unresolved_with_unsupported_namespace_still_errors() -> None:
    # declared_unresolved does not excuse a non-gene namespace: namespace support
    # is validated FIRST. The gene tier must use a recognized gene namespace.
    ds = _gene_ds({"namespace": "refseq", "resolution_status": "declared_unresolved"})
    errs = [r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-namespace-unsupported"


def test_gene_wrong_registry_type_errors() -> None:
    # points at a real dataset that is NOT a gene crosswalk
    meta = {
        "dataset:assembly-registry": {
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.assembly_registry/1.0",
            "member_key_column": "seqcol_digest",
        }
    }
    ds = _gene_ds({"namespace": "hgnc_id", "registry": "dataset:assembly-registry"})
    errs = [r for r in evaluate_gene_identity([ds], registry_meta_by_id=meta) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-registry-invalid"


def test_gene_unloadable_registry_infos_not_errors() -> None:
    ds = _gene_ds({"namespace": "hgnc_id"})
    res = list(evaluate_gene_identity([ds], registry_meta_by_id={_GENE_REGISTRY: None}))
    assert not [r for r in res if r.severity is Severity.ERROR]
    assert [r for r in res if r.rule == "identity.gene-registry-unavailable"]


def test_gene_not_a_dict_errors() -> None:
    ds = _gene_ds("hgnc_id")  # the gene tier must be an object
    errs = [r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-malformed"


def test_gene_missing_namespace_errors() -> None:
    ds = _gene_ds({"canonical": True})
    errs = [r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-malformed"


def test_gene_malformed_registry_errors() -> None:
    # raw frontmatter bypasses the schema: a non-'dataset:' registry must ERROR
    # as malformed, not degrade to a misleading registry-unavailable INFO.
    ds = _gene_ds({"namespace": "hgnc_id", "registry": "gene-crosswalk-hgnc"})
    errs = [r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-malformed"


def test_gene_bad_resolution_status_errors() -> None:
    # 'maybe' must not be treated like 'resolved' and pass silently.
    ds = _gene_ds({"namespace": "hgnc_id", "resolution_status": "maybe"})
    errs = [r for r in evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.gene-malformed"


def test_dataset_without_gene_decl_ignored() -> None:
    ds = {
        "type": "dataset",
        "id": "dataset:x",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0",
        "_path": "data/x/entity.md",
        "identity_context": {"taxon": 9606},
    }
    assert list(evaluate_gene_identity([ds], registry_meta_by_id=_GENE_META_BY_ID)) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_context.py -k gene -v`
Expected: FAIL with `ImportError: cannot import name 'evaluate_gene_identity'`.

- [ ] **Step 3: Append check 2 to the module**

Add these imports at the top of `science/src/science_tool/validate/checks/identity_context.py` (next to the existing imports):

```python
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.gene_crosswalk import (
    GENE_CROSSWALK_ID,
    MEMBER_KEY_COLUMN as _GENE_KEY_COLUMN,
    SUPPORTED_GENE_NAMESPACES,
)
```

Append to the end of the module:

```python
# --- C2: gene identity (check 2 — declaration-level resolvability) ---


def _gene_decl(fm: dict[str, Any]) -> Any:
    """The raw identity_context.molecular_ids.gene declaration, or None."""
    idc = fm.get("identity_context") or {}
    mids = idc.get("molecular_ids") if isinstance(idc, dict) else None
    return mids.get("gene") if isinstance(mids, dict) else None


def _gene_defect(gene: dict[str, Any]) -> str | None:
    """Return a defect message if the raw gene tier is malformed, else None.

    Raw authored frontmatter bypasses the JSON schema (the closed graph Entity
    drops extension fields), so the schema-critical fields are re-enforced here,
    mirroring C1's `_assembly_defect`: `namespace` is required and non-blank;
    `registry`, if present, must be a `dataset:` reference; `resolution_status`,
    if present, must be one of the two valid states. Without this, `maybe` would
    pass like `resolved` and a non-`dataset:` registry would degrade to INFO.
    """
    namespace = gene.get("namespace")
    if not isinstance(namespace, str) or not namespace.strip():
        return "missing or blank namespace"
    registry = gene.get("registry")
    if registry is not None and (not isinstance(registry, str) or not registry.startswith("dataset:")):
        return "registry must be a 'dataset:' reference"
    if gene.get("resolution_status") not in (None, "resolved", "declared_unresolved"):
        return "resolution_status must be 'resolved' or 'declared_unresolved'"
    return None


def _is_gene_crosswalk(meta: dict[str, Any]) -> bool:
    profile = str(meta.get("schema_profile") or "")
    return "+bio.gene_crosswalk/" in f"+{profile}" and meta.get("member_key_column") == _GENE_KEY_COLUMN


def evaluate_gene_identity(
    datasets: Iterable[dict[str, Any]], *, registry_meta_by_id: dict[str, dict[str, Any] | None]
) -> Iterator[Result]:
    """Pure core of check 2 (declaration-level). For each dataset declaring
    identity_context.molecular_ids.gene, verify the namespace is crosswalk-
    supported and the declared registry resolves to a bio.gene_crosswalk
    collection (member_key_column: gene_key). No data payload is read.

    Namespace support is validated BEFORE the declared_unresolved escape: for the
    gene tier every gene namespace is in C2's scope, so an unsupported gene
    namespace is a real error that declared_unresolved must not excuse.
    `registry_meta_by_id` maps each declared (or defaulted) registry id to its
    entity metadata {schema_profile, member_key_column}, or None when it was
    attempted but could not be loaded (→ INFO, never a false ERROR). A loaded
    registry of the WRONG type is an ERROR — a wrong registry must not quietly
    pass. Unlike check 1 this does not resolve a member key: a gene declaration
    names a namespace, not a single key.
    """
    reported_registries: set[str] = set()
    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        gene = _gene_decl(fm)
        if gene is None:
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        if not isinstance(gene, dict):
            yield _result(
                Severity.ERROR, path, f"{ident}: identity_context.molecular_ids.gene must be an object", "identity.gene-malformed"
            )
            continue
        defect = _gene_defect(gene)
        if defect is not None:
            yield _result(
                Severity.ERROR, path, f"{ident}: malformed identity_context.molecular_ids.gene — {defect}", "identity.gene-malformed"
            )
            continue
        namespace = str(gene["namespace"])  # _gene_defect guaranteed present + non-blank str
        if namespace not in SUPPORTED_GENE_NAMESPACES:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: gene namespace {namespace!r} is not crosswalk-supported "
                f"(expected one of {sorted(SUPPORTED_GENE_NAMESPACES)})",
                "identity.gene-namespace-unsupported",
            )
            continue
        if gene.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO, path, f"{ident}: gene identity declared_unresolved (honoured, RCM-D2)", "identity.gene-declared-unresolved"
            )
            continue
        registry_id = gene["registry"] if isinstance(gene.get("registry"), str) else GENE_CROSSWALK_ID
        meta = registry_meta_by_id.get(registry_id)
        if meta is None:
            if registry_id not in reported_registries:
                reported_registries.add(registry_id)
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: gene registry {registry_id!r} unavailable; declared gene namespace cannot be verified",
                    "identity.gene-registry-unavailable",
                )
            continue
        if not _is_gene_crosswalk(meta):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: gene registry {registry_id!r} is not a bio.gene_crosswalk collection "
                f"with member_key_column={_GENE_KEY_COLUMN!r}",
                "identity.gene-registry-invalid",
            )
        # supported namespace + valid crosswalk -> passes silently.


def _load_registry_meta(
    registry_id: str, *, local_by_id: dict[str, dict[str, Any]], commons_cache: dict[str, dict[str, Any] | None]
) -> dict[str, Any] | None:
    """Load a registry's identifying metadata (schema_profile + member_key_column).

    Project-local datasets first, then the commons directly. Returns None when the
    registry cannot be loaded (commons not configured/available, or absent) — the
    evaluator reports that as INFO, never a false ERROR. Mirrors the
    reference-collections check's commons lookup.
    """
    if registry_id in local_by_id:
        fm = local_by_id[registry_id]
        return {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
    if registry_id in commons_cache:
        return commons_cache[registry_id]
    root = resolve_commons_root()
    meta: dict[str, Any] | None = None
    if root.is_dir():
        try:
            record = CommonsEntityAdapter(root).load(registry_id)
            body = getattr(record, "body_path", None)
            fm = _raw_frontmatter(Path(body)) if body else {}
            meta = {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
        except CommonsError:
            meta = None
    commons_cache[registry_id] = meta
    return meta


@Check(section="gene identity", order=27)
def check_gene_identity(ctx: ValidateContext) -> Iterator[Result]:
    datasets = _dataset_frontmatters(ctx)
    local_by_id = {fm["id"]: fm for fm in datasets if isinstance(fm.get("id"), str) and fm["id"]}
    # Load metadata for each registry actually declared (or defaulted) by a gene
    # tier whose namespace is supported and which is not declared_unresolved.
    declared: set[str] = set()
    for fm in datasets:
        gene = _gene_decl(fm)
        if not isinstance(gene, dict) or _gene_defect(gene) is not None:
            continue  # malformed tiers are errored by the evaluator; load no registry for them
        if gene.get("resolution_status") == "declared_unresolved":
            continue
        namespace = str(gene["namespace"])
        if namespace in SUPPORTED_GENE_NAMESPACES:
            declared.add(gene["registry"] if isinstance(gene.get("registry"), str) else GENE_CROSSWALK_ID)
    commons_cache: dict[str, dict[str, Any] | None] = {}
    registry_meta_by_id = {
        registry_id: _load_registry_meta(registry_id, local_by_id=local_by_id, commons_cache=commons_cache)
        for registry_id in declared
    }
    yield from evaluate_gene_identity(datasets, registry_meta_by_id=registry_meta_by_id)
```

(No `__init__.py` change: `identity_context` is already registered.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_context.py -v`
Expected: all PASS (C1's checks 1 & 3 tests + the new gene tests).

- [ ] **Step 5: Run the full validate suite (confirm registration is clean)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate -q`
Expected: PASS. (If a test asserts an exact check inventory, add the `check_gene_identity` function / `identity.gene-*` rules to it — `test_checks_basic.py` only asserts the first 6 checks, so this is unlikely.)

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/identity_context.py science/tests/validate/test_checks_identity_context.py
git commit -m "feat(validate): check 2 — gene namespace & registry resolvability (declaration-level, C2)"
```

---

## Task 7: Migration note, lint, and final C2 verification

**Files:**
- Create: `docs/migration/2026-05-27-gene-crosswalk-identity.md`

C2 makes `identity_context.molecular_ids.gene` resolvable. The migration is light: document the structured gene declaration and the resolver entry point. Like C1, there is no live downstream consumer yet (the check is exercised by fixtures until a gene-bearing dataset adopts `identity_context`).

- [ ] **Step 1: Write the migration note**

Create `docs/migration/2026-05-27-gene-crosswalk-identity.md`:

````markdown
# Declaring gene identity (C2)

A dataset whose data are gene-keyed declares its gene id space via the
`bio.identity_context/1.0` extension's `molecular_ids.gene` tier:

```yaml
identity_context:
  taxon: 9606
  molecular_ids:
    gene:
      namespace: hgnc_id        # hgnc_id | hgnc_symbol | entrez | ensembl
      canonical: true
      registry: dataset:gene-crosswalk-hgnc   # optional; this is the default
      resolution_status: resolved              # or declared_unresolved (RCM-D2)
```

`science validate` (check 2, declaration-level) verifies the namespace is
crosswalk-supported and that `registry` resolves to a `bio.gene_crosswalk/1.0`
collection (`member_key_column: gene_key`). A registry of the wrong type errors;
an unloadable one is reported INFO (cannot verify). This supersedes C1's
"gene resolution lands in C2" — `molecular_ids.gene` is now resolvable.

Payload-level mapping (resolving the actual gene-id column of a dataset) is **not**
done by `science validate`; use the resolver:

```python
from science_tool.commons.gene_crosswalk import to_canonical
m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="TP53")
# -> ResolvedGeneMatch(gene_key="9606|hgnc|HGNC:11998", ...), or
#    AmbiguousGeneMatch(candidates=(...)) when an input maps to >1 gene, or None.
```

The canonical key is the opaque composite `"<taxon>|hgnc|<hgnc_id>"`. Deprecated /
merged / withdrawn ids resolve with `status` + a `replacement_gene_key` forward
pointer (never auto-followed); split entries and shared symbols return
`AmbiguousGeneMatch` (no single key — never guess). Multi-species support is
deferred but the API is taxon-explicit from the start.
````

- [ ] **Step 2: Ruff lint + format both packages**

```bash
cd ~/d/science/science && uv run --frozen ruff check . && uv run --frozen ruff format --check .
cd ~/d/science/science/model && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: clean. If `ruff format --check` reports diffs in files you created, run `uv run --frozen ruff format <file>` and re-commit. Watch for ruff A002 (`gene_id`, not `id`, is used deliberately).

- [ ] **Step 3: Full test sweep of both packages**

```bash
cd ~/d/science/science/model && uv run --frozen pytest -q
cd ~/d/science/science && uv run --frozen pytest -q
```
Expected: PASS in both. (Note: 4 failures pre-exist on `main` and are unrelated to C2 — `test_graph_migrate`, `test_health::test_json_output` ×2, `test_tasks_blockers_json_unresolved`, all "Extra data" JSON-stdout issues. Confirm any failures are exactly these before attributing them to C2.)

- [ ] **Step 4: Smoke-test `science validate`**

Run: `cd ~/d/science && uv run --frozen science validate --verbose` against a project (or rely on the suite). Expected: the gene check runs under section "gene identity" without raising; a dataset declaring `molecular_ids.gene` with a bad namespace surfaces `identity.gene-namespace-unsupported`.

- [ ] **Step 5: Final commit**

```bash
cd ~/d/science
git add docs/migration/2026-05-27-gene-crosswalk-identity.md
git commit -m "docs(bio): gene-crosswalk identity migration note (C2)"

# If ruff reformatted any C2 files, stage them explicitly — never `git add -A`.
git status --short
git add \
  science/src/science_tool/commons/gene_crosswalk.py \
  science/src/science_tool/commons/gene_crosswalk_build.py \
  science/src/science_tool/validate/checks/identity_context.py \
  science/tests/test_gene_crosswalk_build.py \
  science/tests/test_commons_gene_crosswalk.py \
  science/tests/validate/test_checks_identity_context.py
git commit -m "chore(c2): ruff format C2 modules" || echo "nothing to commit"
```

---

## Self-Review (completed by plan author)

**Spec coverage** (against C design §8 C2 + §5 checks 2 & 4, C-D1/C-D3, primitive RCM-D1/D2/D6):
- *Gene crosswalk as a reference collection (third primitive instance), HGNC-anchored* → Task 1 (`bio.gene_crosswalk` `member_key_column: gene_key`) + Task 3 (commons dataset + recipe + fixture) ✓
- *Species-aware `{taxon, namespace, id}` identity, HGNC id anchor, symbol/Entrez/Ensembl inputs (Entrez not canonical)* → Task 4 (`to_canonical(*, taxon, namespace, gene_id)`, `SUPPORTED_GENE_NAMESPACES`, composite `gene_key`) ✓
- *HGNC complete-set + withdrawn source (C-D3, dated/immutable)* → Task 5 (parsing) + Task 3 (recipe `sources.yaml`/`build.py`) ✓
- *Check 2 — identifier resolvability, declaration-level* → Task 6 (`evaluate_gene_identity`; supported namespace before declared_unresolved; declared-registry-or-default; wrong type ERROR, unloadable INFO) ✓
- *Check 4 — deprecated/merged/withdrawn mapped-through-with-provenance, never dropped/guessed* → realized as the **resolver contract** (Task 4: `status` + `replacement_gene_key`, surfaced not auto-followed; `AmbiguousGeneMatch` for split/shared) + Task 5 (`parse_withdrawn`), per the decision to keep payload-level mapping out of `science validate` ✓
- *`molecular_ids.gene` flips declared_unresolved → resolved; registry/resolution_status declarable* → Task 2 (schema) + Task 6 (check) + Task 7 (migration) ✓
- *RCM-D6 exact equality / never collapse distinct keys / opaque key* → Task 4 (`AmbiguousGeneMatch` has no `gene_key`; merge surfaced not followed; `_parse_crosswalk_rows` rejects duplicate keys; taxon gated on a parameter, key never split) ✓

**Type consistency:** `make_gene_key(taxon, hgnc_id) -> str`; `CrosswalkRow(gene_key, symbol, entrez_id, ensembl_gene_id, alias_symbol: tuple, prev_symbol: tuple, status, replacement_gene_keys: tuple)`; `ResolvedGeneMatch(gene_key, symbol, entrez_id, ensembl_gene_id, match_type, status, replacement_gene_key)`; `AmbiguousGeneMatch(query, candidates)`; `to_canonical(*, taxon, namespace, gene_id, registry_id, commons_root, data_root) -> GeneMatch | None`; `available_gene_keys(*, registry_id, commons_root, data_root)`; `load_gene_crosswalk(...)`; `_parse_crosswalk_rows(rows)`; `_match_rows(rows, taxon, namespace, gene_id)`; constants `GENE_CROSSWALK_ID`, `GENE_CROSSWALK_RESOURCE`, `MEMBER_KEY_COLUMN`, `SUPPORTED_GENE_NAMESPACES`, `_HUMAN_TAXON`. Build: `parse_complete_set(tsv_text)`, `parse_withdrawn(tsv_text)`, `build_rows(*, complete_set_text, withdrawn_text)`, `fetch_text(url)`. Check: `evaluate_gene_identity(datasets, *, registry_meta_by_id)`, `_gene_decl(fm)`, `_gene_defect(gene)` (re-enforces namespace/registry/resolution_status on raw frontmatter, mirroring C1's `_assembly_defect`), `_is_gene_crosswalk(meta)`, `_load_registry_meta(registry_id, *, local_by_id, commons_cache)`, `check_gene_identity` (`order=27`). Rules: `identity.gene-malformed`, `identity.gene-namespace-unsupported`, `identity.gene-declared-unresolved`, `identity.gene-registry-invalid`, `identity.gene-registry-unavailable`. Reuses the existing `_dataset_frontmatters`, `_raw_frontmatter`, `_result` from C1's module.

**Two design→implementation reconciliations (deliberate):** (a) Check 2 does **not** consume `evaluate_key_resolution` (a gene declaration names a namespace, not a member key) — it uses a registry-metadata map, mirroring C1's per-declared-registry structure. The substrate's `member_of` promotion is inherited but unused in v1. (b) Check 4 is realized as the resolver contract + downstream tests, not a `science validate` check (the user's "declaration-level only" decision) — `science validate` never reads data payloads.

**Out of scope (per C phasing):** protein (C3) and variant/liftover (C4) tiers; NCBI/Ensembl/BioMart crosswalk sources; multi-species data (API is taxon-ready, data is human-only); promoting a gene to its own `member_of` dataset (no evidence-bearing gene yet); payload-level id-column auditing as a CLI. Populating the real HGNC crosswalk is an operator-run recipe step (network); the acceptance gate is the hermetic fixture + green tests.

---

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task with two-stage review between tasks (REQUIRED SUB-SKILL: superpowers:subagent-driven-development). Tasks are in dependency order (1→7); dispatch them in order. Implement on a `feat/c2-gene-crosswalk` branch, not `main`.
2. **Inline Execution** — execute tasks in this session with checkpoints (REQUIRED SUB-SKILL: superpowers:executing-plans).
