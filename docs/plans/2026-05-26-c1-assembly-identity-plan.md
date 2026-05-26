# C1 Assembly Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Pillar C sub-phase **C1 — assembly identity**: a `bio.identity_context/1.0` declaration component, the assembly registry as a pinned reference collection keyed by `seqcol_digest` (built no-FASTA via `refget`/seqcolapi), a pure registry resolver, and validate checks 1 & 3 (assembly declared-&-recognized; cross-dataset assembly mismatch, detect-only) — consuming the Plan 1 substrate (`evaluate_key_resolution`) for exact-equality key resolution.

**Architecture:** Three layers. (1) **science-model**: two additive extension schemas — `bio.identity_context/1.0` (the coordinate-system declaration: `taxon` + `molecular_ids.<tier>.namespace` + inline `assembly.{seqcol_digest,label,registry,resolution_status}`) and a minimal `bio.assembly_registry/1.0` (the collection's `member_key_column: seqcol_digest`). (2) **commons data**: the `dataset:assembly-registry` reference collection (entity + datapackage) plus a no-FASTA build recipe that pins seqcolapi level-2 records and recomputes the canonical seqcol digest as an integrity gate. (3) **science-tool**: a pure resolver over the registry rows (`available_assembly_keys`, `resolve_assembly`) and two `science validate` checks. Implements C-D2/C-D5/C-D6 and §5 checks 1 & 3 of `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md`, with the assembly registry as the second instance of the foundation primitive (`docs/plans/2026-05-26-reference-collection-member-promotion-design.md`).

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, `pytest`, `uv` (`uv run --frozen`), the `science-model` and `science` (`science_tool`) packages, `httpx` (already a science-tool dep, build-time fetch only), and `refget` (PyPI, recipe-only, lazily imported). All repo paths are relative to `~/d/science`; the commons lives at `~/d/science-commons`.

---

## Background the implementer must read first

- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C. **C-D2** (assembly identity = refget seqcol digest; exact `seqcol_digest` equality is identity; registry is a reference-collection instance keyed by `seqcol_digest`). **C-D6** (the `bio.identity_context/1.0` component shape). **§5 checks 1 & 3** (assembly declared/recognized; cross-dataset mismatch, C1 detect-only). **§8** locks C1 = assembly registry + identity_context container + checks 1 & 3, exact-equality only.
- `docs/plans/2026-05-26-reference-collection-member-promotion-design.md` — the primitive. RCM-D2 (resolve-or-`declared_unresolved`, guardrail 1); RCM-D6 (exact key equality is identity; compatibility is a *separate* relation, never a key collapse — C1 ships equality only). The assembly registry is the **second instance**.
- `docs/plans/2026-05-26-generic-reference-collection-substrate-plan.md` — **Plan 1 (the substrate this plan consumes)**. It ships `science_tool/commons/member.py` with the **pure, dict-based** helpers `parse_member_of(entity_dict) -> MemberOf | None`, `evaluate_key_resolution(*, key, available_keys, declared_status) -> ResolutionState`, and `ResolutionState{RESOLVED, UNRESOLVED, DECLARED_UNRESOLVED, UNKNOWN}`. **C1 is where Plan 1's deferred "member-key-in-collection verification" becomes concrete for the assembly instance**: this plan supplies `available_keys` (the registry's seqcol digests) so `evaluate_key_resolution` returns RESOLVED/UNRESOLVED instead of UNKNOWN. **Plan 1 must be executed (or at least its `member.py` merged) before Task 6 of this plan.**

### Two grounding facts that shape this plan (verified against the codebase)

1. **The graph `Entity` is a closed pydantic model.** `science_model/entities.py::Entity` has no `extra="allow"`, carries no `identity_context`/`reference_genome`, and its typed `derivation` (`science_model/packages/schema.py::DerivationBlock`) is a *different* shape (`workflow`/`workflow_run`/`git_commit`/…) with **no** `kind`/`member_key`. **Therefore validate checks must read extension fields from RAW frontmatter, never via `getattr(entity, "identity_context")`.** This plan's checks re-parse `entity.file_path` (a tiny `_raw_frontmatter` helper handling both `entity.md` fenced YAML and `datapackage.yaml`). Plan 1's *pure* helpers are dict-based, so they accept raw frontmatter directly — that is the clean consumption path. (Note for the reviewer: Plan 1's own Task-4 check reads `getattr(entity, "derivation")`, which will silently no-op against this closed Entity; it needs the same raw-frontmatter correction. Flagged separately — not fixed here.)

2. **Profile composition is `allOf` over profile-string components; there is no cross-file `$ref`.** `EntityValidator._compose()` builds `{"allOf": [base, mixin, ext1, ext2, …]}` from the `schema_profile` string. The filename convention (`entity_schema/loader.py::_filename_for`) is `name.replace(".", "-")` → so `bio.identity_context` → `extension-bio-identity_context-1.0.json` (**underscore preserved**) and `bio.assembly_registry` → `extension-bio-assembly_registry-1.0.json`. Consequently `bio.identity_context/1.0` is realized as a **sibling extension added to a dataset's profile** (`…+bio.rnaseq/1.0+bio.identity_context/1.0`), not as a field referenced *by* `bio.rnaseq`. The *requirement* that a coordinate-bearing dataset declare it is enforced by **check 1** (the validate surface), exactly as the design's §5 specifies — not by JSON-schema cross-refs.

### Codebase anchors (read before writing code)

- Schemas dir: `science/model/src/science_model/schemas/` — existing `extension-bio-rnaseq-1.0.json` etc.; `reference_genome` is `{"type":"string","minLength":1}` (optional, top-level) on `bio.rnaseq`/`bio.scrna`/`bio.cna`. The `$defs` + `#/$defs/...` same-file `$ref` pattern is in `mixin-dataset-1.0.json`.
- Model test template: `science/model/tests/test_bio_extension_cna.py` (fixture dict → `SchemaLoader().load(ProfileComponent(...))` → `EntityValidator().validate(...)` → `EntityValidationError`).
- Commons exemplar: `~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/` (`entity.md` + `datapackage.yaml` + stub `recipe/`). Commons root resolves via `science_tool/commons/config.py::resolve_commons_root()` (env `SCIENCE_COMMONS_ROOT` → global config → default `~/d/science-commons`).
- Data resolver: `science/src/science_tool/commons/resolver.py::resolve(dataset_id, logical_path, *, commons_root=None, data_root=None) -> ResolvedDataResource` (sha256-verified; `.path`); errors in `science_tool/commons/errors.py` (`CommonsError` base).
- Validate check idiom: `science/src/science_tool/validate/checks/code_files.py` — `@Check(section=..., order=...)`, `Result(severity, path, line, message, rule, task)`, `Severity{ERROR,WARN,INFO}`, `ValidateContext.from_project_root(root, *, strict, verbose)` with `.project_root`. `load_project_sources(project_root, *, include_commons=True) -> ProjectSources` exposes `.entities: list[Entity]` (each with `.kind`, `.canonical_id`, `.file_path`) and `.markdown_documents: list[MarkdownSourceDocument]` (`.path`, `.frontmatter`, `.body`). Registration: add the module name in `_load_canonical_checks()` in `validate/checks/__init__.py`. Check test template: `science/tests/validate/test_produced_by_check.py` (a `_ctx(tmp_path)` helper writing a minimal `science.yaml` + `knowledge/local/`).
- Existing in-use check `order=` values: 6, 7 (`code_files`), 20 (`cross_references`); Plan 1 takes 24 (`reference_collections`). This plan takes **25** (check 1) and **26** (check 3).

---

## Prerequisite (before Task 6)

Task 6 consumes Plan 1's substrate and assumes the reference-collection check is **load-bearing**. As written, Plan 1's Task-4 check reads the member-of derivation via `getattr(entity, "derivation")` off the closed graph `Entity`, whose typed `DerivationBlock` has no `kind`/`member_key` — so it will silently no-op on `member_of` datasets. **Before executing Task 6:** amend Plan 1's Task 4 to read raw frontmatter (the same `_raw_frontmatter` / `entity.file_path`-under-`project_root` pattern this plan uses) instead of the typed entity, and re-run Plan 1's check tests. Plan 1's *pure* helpers (`parse_member_of`, `evaluate_key_resolution`) are dict-based and need no change — only its check's data source does. (Tasks 1–5 of this plan do not depend on Plan 1 and may proceed first.)

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json` | Create | The `identity_context` declaration component (taxon + molecular_ids + assembly). |
| `science/model/tests/test_bio_extension_identity_context.py` | Create | Schema tests for `bio.identity_context`. |
| `science/model/src/science_model/schemas/extension-bio-assembly_registry-1.0.json` | Create | Minimal collection extension: `member_key_column: seqcol_digest`. |
| `science/model/tests/test_bio_extension_assembly_registry.py` | Create | Schema tests for `bio.assembly_registry`. |
| `science/src/science_tool/commons/assembly_registry_build.py` | Create | No-FASTA recipe helpers: `compute_seqcol_digest`, `build_registry_row` (recompute-and-assert), `fetch_seqcol_level2` (build-time network). |
| `science/tests/test_assembly_registry_build.py` | Create | Recipe tests (inherent-attrs invariant; digest-mismatch raises); `pytest.importorskip("refget")`. |
| `~/d/science-commons/datasets/assembly-registry/entity.md` | Create | The reference-collection dataset entity. |
| `~/d/science-commons/datasets/assembly-registry/datapackage.yaml` | Create | The `assemblies.csv` resource + sha256. |
| `~/d/science-commons/datasets/assembly-registry/recipe/build.py` | Create | Thin operator-run wrapper calling the build helpers; writes `assemblies.csv`. |
| `~/d/science-commons/datasets/assembly-registry/recipe/sources.yaml` | Create | Pinned `{label, seqcol_digest, accession}` inputs the recipe fetches+verifies. |
| `~/d/science-commons/datasets/assembly-registry/recipe/README.md` | Create | How to (re)build the registry. |
| `science/src/science_tool/commons/assembly.py` | Create | Pure resolver: `AssemblyEntry`, `load_assembly_registry`, `available_assembly_keys`, `resolve_assembly`. |
| `science/tests/test_commons_assembly.py` | Create | Resolver tests against a synthetic fixture registry. |
| `science/tests/fixtures/commons/assembly/` (+ `assembly-data/`) | Create | Hermetic fixture: a 2-row registry entity store + data file + sha256. |
| `science/src/science_tool/validate/checks/identity_context.py` | Create | Check 1 (`order=25`) + check 3 (`order=26`) + `_raw_frontmatter` + pure evaluators. |
| `science/src/science_tool/validate/checks/__init__.py` | Modify | Register `identity_context` in `_load_canonical_checks()`. |
| `science/tests/validate/test_checks_identity_context.py` | Create | Tests for the pure evaluators of checks 1 & 3. |
| `docs/usage/assembly-identity.md` (or nearest existing usage dir) | Create | Migration note: free-text `reference_genome` → `identity_context.assembly`. |

---

## Task 1: `bio.identity_context/1.0` extension schema

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json`
- Test: `science/model/tests/test_bio_extension_identity_context.py`

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_bio_extension_identity_context.py` (mirrors `test_bio_extension_cna.py`):

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_idc_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.identity_context/1.0",
        "id": "dataset:example-idc",
        "type": "dataset",
        "title": "Example dataset with identity context",
        "version": "1.0.0",
        "created": "2026-05-26",
        "updated": "2026-05-26",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "identity_context": {
            "taxon": 9606,
            "molecular_ids": {"gene": {"namespace": "hgnc", "canonical": True}},
            "assembly": {
                "seqcol_digest": "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
                "label": "GRCh38",
                "registry": "dataset:assembly-registry",
                "resolution_status": "resolved",
            },
        },
    }


def test_loader_resolves_identity_context_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.identity_context", version="1.0"))
    assert schema["$id"].endswith("extension-bio-identity_context-1.0.json")


def test_minimal_valid_identity_context_passes(base_idc_entity: dict) -> None:
    EntityValidator().validate(base_idc_entity)


def test_identity_context_required_when_extension_declared(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]
    with pytest.raises(EntityValidationError, match="identity_context"):
        EntityValidator().validate(base_idc_entity)


def test_taxon_required(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]["taxon"]
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_requires_seqcol_digest(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]["assembly"]["seqcol_digest"]
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_requires_resolution_status(base_idc_entity: dict) -> None:
    del base_idc_entity["identity_context"]["assembly"]["resolution_status"]
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_requires_registry(base_idc_entity: dict) -> None:
    # The declared reference collection is part of the contract, not advisory
    # (finding 1): a keyed reference must name the registry it resolves against.
    del base_idc_entity["identity_context"]["assembly"]["registry"]
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_rejects_unknown_resolution_status(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["assembly"]["resolution_status"] = "maybe"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_assembly_declared_unresolved_passes(base_idc_entity: dict) -> None:
    # A keyed reference may be declared_unresolved (RCM-D2, guardrail 1).
    base_idc_entity["identity_context"]["assembly"]["resolution_status"] = "declared_unresolved"
    EntityValidator().validate(base_idc_entity)


def test_registry_must_be_dataset_ref(base_idc_entity: dict) -> None:
    base_idc_entity["identity_context"]["assembly"]["registry"] = "assembly-registry"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_idc_entity)


def test_identity_context_allows_future_sibling_keys(base_idc_entity: dict) -> None:
    # additionalProperties: true on identity_context leaves room for later
    # non-molecular siblings (cell_line, disease, ontology) — C-D6.
    base_idc_entity["identity_context"]["cell_line"] = {"namespace": "cellosaurus"}
    EntityValidator().validate(base_idc_entity)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_identity_context.py -v`
Expected: FAIL — `test_loader_resolves_identity_context_schema` raises a load error (file missing) and the rest error out because the schema does not exist.

- [ ] **Step 3: Create the schema**

Create `science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json`:

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
              "canonical": {"type": "boolean"}
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

Notes: `identity_context.additionalProperties: true` is deliberate (C-D6 siblings). `assembly.additionalProperties: false` keeps the assembly block tight (exact-equality identity in C1; compatibility/liftover fields arrive in C4). Both `registry` and `resolution_status` are required whenever `assembly` is present — the keyed reference must name the collection it resolves against (the check passes *that* registry id through, not a hard-coded default), and the status is never an unchecked string (RCM-D2).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_identity_context.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/schemas/extension-bio-identity_context-1.0.json science/model/tests/test_bio_extension_identity_context.py
git commit -m "feat(bio): bio.identity_context/1.0 declaration component (C-D6)"
```

---

## Task 2: `bio.assembly_registry/1.0` collection extension

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-assembly_registry-1.0.json`
- Test: `science/model/tests/test_bio_extension_assembly_registry.py`

The assembly registry is the collection dataset (second instance of the primitive). Its only extension-specific facts: the member-key column is `seqcol_digest` (a `const`, so it is machine-checkable that this collection is seqcol-keyed) and an optional `assembly_count`.

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_bio_extension_assembly_registry.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_registry_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.assembly_registry/1.0",
        "id": "dataset:assembly-registry",
        "type": "dataset",
        "title": "Assembly registry (seqcol-keyed reference collection)",
        "version": "1.0.0",
        "created": "2026-05-26",
        "updated": "2026-05-26",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "member_key_column": "seqcol_digest",
        "assembly_count": 2,
    }


def test_loader_resolves_assembly_registry_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.assembly_registry", version="1.0"))
    assert schema["$id"].endswith("extension-bio-assembly_registry-1.0.json")


def test_minimal_valid_registry_passes(base_registry_entity: dict) -> None:
    EntityValidator().validate(base_registry_entity)


def test_member_key_column_required(base_registry_entity: dict) -> None:
    del base_registry_entity["member_key_column"]
    with pytest.raises(EntityValidationError, match="member_key_column"):
        EntityValidator().validate(base_registry_entity)


def test_member_key_column_must_be_seqcol_digest(base_registry_entity: dict) -> None:
    base_registry_entity["member_key_column"] = "accession"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_registry_entity)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_assembly_registry.py -v`
Expected: FAIL (schema file missing).

- [ ] **Step 3: Create the schema**

Create `science/model/src/science_model/schemas/extension-bio-assembly_registry-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-assembly_registry-1.0.json",
  "title": "science entity bio.assembly_registry extension",
  "type": "object",
  "required": ["member_key_column"],
  "properties": {
    "member_key_column": {"const": "seqcol_digest"},
    "assembly_count": {"type": "integer", "minimum": 0}
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_assembly_registry.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full model suite (no regression)**

Run: `cd ~/d/science/science/model && uv run --frozen pytest -q`
Expected: PASS (additive schemas; nothing else affected).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/schemas/extension-bio-assembly_registry-1.0.json science/model/tests/test_bio_extension_assembly_registry.py
git commit -m "feat(bio): bio.assembly_registry/1.0 collection extension (seqcol-keyed)"
```

---

## Task 3: No-FASTA registry build helpers

**Files:**
- Create: `science/src/science_tool/commons/assembly_registry_build.py`
- Test: `science/tests/test_assembly_registry_build.py`

The canonical seqcol digest is computed over the **inherent attributes `names` + `sequences` only** (lengths are carried in the level-2 record but **not** folded into the digest — GA4GH seqcol v1.0.0). We never touch FASTA: per-contig `SQ.` digests come from a refget seqcol server's level-2 record. `refget` is imported lazily so the resolver/checks (Tasks 5–7) carry no dependency on it.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_assembly_registry_build.py`:

```python
from __future__ import annotations

import pytest

# Import the module unconditionally: it must import cleanly WITHOUT refget
# (refget is imported lazily inside the digest functions). Only the assertions
# that actually compute a digest skip when refget is absent.
from science_tool.commons.assembly_registry_build import (
    build_registry_row,
    compute_seqcol_digest,
    fetch_seqcol_level2,
)

_L2 = {
    "names": ["chr1", "chr2"],
    "lengths": [10, 20],
    "sequences": ["SQ.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "SQ.bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
}


def test_module_imports_without_refget() -> None:
    # The lazy-import contract: importing the module does not require refget.
    assert callable(compute_seqcol_digest)
    assert callable(build_registry_row)
    assert callable(fetch_seqcol_level2)


def test_lengths_are_not_inherent() -> None:
    pytest.importorskip("refget")
    # Same names+sequences, different lengths -> identical digest. The helper
    # passes ONLY the inherent payload (names + sequences) with an explicit
    # inherent_attrs, so lengths cannot leak into the canonical id.
    other = {**_L2, "lengths": [999, 999]}
    assert compute_seqcol_digest(_L2) == compute_seqcol_digest(other)


def test_sequences_change_the_digest() -> None:
    pytest.importorskip("refget")
    other = {**_L2, "sequences": ["SQ.cccccccccccccccccccccccccccccccc", _L2["sequences"][1]]}
    assert compute_seqcol_digest(_L2) != compute_seqcol_digest(other)


def test_build_row_round_trips_when_digest_matches() -> None:
    pytest.importorskip("refget")
    digest = compute_seqcol_digest(_L2)
    row = build_registry_row(
        level2=_L2, label="TEST", accession="GCA_TEST.1", server_digest=digest, source_url="https://x"
    )
    assert row["seqcol_digest"] == digest
    assert row["label"] == "TEST"
    assert row["accession"] == "GCA_TEST.1"
    assert row["n_sequences"] == 2


def test_build_row_raises_on_digest_mismatch() -> None:
    pytest.importorskip("refget")
    with pytest.raises(ValueError, match="digest mismatch"):
        build_registry_row(
            level2=_L2, label="TEST", accession="GCA_TEST.1",
            server_digest="not-the-real-digest", source_url="https://x",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_assembly_registry_build.py -v`
Expected: ALL tests FAIL at collection with `ModuleNotFoundError: No module named 'science_tool.commons.assembly_registry_build'` (the module does not exist yet — including `test_module_imports_without_refget`). After Step 3, `test_module_imports_without_refget` always runs (the module imports without `refget`); the four digest tests run when `refget` is installed and SKIP otherwise. To exercise the digest assertions, install `refget` into the run env (e.g. `uv run --with refget pytest ...`); do **not** add `refget` to `science_tool`'s pinned deps.

- [ ] **Step 3: Implement the build helpers**

Create `science/src/science_tool/commons/assembly_registry_build.py`:

```python
"""No-FASTA build helpers for the seqcol-keyed assembly registry (C-D2).

The canonical seqcol digest is computed over the inherent attributes
``names`` + ``sequences`` only (GA4GH seqcol v1.0.0); ``lengths`` is carried in
the level-2 record but is not part of the collection identity. Per-contig
``SQ.`` digests come from a refget seqcol server's level-2 record, so no FASTA
is ever fetched. ``refget`` is imported lazily — only building the registry
needs it; resolving/validating it does not. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D2).
"""

from __future__ import annotations

from typing import Any

_SEQCOL_SERVER = "https://seqcolapi.databio.org"


_INHERENT_ATTRS = ["names", "sequences"]  # GA4GH seqcol v1.0.0; lengths is NOT inherent


def compute_seqcol_digest(level2: dict[str, Any]) -> str:
    """Canonical seqcol digest from a level-2 record {names, lengths, sequences}.

    The canonical identity is over the inherent attributes ``names`` +
    ``sequences`` only; ``lengths`` is carried in the level-2 record but is NOT
    part of the collection identity (GA4GH seqcol v1.0.0). We therefore (1) pass
    only the inherent payload and (2) pass ``inherent_attrs`` explicitly, so the
    digest is correct regardless of the library's default — it never depends on
    refget silently dropping ``lengths``. ``refget.utils.seqcol_digest`` applies
    the spec's canonical-JSON + sha512t24u rollup over exactly these attributes.
    """
    from refget.utils import seqcol_digest  # lazy: recipe-only dependency

    return seqcol_digest(
        {"names": list(level2["names"]), "sequences": list(level2["sequences"])},
        inherent_attrs=_INHERENT_ATTRS,
    )


def build_registry_row(
    *, level2: dict[str, Any], label: str, accession: str, server_digest: str, source_url: str
) -> dict[str, Any]:
    """Build one registry row, asserting the recomputed digest matches the server.

    The recompute-and-assert is the integrity gate: it proves the pinned
    level-2 record reproduces the canonical identifier with zero FASTA.
    """
    computed = compute_seqcol_digest(level2)
    if computed != server_digest:
        raise ValueError(
            f"seqcol digest mismatch for {label!r}: server={server_digest!r} computed={computed!r}"
        )
    return {
        "seqcol_digest": server_digest,
        "label": label,
        "accession": accession,
        "n_sequences": len(level2["names"]),
        "source_url": source_url,
    }


def fetch_seqcol_level2(digest: str, *, base_url: str = _SEQCOL_SERVER) -> dict[str, Any]:
    """Fetch a level-2 seqcol record from a refget seqcol server (build-time only).

    Network call — used only when (re)building the registry, never at resolve
    time. The level-2 response carries {names, lengths, sequences[SQ...]}.
    """
    import httpx

    resp = httpx.get(f"{base_url}/collection/{digest}", params={"level": 2}, timeout=30.0)
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_assembly_registry_build.py -v`
Expected: PASS (with `refget` installed in the running env), or SKIP otherwise. The full-suite gate (Task 8) re-confirms.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/commons/assembly_registry_build.py science/tests/test_assembly_registry_build.py
git commit -m "feat(commons): no-FASTA seqcol registry build helpers (C-D2)"
```

---

## Task 4: Assembly registry commons dataset + synthetic test fixture

**Files:**
- Create: `~/d/science-commons/datasets/assembly-registry/{entity.md,datapackage.yaml,recipe/build.py,recipe/sources.yaml,recipe/README.md}`
- Create: `science/tests/fixtures/commons/assembly/datasets/assembly-registry/{entity.md,datapackage.yaml}`
- Create: `science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv`

This task creates (a) the real commons reference-collection dataset + its operator-run recipe, and (b) a **hermetic synthetic fixture** (fixed digest strings, no network, no refget) used by Tasks 5–7. The real registry rows are populated by running the recipe (network); the plan's acceptance gate is the hermetic fixture + green tests, not the populated real rows.

- [ ] **Step 1: Create the real commons dataset entity**

`~/d/science-commons/datasets/assembly-registry/entity.md`:

```markdown
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.assembly_registry/1.0
id: dataset:assembly-registry
type: dataset
title: "Assembly registry — seqcol-keyed reference collection of genome assemblies"
version: "1.0.0"
created: "2026-05-26"
updated: "2026-05-26"
tags: []
access:
  level: public
  availability: available
  verified: true
  verification_method: retrieved
  source_url: https://seqcolapi.databio.org
datapackage: datapackage.yaml
origin: external
status: active
tier: use-now
update_cadence: static
member_key_column: seqcol_digest
assembly_count: 0
---

# Assembly registry

A reference collection (foundation primitive, second instance) whose member rows
are addressed by their GA4GH refget Sequence Collection (seqcol) digest. Built
no-FASTA from pinned seqcol-server level-2 records; see `recipe/`. Individual
assemblies are promoted to their own `dataset` (derivation `kind: member_of`,
`member_key` = the `seqcol_digest`) only on demand.
```

(Set `assembly_count` to the real row count after Step 6.)

- [ ] **Step 2: Create the datapackage (hash filled in Step 6)**

`~/d/science-commons/datasets/assembly-registry/datapackage.yaml`:

```yaml
name: assembly-registry
profile: data-package
title: "Assembly registry — seqcol digests for canonical genome assemblies"
version: "1.0.0"
licenses:
  - name: CC0-1.0
    path: https://creativecommons.org/publicdomain/zero/1.0/
    title: Creative Commons Zero v1.0 Universal
provenance:
  - action: build
    tool: recipe/build.py
resources:
  - name: assemblies
    path: assemblies.csv
    format: csv
    mediatype: text/csv
    description: "One row per assembly: seqcol_digest (member key), label, accession, n_sequences, source_url."
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 0
```

- [ ] **Step 3: Create the pinned recipe inputs**

`~/d/science-commons/datasets/assembly-registry/recipe/sources.yaml` (the operator fills the real seqcol digests — see README for how to discover them):

```yaml
# Pinned seqcol collection digests, fetched + verified no-FASTA at build time.
# Discover digests via the seqcol server's /list/collection endpoint or the
# refget seqcol standard paper; each is recompute-verified by build.py.
assemblies:
  - label: GRCh38
    accession: GCA_000001405.15
    seqcol_digest: "REPLACE_WITH_GRCh38_SEQCOL_DIGEST"
  - label: GRCh37
    accession: GCA_000001405.14
    seqcol_digest: "REPLACE_WITH_GRCh37_SEQCOL_DIGEST"
```

- [ ] **Step 4: Create the recipe runner**

`~/d/science-commons/datasets/assembly-registry/recipe/build.py`:

```python
"""Operator-run, no-FASTA build of the assembly registry's assemblies.csv.

Run from the dataset directory:  uv run --with refget --with httpx \
    --with pyyaml python recipe/build.py
Network is used only to fetch pinned seqcol level-2 records; output is KBs.
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from science_tool.commons.assembly_registry_build import build_registry_row, fetch_seqcol_level2

_HERE = Path(__file__).resolve().parent
_OUT = _HERE.parent / "assemblies.csv"
_FIELDS = ["seqcol_digest", "label", "accession", "n_sequences", "source_url"]


def main() -> None:
    sources = yaml.safe_load((_HERE / "sources.yaml").read_text(encoding="utf-8"))
    rows = []
    for src in sources["assemblies"]:
        level2 = fetch_seqcol_level2(src["seqcol_digest"])
        rows.append(
            build_registry_row(
                level2=level2,
                label=src["label"],
                accession=src["accession"],
                server_digest=src["seqcol_digest"],
                source_url=f"https://seqcolapi.databio.org/collection/{src['seqcol_digest']}",
            )
        )
    with _OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {_OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Write the recipe README**

`~/d/science-commons/datasets/assembly-registry/recipe/README.md`:

```markdown
# Assembly registry build (no-FASTA)

1. Fill `sources.yaml` with each assembly's seqcol collection digest. Discover
   digests from `https://seqcolapi.databio.org/list/collection` (or the refget
   seqcol standard paper). The build verifies each by recomputing it from the
   server's level-2 record (`names` + `sequences`), so a wrong digest fails fast.
2. Build: `uv run --with refget --with httpx --with pyyaml python recipe/build.py`
   (writes `../assemblies.csv`).
3. Pin the artifact hash + size into `datapackage.yaml`:
   `python - <<'PY'\nimport hashlib,os;p="assemblies.csv";print("sha256:"+hashlib.sha256(open(p,'rb').read()).hexdigest(),os.path.getsize(p))\nPY`
4. Update `entity.md` `assembly_count` to the row count.

No FASTA is downloaded; per-contig `SQ.` digests come from the seqcol server.
```

- [ ] **Step 6: (Operator step — network) Populate the real registry**

If network + `refget` are available: fill `sources.yaml` digests, run the build, then update the datapackage hash/bytes and `entity.md` `assembly_count`:

```bash
cd ~/d/science-commons/datasets/assembly-registry
uv run --with refget --with httpx --with pyyaml python recipe/build.py
python - <<'PY'
import hashlib, os
b = open("assemblies.csv", "rb").read()
print("sha256:" + hashlib.sha256(b).hexdigest(), len(b))
PY
# paste the printed hash + bytes into datapackage.yaml; set entity.md assembly_count
```

If network is unavailable, leave the placeholder hash and `assembly_count: 0`; the machinery + hermetic tests below still stand, and the rows are added when the recipe is next run. **Do not commit `assemblies.csv` with a placeholder hash** — either populate it fully or leave it unbuilt.

- [ ] **Step 7: Create the hermetic synthetic fixture (no network, no refget)**

`science/tests/fixtures/commons/assembly/datasets/assembly-registry/entity.md` (a 2-row registry; mirrors the real entity but self-contained):

```markdown
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.assembly_registry/1.0
id: dataset:assembly-registry
type: dataset
title: "Assembly registry (test fixture)"
version: "1.0.0"
created: "2026-05-26"
updated: "2026-05-26"
datapackage: datapackage.yaml
origin: external
status: active
tier: use-now
access:
  level: public
  verified: true
member_key_column: seqcol_digest
assembly_count: 2
---

# Assembly registry (test fixture)
```

`science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv` (the data lives under the data-root layout `<data_root>/<slug>/<logical_path>`; two fixed, arbitrary-but-stable digest strings):

```csv
seqcol_digest,label,accession,n_sequences,source_url
g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp,GRCh38,GCA_000001405.15,2,https://example.org/grch38
5K4odB173rjao1Cnbk5BnvLt9V7aPAa2,GRCh37,GCA_000001405.14,2,https://example.org/grch37
```

`science/tests/fixtures/commons/assembly/datasets/assembly-registry/datapackage.yaml` (fill the hash in Step 8):

```yaml
name: assembly-registry
profile: data-package
resources:
  - name: assemblies
    path: assemblies.csv
    format: csv
    mediatype: text/csv
    hash: "sha256:REPLACE_WITH_FIXTURE_CSV_SHA256"
    bytes: 0
```

- [ ] **Step 8: Pin the fixture CSV hash**

```bash
cd ~/d/science
python - <<'PY'
import hashlib, os
p = "science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv"
b = open(p, "rb").read()
print("sha256:" + hashlib.sha256(b).hexdigest(), len(b))
PY
# paste the hash into the fixture datapackage.yaml `hash:` and the byte count into `bytes:`
```

- [ ] **Step 9: Commit**

```bash
cd ~/d/science
git add science/tests/fixtures/commons/assembly
git commit -m "feat(commons): assembly-registry reference collection + recipe + test fixture"
# Commit the real commons dataset separately in ~/d/science-commons if/when populated.
```

(The `~/d/science-commons` dataset is committed in that repo; only the in-`science` test fixture is committed here.)

---

## Task 5: Assembly registry resolver

**Files:**
- Create: `science/src/science_tool/commons/assembly.py`
- Test: `science/tests/test_commons_assembly.py`

A pure resolver over the registry rows. It reads the registry's data resource through the framework's sha256-verified `resolve()`, exposes the set of seqcol-digest keys (the `available_keys` that Task 6 feeds to Plan 1's `evaluate_key_resolution`), and resolves a label-or-digest to an entry. **Exact `seqcol_digest` equality is identity (RCM-D6);** a `label` is an advisory alias only.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_assembly.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.assembly import (
    AssemblyEntry,
    available_assembly_keys,
    load_assembly_registry,
    resolve_assembly,
)

_FIX = Path(__file__).parent / "fixtures" / "commons" / "assembly"
_COMMONS = _FIX  # entity store
_DATA = Path(__file__).parent / "fixtures" / "commons" / "assembly-data"  # data root


def _kw() -> dict:
    return {"commons_root": _COMMONS, "data_root": _DATA}


def test_load_returns_entries() -> None:
    entries = load_assembly_registry(**_kw())
    assert all(isinstance(e, AssemblyEntry) for e in entries)
    assert {e.label for e in entries} == {"GRCh38", "GRCh37"}


def test_available_keys_are_the_seqcol_digests() -> None:
    keys = available_assembly_keys(**_kw())
    assert "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp" in keys
    assert "5K4odB173rjao1Cnbk5BnvLt9V7aPAa2" in keys
    assert len(keys) == 2


def test_resolve_by_exact_digest() -> None:
    entry = resolve_assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp", **_kw())
    assert entry is not None and entry.label == "GRCh38"


def test_resolve_by_label_alias() -> None:
    entry = resolve_assembly("GRCh37", **_kw())
    assert entry is not None and entry.seqcol_digest == "5K4odB173rjao1Cnbk5BnvLt9V7aPAa2"


def test_resolve_unknown_returns_none() -> None:
    assert resolve_assembly("not-a-real-key", **_kw()) is None


# --- registry row validation (pure, no I/O) — finding 5 ---


def test_parse_rejects_duplicate_member_key() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    rows = [
        {"seqcol_digest": "DUP", "label": "A", "accession": ""},
        {"seqcol_digest": "DUP", "label": "B", "accession": ""},
    ]
    with pytest.raises(AssemblyRegistryError, match="duplicate member key"):
        _parse_registry_rows(rows)


def test_parse_rejects_blank_digest() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    with pytest.raises(AssemblyRegistryError, match="blank seqcol_digest"):
        _parse_registry_rows([{"seqcol_digest": "  ", "label": "A", "accession": ""}])


def test_parse_rejects_missing_column() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    with pytest.raises(AssemblyRegistryError, match="missing required column"):
        _parse_registry_rows([{"label": "A", "accession": ""}])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_assembly.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.assembly'`.

- [ ] **Step 3: Implement the resolver**

Create `science/src/science_tool/commons/assembly.py`:

```python
"""Resolver over the seqcol-keyed assembly registry (C-D2, second primitive instance).

Pure over pinned, sha256-verified inputs (no network): reads the registry's
data resource through the commons resolver and exposes the seqcol-digest key
set + a label/digest lookup. Exact ``seqcol_digest`` equality is identity
(RCM-D6); ``label`` is an advisory alias. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D2).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.resolver import resolve

ASSEMBLY_REGISTRY_ID = "dataset:assembly-registry"
ASSEMBLY_RESOURCE = "assemblies.csv"


class AssemblyRegistryError(ValueError):
    """A registry row violates the reference-collection contract (RCM-D1/D6)."""


@dataclass(frozen=True, slots=True)
class AssemblyEntry:
    """One registry row: the seqcol digest (member key) + advisory aliases."""

    seqcol_digest: str
    label: str
    accession: str


def _parse_registry_rows(rows: Iterable[dict[str, Any]]) -> list[AssemblyEntry]:
    """Validate + parse raw CSV rows into entries; fail early on a broken collection.

    A keyed reference collection must have a present, non-blank member key on
    every row and **unique** member keys (RCM-D6: exact equality is identity, so
    a duplicate key is two rows claiming one identity). Pure (no I/O) so it is
    unit-testable with in-memory dicts.
    """
    entries: list[AssemblyEntry] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if "seqcol_digest" not in row:
            raise AssemblyRegistryError(f"row {i}: missing required column 'seqcol_digest'")
        digest = (row.get("seqcol_digest") or "").strip()
        if not digest:
            raise AssemblyRegistryError(f"row {i}: blank seqcol_digest (member key)")
        if digest in seen:
            raise AssemblyRegistryError(f"duplicate member key seqcol_digest={digest!r}")
        seen.add(digest)
        entries.append(
            AssemblyEntry(
                seqcol_digest=digest,
                label=(row.get("label") or "").strip(),
                accession=(row.get("accession") or "").strip(),
            )
        )
    return entries


def load_assembly_registry(
    *,
    registry_id: str = ASSEMBLY_REGISTRY_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[AssemblyEntry]:
    """Load + sha256-verify the registry rows. Raises CommonsError if absent,
    AssemblyRegistryError if a row violates the collection contract."""
    resolved = resolve(registry_id, ASSEMBLY_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as fh:
        return _parse_registry_rows(csv.DictReader(fh))


def available_assembly_keys(
    *,
    registry_id: str = ASSEMBLY_REGISTRY_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> set[str]:
    """The set of seqcol-digest member keys for `registry_id` — the `available_keys`
    fed to `evaluate_key_resolution` (RCM-D2). The caller passes the registry id
    declared on the dataset; there is no hard-coded default fallback in the check."""
    return {
        e.seqcol_digest
        for e in load_assembly_registry(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    }


def resolve_assembly(
    label_or_digest: str,
    *,
    registry_id: str = ASSEMBLY_REGISTRY_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> AssemblyEntry | None:
    """Resolve a seqcol digest (exact equality, RCM-D6) or an advisory label alias."""
    entries = load_assembly_registry(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    for entry in entries:
        if entry.seqcol_digest == label_or_digest:
            return entry
    label_matches = [e for e in entries if e.label and e.label == label_or_digest]
    return label_matches[0] if len(label_matches) == 1 else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_assembly.py -v`
Expected: all PASS. (If a `DataIntegrityError` fires, the fixture CSV hash in Task 4 Step 8 was not pinned correctly — re-run the sha256 step.)

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/commons/assembly.py science/tests/test_commons_assembly.py
git commit -m "feat(commons): assembly registry resolver (seqcol exact-equality, RCM-D6)"
```

---

## Task 6: Check 1 — assembly declared & recognized

**Files:**
- Create: `science/src/science_tool/validate/checks/identity_context.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Test: `science/tests/validate/test_checks_identity_context.py`

**Depends on Plan 1's `science_tool/commons/member.py` (`evaluate_key_resolution`, `ResolutionState`).** The check reads each dataset's RAW frontmatter (the closed graph `Entity` does not surface `identity_context`), then for a coordinate-bearing dataset (`bio.rnaseq`/`bio.scrna`/`bio.cna` in its profile):
- if it declares no `identity_context.assembly` → WARN (migrate free-text `reference_genome` → structured);
- if the declared `assembly` block is malformed (not an object, blank `seqcol_digest`, missing/non-`dataset:` `registry`, or a `resolution_status` outside `{resolved, declared_unresolved}`) → ERROR `identity.assembly-malformed` (raw authored files bypass the JSON schema, so the check re-enforces these — finding 4);
- otherwise evaluate the `seqcol_digest` key against the keys of the registry **the dataset declares** (loaded per declared registry id — *no* hard-coded default, finding 1) via `evaluate_key_resolution` — UNRESOLVED → ERROR, DECLARED_UNRESOLVED → INFO, RESOLVED → pass silently, and an unloadable/unknown registry → INFO `identity.registry-unavailable` (never a false ERROR).

The core is a **pure evaluator** (`evaluate_identity_context(datasets, *, registry_keys_by_id)`) tested directly with dicts; the `@Check` wrapper loads each declared registry's keys and re-reads raw frontmatter (resolving `entity.file_path` under `ctx.project_root` so it works from any cwd — finding 2).

- [ ] **Step 1: Write the failing tests**

Create `science/tests/validate/test_checks_identity_context.py`:

```python
from __future__ import annotations

from science_tool.validate.checks.identity_context import evaluate_identity_context
from science_tool.validate.result import Severity

_REGISTRY = "dataset:assembly-registry"
_REGISTRY_KEYS = {"g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp", "5K4odB173rjao1Cnbk5BnvLt9V7aPAa2"}
_KEYS_BY_ID = {_REGISTRY: set(_REGISTRY_KEYS)}
_COORD_PROFILE = "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0"


def _ds(profile: str, **fm) -> dict:
    return {"type": "dataset", "id": "dataset:x", "schema_profile": profile, "_path": "data/x/entity.md", **fm}


def _assembly(digest: str, *, status: str = "resolved", registry: str = _REGISTRY) -> dict:
    return {"seqcol_digest": digest, "registry": registry, "resolution_status": status}


def test_resolved_assembly_passes_silently() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp")})
    # RESOLVED is silent: no WARN/ERROR/INFO at all.
    assert list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID)) == []


def test_unresolved_assembly_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("NOT_IN_REGISTRY")})
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule == "identity.assembly-unresolved"


def test_declared_unresolved_assembly_infos() -> None:
    ds = _ds(
        "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0",
        identity_context={"taxon": 9606, "assembly": _assembly("WHATEVER", status="declared_unresolved")},
    )
    results = list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert [r for r in results if r.rule == "identity.assembly-declared-unresolved"]


def test_freetext_reference_genome_without_identity_context_warns() -> None:
    ds = _ds("science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0", reference_genome="GRCh38")
    warns = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.WARN]
    assert len(warns) == 1
    assert warns[0].rule == "identity.assembly-undeclared"


def test_non_coordinate_dataset_ignored() -> None:
    ds = _ds("science-entity-base/1.0+dataset/1.0+bio.table/1.0")
    assert list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID)) == []


# --- finding 1: keys are looked up by the DECLARED registry, never a default ---


def test_foreign_registry_is_not_validated_against_default() -> None:
    # The digest IS a default-registry key, but the dataset declares a different
    # registry. It must NOT silently validate against the default's keys.
    ds = _ds(
        _COORD_PROFILE,
        identity_context={
            "taxon": 9606,
            "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp", registry="dataset:not-assembly-registry"),
        },
    )
    results = list(evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert not [r for r in results if r.rule == "identity.assembly-declared-unresolved"]
    assert [r for r in results if r.rule == "identity.registry-unavailable"]


def test_registry_unavailable_cannot_falsely_error() -> None:
    # The declared registry maps to None (attempted but not loadable): a declared
    # resolved digest is reported INFO (unverifiable), never ERROR.
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp")})
    results = list(evaluate_identity_context([ds], registry_keys_by_id={_REGISTRY: None}))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert [r for r in results if r.rule == "identity.registry-unavailable"]


# --- finding 4: raw authored files bypass the JSON schema, so check 1 must
# itself enforce the schema-critical assembly fields ---


def test_malformed_assembly_not_a_dict_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": "GRCh38"})
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_missing_seqcol_digest_errors() -> None:
    ds = _ds(
        _COORD_PROFILE,
        identity_context={"taxon": 9606, "assembly": {"registry": _REGISTRY, "resolution_status": "resolved"}},
    )
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_missing_registry_errors() -> None:
    ds = _ds(
        _COORD_PROFILE,
        identity_context={"taxon": 9606, "assembly": {"seqcol_digest": "X", "resolution_status": "resolved"}},
    )
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"


def test_bad_resolution_status_errors() -> None:
    ds = _ds(_COORD_PROFILE, identity_context={"taxon": 9606, "assembly": _assembly("X", status="maybe")})
    errors = [r for r in evaluate_identity_context([ds], registry_keys_by_id=_KEYS_BY_ID) if r.severity is Severity.ERROR]
    assert len(errors) == 1 and errors[0].rule == "identity.assembly-malformed"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.validate.checks.identity_context'`.

- [ ] **Step 3: Implement the check module (check 1 + the raw-frontmatter helper + the pure evaluator)**

Create `science/src/science_tool/validate/checks/identity_context.py`:

```python
"""Assembly-identity checks (Pillar C, §5 checks 1 & 3; C1 detect-only, exact-equality).

Reads RAW frontmatter (the closed graph Entity does not surface extension
fields) and resolves declared assembly seqcol digests against the assembly
registry via the Plan 1 substrate `evaluate_key_resolution` (RCM-D2 guardrail 1,
exact-equality RCM-D6). Check 3 (cross-dataset assembly mismatch) is added in a
later task in this same module. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.assembly import AssemblyRegistryError, available_assembly_keys
from science_tool.commons.errors import CommonsError
from science_tool.commons.member import ResolutionState, evaluate_key_resolution
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# bio extensions whose data are assembly-anchored (coordinate-bearing).
_COORDINATE_EXTENSIONS = ("bio.rnaseq", "bio.scrna", "bio.cna")


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _raw_frontmatter(path: Path) -> dict[str, Any]:
    """Raw frontmatter for either an entity.md (fenced YAML) or a datapackage.yaml."""
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
    elif text.startswith("---"):
        end = text.find("\n---", 3)
        data = yaml.safe_load(text[3:end]) if end != -1 else {}
    else:
        data = {}
    return data if isinstance(data, dict) else {}


def _is_coordinate_bearing(profile: str) -> bool:
    return any(f"+{ext}/" in f"+{profile}" for ext in _COORDINATE_EXTENSIONS)


def _assembly_defect(assembly: Any) -> str | None:
    """Return a defect message if the raw assembly block is malformed, else None.

    The graph Entity is closed and local authored frontmatter can bypass the
    JSON schema, so the schema-critical fields are re-enforced here (finding 4).
    """
    if not isinstance(assembly, dict):
        return "not an object"
    digest = assembly.get("seqcol_digest")
    if not isinstance(digest, str) or not digest.strip():
        return "missing or blank seqcol_digest"
    registry = assembly.get("registry")
    if not isinstance(registry, str) or not registry.startswith("dataset:"):
        return "missing or malformed registry (must be a dataset: reference)"
    if assembly.get("resolution_status") not in ("resolved", "declared_unresolved"):
        return "resolution_status must be 'resolved' or 'declared_unresolved'"
    return None


def evaluate_identity_context(
    datasets: Iterable[dict[str, Any]], *, registry_keys_by_id: dict[str, set[str] | None]
) -> Iterator[Result]:
    """Pure core of check 1. `datasets` are raw frontmatter dicts (with `_path`).

    `registry_keys_by_id` maps each declared registry id to its seqcol-digest key
    set, or to None when that registry was attempted but could not be loaded.
    Keys are looked up by the registry the dataset *declares* — never a hard-coded
    default — so naming a foreign/unknown registry cannot silently validate
    against the canonical one (finding 1). An unloadable/unknown registry yields
    an INFO (unverifiable), never a false ERROR (missing infra must not error).
    """
    reported_registries: set[str] = set()
    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        if not _is_coordinate_bearing(str(fm.get("schema_profile") or "")):
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        idc = fm.get("identity_context") or {}
        assembly = idc.get("assembly") if isinstance(idc, dict) else None

        if assembly is None:
            has_freetext = bool(fm.get("reference_genome"))
            detail = (
                "free-text reference_genome is set but identity_context.assembly is not; "
                "migrate to a structured seqcol_digest declaration"
                if has_freetext
                else "coordinate-bearing dataset does not declare identity_context.assembly"
            )
            yield _result(Severity.WARN, path, f"{ident}: {detail}", "identity.assembly-undeclared")
            continue

        defect = _assembly_defect(assembly)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: malformed identity_context.assembly — {defect}",
                "identity.assembly-malformed",
            )
            continue

        digest = str(assembly["seqcol_digest"])
        registry_id = str(assembly["registry"])
        status = assembly["resolution_status"]

        known = registry_id in registry_keys_by_id and registry_keys_by_id[registry_id] is not None
        available = registry_keys_by_id[registry_id] if known else None
        state = evaluate_key_resolution(key=digest, available_keys=available, declared_status=status)
        if state is ResolutionState.UNRESOLVED:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: assembly seqcol_digest {digest!r} does not resolve in {registry_id!r}",
                "identity.assembly-unresolved",
            )
        elif state is ResolutionState.DECLARED_UNRESOLVED:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: assembly seqcol_digest declared_unresolved (honoured, RCM-D2)",
                "identity.assembly-declared-unresolved",
            )
        elif state is ResolutionState.UNKNOWN and not known and registry_id not in reported_registries:
            reported_registries.add(registry_id)
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: registry {registry_id!r} unavailable; declared seqcol digest cannot be verified",
                "identity.registry-unavailable",
            )
        # RESOLVED passes silently.


def _dataset_frontmatters(ctx: ValidateContext) -> list[dict[str, Any]]:
    """Raw frontmatter for every dataset entity, re-reading file_path under project_root.

    `entity.file_path` is project-relative; resolve it against `ctx.project_root`
    so the check works when `science validate` is run from another cwd (finding 2).
    """
    sources = load_project_sources(ctx.project_root, include_commons=False)
    out: list[dict[str, Any]] = []
    for entity in sources.entities:
        if getattr(entity, "kind", None) != "dataset":
            continue
        rel = Path(getattr(entity, "file_path", ""))
        abs_path = rel if rel.is_absolute() else ctx.project_root / rel
        if not abs_path.is_file():
            continue
        fm = _raw_frontmatter(abs_path)
        fm.setdefault("type", "dataset")
        if not fm.get("id"):
            fm["id"] = getattr(entity, "canonical_id", "?")
        fm["_path"] = str(rel)
        out.append(fm)
    return out


@Check(section="assembly identity", order=25)
def check_identity_context_assembly(ctx: ValidateContext) -> Iterator[Result]:
    datasets = _dataset_frontmatters(ctx)
    # Load keys for each registry actually declared (no default fallback): a
    # dataset's digest is verified only against the registry it names (finding 1).
    declared_registries: set[str] = set()
    for fm in datasets:
        idc = fm.get("identity_context") or {}
        assembly = idc.get("assembly") if isinstance(idc, dict) else None
        if isinstance(assembly, dict) and isinstance(assembly.get("registry"), str):
            declared_registries.add(assembly["registry"])
    registry_keys_by_id: dict[str, set[str] | None] = {}
    for registry_id in declared_registries:
        try:
            registry_keys_by_id[registry_id] = available_assembly_keys(registry_id=registry_id)
        except (CommonsError, AssemblyRegistryError):
            registry_keys_by_id[registry_id] = None
    yield from evaluate_identity_context(datasets, registry_keys_by_id=registry_keys_by_id)
```

- [ ] **Step 4: Register the check**

In `science/src/science_tool/validate/checks/__init__.py`, add `"identity_context"` to the tuple in `_load_canonical_checks()`, after Plan 1's `"reference_collections"`:

```python
        "reference_collections",
        "identity_context",
        "prose_lints",
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_context.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/identity_context.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_identity_context.py
git commit -m "feat(validate): check 1 — assembly declared & recognized (RCM-D2, consumes Plan 1)"
```

---

## Task 7: Check 3 — cross-dataset assembly mismatch (detect-only)

**Files:**
- Modify: `science/src/science_tool/validate/checks/identity_context.py`
- Test: `science/tests/validate/test_checks_identity_context.py`

A derived dataset whose declared inputs span **distinct** seqcol digests, with no liftover available (there is none in C1), is flagged WARN — **detect-only**; the remedy (liftover) is C4 (§5 check 3). Scope for C1: compare the assemblies declared by the dataset and the **project-local** inputs it can see. Pure evaluator over a `{id: frontmatter}` map.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/validate/test_checks_identity_context.py`:

```python
from science_tool.validate.checks.identity_context import evaluate_cross_dataset_assembly


def _with_assembly(id_: str, digest: str, **extra) -> dict:
    return {
        "id": id_,
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.identity_context/1.0",
        "_path": f"data/{id_.split(':')[-1]}/entity.md",
        "identity_context": {"taxon": 9606, "assembly": {"seqcol_digest": digest, "resolution_status": "resolved"}},
        **extra,
    }


def test_inputs_spanning_two_assemblies_warns() -> None:
    a = _with_assembly("dataset:a", "DIGEST_38")
    b = _with_assembly("dataset:b", "DIGEST_37")
    derived = _with_assembly(
        "dataset:c", "DIGEST_38",
        derivation={"inputs": ["dataset:a", "dataset:b"]},
    )
    warns = [
        r
        for r in evaluate_cross_dataset_assembly([a, b, derived])
        if r.rule == "identity.cross-dataset-assembly-mismatch"
    ]
    assert len(warns) == 1


def test_inputs_single_assembly_no_warn() -> None:
    a = _with_assembly("dataset:a", "DIGEST_38")
    derived = _with_assembly("dataset:c", "DIGEST_38", derivation={"inputs": ["dataset:a"]})
    assert list(evaluate_cross_dataset_assembly([a, derived])) == []


def test_no_derivation_inputs_no_warn() -> None:
    a = _with_assembly("dataset:a", "DIGEST_38")
    assert list(evaluate_cross_dataset_assembly([a])) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_context.py -k cross_dataset -v`
Expected: FAIL with `ImportError: cannot import name 'evaluate_cross_dataset_assembly'`.

- [ ] **Step 3: Implement check 3**

Append to `science/src/science_tool/validate/checks/identity_context.py`:

```python
def _declared_digest(fm: dict[str, Any]) -> str | None:
    idc = fm.get("identity_context") or {}
    assembly = idc.get("assembly") if isinstance(idc, dict) else None
    if isinstance(assembly, dict) and assembly.get("seqcol_digest"):
        return str(assembly["seqcol_digest"])
    return None


def evaluate_cross_dataset_assembly(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Pure core of check 3: flag a derived dataset whose inputs span assemblies.

    Detect-only for C1 — the liftover remedy lands in C4 (§5 check 3).
    """
    by_id = {fm.get("id"): fm for fm in datasets if fm.get("id")}
    for fm in datasets:
        derivation = fm.get("derivation") or {}
        inputs = derivation.get("inputs") if isinstance(derivation, dict) else None
        if not inputs:
            continue
        digests: set[str] = set()
        own = _declared_digest(fm)
        if own:
            digests.add(own)
        for input_id in inputs:
            parent = by_id.get(input_id)
            if parent is None:
                continue  # not project-local; C1 scope is project-local inputs
            parent_digest = _declared_digest(parent)
            if parent_digest:
                digests.add(parent_digest)
        if len(digests) >= 2:
            yield _result(
                Severity.WARN,
                fm.get("_path"),
                f"{fm.get('id', '?')}: derivation inputs span distinct assemblies {sorted(digests)} "
                f"with no liftover available (detect-only; remedy in C4)",
                "identity.cross-dataset-assembly-mismatch",
            )


@Check(section="assembly identity", order=26)
def check_cross_dataset_assembly(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_cross_dataset_assembly(_dataset_frontmatters(ctx))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_context.py -v`
Expected: all PASS (check 1 + check 3 tests).

- [ ] **Step 5: Run the full validate suite (confirm registration is clean)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate -q`
Expected: PASS. (If `test_checks_basic.py` asserts an exact check inventory, add `identity.*` rules / the two new check functions to that inventory.)

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/identity_context.py science/tests/validate/test_checks_identity_context.py
git commit -m "feat(validate): check 3 — cross-dataset assembly mismatch (detect-only, C1)"
```

---

## Task 8: Migration note, lint, and final C1 verification

**Files:**
- Create: `docs/usage/assembly-identity.md` (or the nearest existing usage/how-to dir — if none, place under `docs/`)

The migration is light: **zero datasets currently carry `reference_genome`** (verified), so there is no data rewrite. Free-text `reference_genome` stays valid in the bio schemas but is now flagged by check 1 (`identity.assembly-undeclared`); the structured replacement is `identity_context.assembly`. Document the path; the WARN→ERROR promotion is deferred (post-C1).

- [ ] **Step 1: Write the migration note**

Create `docs/usage/assembly-identity.md`:

```markdown
# Declaring assembly identity (C1)

A coordinate-bearing dataset (`bio.rnaseq` / `bio.scrna` / `bio.cna`) declares
its assembly via the `bio.identity_context/1.0` extension instead of the
free-text `reference_genome` field.

Add `+bio.identity_context/1.0` to the dataset's `schema_profile` and:

```yaml
identity_context:
  taxon: 9606
  molecular_ids:
    gene: {namespace: hgnc, canonical: true}   # gene resolution lands in C2
  assembly:
    seqcol_digest: <SQ-collection-digest>       # canonical key (C-D2)
    label: GRCh38                               # advisory alias
    registry: dataset:assembly-registry
    resolution_status: resolved                 # or declared_unresolved (RCM-D2)
```

`seqcol_digest` must resolve in `dataset:assembly-registry` (exact equality,
RCM-D6) or carry `resolution_status: declared_unresolved`. Free-text
`reference_genome` is deprecated: `science validate` warns
(`identity.assembly-undeclared`) until migrated. Cross-assembly joins are
detected (`identity.cross-dataset-assembly-mismatch`); the liftover remedy
arrives in C4.
```

(If the repo already has a usage/how-to directory, place the file there and match its index conventions instead of creating `docs/usage/`.)

- [ ] **Step 2: Ruff lint + format both packages**

```bash
cd ~/d/science/science && uv run --frozen ruff check . && uv run --frozen ruff format --check .
cd ~/d/science/science/model && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: clean. If `ruff format --check` reports diffs in files you created, run `uv run --frozen ruff format <file>` and re-commit.

- [ ] **Step 3: Full test sweep of both packages**

```bash
cd ~/d/science/science/model && uv run --frozen pytest -q
cd ~/d/science/science && uv run --frozen pytest -q
```
Expected: PASS in both (the `refget`-gated recipe test SKIPs if `refget` is absent — install it in the run env to exercise it).

- [ ] **Step 4: Smoke-test `science validate` on a real project**

Run: `cd ~/d/science && uv run --frozen science validate --verbose` against a project with a dataset (or confirm via the suite). Expected: the two new checks run under section "assembly identity" without raising, and a free-text `reference_genome` dataset (if any) surfaces `identity.assembly-undeclared`.

- [ ] **Step 5: Final commit**

```bash
cd ~/d/science
git add docs/usage/assembly-identity.md
git commit -m "docs(bio): assembly-identity migration note (free-text reference_genome -> identity_context)"

# If ruff reformatted any C1 files, review and stage them explicitly — never `git add -A`
# (it could sweep unrelated working-tree changes into the commit).
git status --short
git add \
  science/src/science_tool/commons/assembly.py \
  science/src/science_tool/commons/assembly_registry_build.py \
  science/src/science_tool/validate/checks/identity_context.py \
  science/tests/test_assembly_registry_build.py \
  science/tests/test_commons_assembly.py \
  science/tests/validate/test_checks_identity_context.py
git commit -m "chore(c1): ruff format C1 modules" || echo "nothing to commit"
```

---

## Self-Review (completed by plan author)

**Spec coverage** (against C design §8 C1 + §5 checks 1 & 3, and the primitive's RCM-D2/D5/D6):
- *`bio.identity_context` container + inline `seqcol_digest` declaration with `resolution_status`* → Task 1 (schema, `resolution_status` required when assembly present) ✓
- *Assembly registry, seqcol-keyed, as a reference collection (second primitive instance)* → Task 2 (collection extension `member_key_column: seqcol_digest`) + Task 4 (commons dataset + recipe + fixture) ✓
- *No-FASTA build (pinned digest table)* → Task 3 (`refget` seqcol digest over names+sequences; recompute-and-assert integrity gate; seqcolapi level-2 fetch) ✓
- *Exact-equality resolution (RCM-D6), `available_keys` for the assembly instance* → Task 5 (resolver; `available_assembly_keys(registry_id=…)`; `_parse_registry_rows` rejects blank/missing/duplicate keys — finding 5) feeding Task 6 ✓
- *Check 1 — assembly declared & recognized* → Task 6, **consuming Plan 1's `evaluate_key_resolution`**: keys looked up by the **declared** registry, no default fallback (finding 1); malformed assembly fields re-enforced on raw frontmatter (finding 4); UNRESOLVED→ERROR, DECLARED_UNRESOLVED→INFO, RESOLVED→silent, unloadable/unknown registry→INFO (not ERROR) ✓
- *Check 3 — cross-dataset assembly mismatch, detect-only* → Task 7 ✓
- *Free-text `reference_genome` → structured migration* → Task 6 WARN + Task 8 note (no data rewrite: zero datasets carry it today) ✓

**Type consistency:** `compute_seqcol_digest(level2)` (inherent payload only, explicit `inherent_attrs`), `build_registry_row(*, level2, label, accession, server_digest, source_url)`, `fetch_seqcol_level2(digest, *, base_url)`; `AssemblyEntry(seqcol_digest, label, accession)`, `AssemblyRegistryError`, `_parse_registry_rows(rows)`, `load_assembly_registry(*, registry_id, commons_root, data_root)`, `available_assembly_keys(*, registry_id, commons_root, data_root)`, `resolve_assembly(label_or_digest, *, registry_id, commons_root, data_root)`, `ASSEMBLY_REGISTRY_ID`, `ASSEMBLY_RESOURCE`; `evaluate_identity_context(datasets, *, registry_keys_by_id)`, `_assembly_defect(assembly)`, `evaluate_cross_dataset_assembly(datasets)`, `_raw_frontmatter`, `_dataset_frontmatters` (resolves `file_path` under `project_root` — finding 2), `_declared_digest` — used identically across tasks. Check rules: `identity.assembly-undeclared`, `identity.assembly-malformed`, `identity.assembly-unresolved`, `identity.assembly-declared-unresolved`, `identity.registry-unavailable`, `identity.cross-dataset-assembly-mismatch`.

**Two design→implementation reconciliations (deliberate, documented in-plan):** (a) `bio.identity_context` is a **sibling extension added to the profile**, not a cross-extension `$ref` (framework composes via `allOf` over profile components, no cross-file refs); presence on coordinate-bearing datasets is enforced by check 1 (the validate surface, per §5), not by JSON schema. (b) Checks read **raw frontmatter** (`_raw_frontmatter` over `entity.file_path`), because the graph `Entity` is closed and drops extension fields. Both honor the design's intent (one shared declaration; checks enforce presence) within the framework as built.

**Cross-plan dependency (now an explicit prerequisite):** Plan 1's Task-4 reference-collection check reads `getattr(entity, "derivation")` off the closed graph `Entity`, whose typed `DerivationBlock` has no `kind`/`member_key`; that check will silently no-op on `member_of` datasets and needs the same raw-frontmatter correction before it is load-bearing. This is captured as the **Prerequisite (before Task 6)** section above, not only here. Plan 1's *pure* helpers (`evaluate_key_resolution`, `parse_member_of`) are dict-based and are consumed correctly.

**Out of scope (per C phasing):** gene/protein/variant tiers (C2/C3/C4), liftover + seqcol compatibility relations (C4), the WARN→ERROR promotion of free-text `reference_genome`, and any non-molecular identity (cell line, disease, ontology — later pillar). Populating the *real* GRCh38/GRCh37 registry rows is an operator-run recipe step (network); the plan's acceptance gate is the hermetic fixture + green tests.

---

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task with two-stage review between tasks (REQUIRED SUB-SKILL: superpowers:subagent-driven-development). **Honor the Prerequisite above before Task 6**: Plan 1's `science_tool/commons/member.py` must be present *and* its Task-4 check made raw-frontmatter-based.
2. **Inline Execution** — execute tasks in this session with checkpoints (REQUIRED SUB-SKILL: superpowers:executing-plans).
