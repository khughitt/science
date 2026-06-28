# C3 Protein Crosswalk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Pillar C sub-phase **C3 — protein identity**: a pinned UniProtKB (reviewed Swiss-Prot, human) protein crosswalk as a reference collection keyed by an opaque composite `protein_key`, a pure provenance-carrying resolver (`to_canonical`) that surfaces isoform→canonical and merged-accession relations without collapsing them and carries a protein→gene (`gene_key`) join pointer, and a declaration-level `science validate` protein check — implemented by **generalizing** C2's gene check into a shared `evaluate_tier_identity` helper that both tiers use.

**Architecture:** Three layers, mirroring C2, with one simplification: **no `identity_context` schema change is needed** — C2 already added `registry` + `resolution_status` to the *generic* `molecular_ids.<tier>` sub-schema, so `molecular_ids.protein` already validates. (1) **science-model**: a minimal `bio.protein_crosswalk/1.0` collection extension (`member_key_column: protein_key`). (2) **commons data**: the `dataset:protein-crosswalk-uniprot` reference collection (entity + datapackage) and a no-network-at-resolve recipe that fetches pinned, dated reviewed-human UniProt release files (idmapping + secondary accessions) and builds `crosswalk.csv`. (3) **science-tool**: pure UniProt parsing helpers, a pure resolver over the crosswalk rows (`to_canonical` returning a discriminated `ResolvedProteinMatch | AmbiguousProteinMatch | None`), and the C2 gene check refactored into a tier-parameterized `evaluate_tier_identity` with a protein check (`order=28`) added. Implements C-D1 (UniProtKB accession anchor; Ensembl-protein / RefSeq-protein / entry-name inputs; isoforms a non-collapsed lower-level identity, decision d5) and §8 sub-phase C3 of `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md`; the crosswalk is the **fourth instance** of the foundation primitive (`docs/plans/historical/2026-05-26-reference-collection-member-promotion-design.md`), after gene-sets (D), the assembly registry (C1), and the gene crosswalk (C2).

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, `pytest`, `uv` (`uv run --frozen`), the `science-model` and `science` (`science_tool`) packages, `httpx` (already a science-tool dep, build-time fetch only), `pyyaml` (recipe). No new pinned dependency (UniProt release files are plain TSV; parsing is stdlib `csv`). All repo paths are relative to `~/d/science`; the commons lives at `~/d/science-commons`.

---

## Background the implementer must read first

- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C. **C-D1** (protein canonical = **UniProtKB accession**, Swiss-Prot canonical; accepted inputs Ensembl protein/transcript, RefSeq protein, Entrez; **isoform accessions `P12345-2` are a valid lower-level identity, NOT collapsed** to the canonical — decision d5). **C-D3** (protein crosswalk = UniProt per-release `idmapping`, human; a commons `reference` dataset with a recipe + hash-verified artifact; dated/immutable handles, `latest` discovery-only). **§6** (UniProt/AlphaFold → "protein identity + protein↔gene"). **§8** locks C3 = protein crosswalk.
- `docs/plans/historical/2026-05-26-reference-collection-member-promotion-design.md` — the primitive. RCM-D1 (collection = a `dataset` with a mechanism-specific key column), RCM-D2 (resolve-or-`declared_unresolved`), RCM-D6 (**exact key equality is identity; an isoform/merged relation relates two *distinct* identities with provenance — never a key collapse**). The protein crosswalk is the **fourth instance**; its `member_of` promotion (a protein promoted to its own `dataset`) is inherited but **unused in C3 v1** (no evidence-bearing protein yet).
- `docs/plans/2026-05-27-c2-gene-crosswalk-plan.md` — **C2 (the sibling this plan mirrors)**, already merged. It shipped `bio.gene_crosswalk/1.0`, `commons/gene_crosswalk.py` (the resolver template), `commons/gene_crosswalk_build.py` (the build-helper template), and the gene check in `validate/checks/identity_context.py` (the check this plan **generalizes**). Read `science/src/science_tool/commons/gene_crosswalk.py` and the gene section of `science/src/science_tool/validate/checks/identity_context.py` before writing — C3's resolver and check follow their exact shape and idioms.

### Brainstorm decisions locked for this plan (do not relitigate)

1. **Isoform inputs are surfaced, never collapsed (decision d5).** A `uniprot` input with a `-N` suffix (`P12345-2`) strips to its canonical accession, resolves to the canonical member row, and returns `match_type="isoform"` with the queried isoform accession preserved in the `isoform` field. Both the isoform accession and the canonical `protein_key`/`gene_key` are surfaced; the result never silently equates the isoform with the canonical. Isoforms are **not** their own member rows in v1. (Mirrors C2's "surface, don't collapse" for merged ids.)
2. **v1 source = reviewed Swiss-Prot, human only.** ~20k canonical proteins — the canonical proteome. TrEMBL (unreviewed) is a later increment. Canonical identity = the Swiss-Prot accession.
3. **Lifecycle = merged (secondary accessions), surfaced with provenance.** A UniProt secondary accession is its own member row with `status: merged` + `replacement_protein_key` → the primary, surfaced never auto-followed (the C2 merged pattern). No `split` status for proteins. (Deleted accessions → `withdrawn` is a deferrable later add.)
4. **Each protein row carries the C2 `gene_key` (protein→gene join pointer).** Populated from UniProt's HGNC cross-reference via `make_gene_key`. Carried as a join pointer only — **no runtime cross-validation against C2** (mirrors C2's "surface, don't follow"); possibly-empty (no HGNC mapping) or rarely multi-valued.
5. **Member key = an opaque composite `"<taxon>|uniprot|<accession>"`** (e.g. `9606|uniprot|P04217`), constructed only by `make_protein_key`. The `|` field delimiter never collides with a UniProt accession (accessions are `[A-Z0-9]` only). The key is **opaque** — byte-equality is identity (RCM-D6) and nothing downstream splits it (the resolver gates on a `taxon` parameter / `_HUMAN_TAXON`, never by parsing the key). Multi-value columns use `;` within a cell.
6. **The resolver returns a discriminated result**: `ResolvedProteinMatch | AmbiguousProteinMatch | None`. `AmbiguousProteinMatch` carries `candidates` (≥2) and **has no `protein_key`** (e.g. a RefSeq/Ensembl-protein id mapping to >1 UniProt). `None` = genuinely not found.
7. **Supported input namespaces = `{uniprot, uniprot_entry_name, ensembl_protein, refseq_protein}`.** Entrez **gene** id is deliberately excluded — it is gene-space and one-to-many over proteins; the reverse (protein→gene) is the `gene_key` column.
8. **The check is declaration-level only and is implemented by generalizing C2's gene check.** Extract `evaluate_tier_identity` parameterized by a `_TierSpec`; rewrite C2's `evaluate_gene_identity` as a thin wrapper (its tests are the refactor guard); add a protein wrapper + `check_protein_identity` (`order=28`). Same ordering (malformed → namespace-unsupported → declared_unresolved → registry-unavailable(INFO)/registry-invalid(ERROR)) and the same raw-frontmatter `_tier_defect` re-enforcement. Payload-level resolution stays out of `science validate` (the resolver contract is where lifecycle map-through lives).

### Two grounding facts (verified against the codebase; carried from C1/C2)

1. **The graph `Entity` is a closed pydantic model** that drops extension fields, so the check reads **raw frontmatter**. The check module `identity_context.py` already gathers it via **tolerant `DatapackageAdapter().discover(ctx.project_root)`** in `_dataset_frontmatters` (NOT `load_project_sources`, which strict-validates and can crash the run). The generalized check **reuses** `_dataset_frontmatters`, `_raw_frontmatter`, `_load_registry_meta`, and the `_result` helper already in that module.
2. **Profile composition is `allOf` over profile-string components; there is no cross-file `$ref`.** `_filename_for` is `name.replace(".", "-")`, so `bio.protein_crosswalk` → `extension-bio-protein_crosswalk-1.0.json` (underscore preserved). The `science-entity-base` `schema_profile` pattern already permits `_` in component names (widened in C1) — **no base-schema change is needed**.

### Codebase anchors (read before writing code)

- Schemas dir: `science/model/src/science_model/schemas/` — `extension-bio-gene_crosswalk-1.0.json` is the minimal-collection template. Model test template: `science/model/tests/test_bio_extension_gene_crosswalk.py`.
- Data resolver: `science/src/science_tool/commons/resolver.py::resolve(dataset_id, logical_path, *, commons_root=None, data_root=None) -> ResolvedDataResource` (sha256-verified `.path`; data lives at `<data_root>/<slug>/<logical_path>`; slug derives from the `dataset:<slug>` id). Errors subclass `CommonsError`.
- Resolver template: `science/src/science_tool/commons/gene_crosswalk.py` (`CrosswalkRow`, `_parse_crosswalk_rows` with blank/dup/missing-column + status↔replacement-count guards, `load_*`, `available_*_keys`, `to_canonical`, `make_gene_key`, `_split_multi`). Build template: `science/src/science_tool/commons/gene_crosswalk_build.py`.
- Check module to EXTEND/GENERALIZE: `science/src/science_tool/validate/checks/identity_context.py` — the C2 gene section is `# --- C2: gene identity ...` through `check_gene_identity` (≈ lines 246–420). `identity_context` is **already registered** in `_load_canonical_checks()` (no `__init__.py` change needed). Reuses `_dataset_frontmatters(ctx)`, `_raw_frontmatter(path)`, `_result(severity, path, message, rule)`, `Severity{ERROR,WARN,INFO}`, the `@Check(section=, order=)` decorator, `ValidateContext`.
- In-use check `order=` values: 0–14, 16–28 (15 is the only gap). Duplicate orders are an established pattern. `test_checks_basic.py` asserts only the first 6 checks, so **order=28 for the protein check is safe and needs no inventory update**. C1 took 25 & 26 in this module; C2 took 27.
- Commons exemplar: `~/d/science-commons/datasets/gene-crosswalk-hgnc/` (entity + datapackage + `recipe/`), created by C2 — copy its structure. C2's hermetic fixture under `science/tests/fixtures/commons/gene-crosswalk{,-data}/` is the layout template.

### Task dependency order

Tasks are numbered in dependency order; execute (or dispatch) them in order:
- **1** (schema) is independent.
- **2** (commons dataset + fixture) needs Task 1's schema (the entity validates against `bio.protein_crosswalk`).
- **3** (resolver) needs Task 2's fixture (its tests read the fixture `crosswalk.csv`).
- **4** (build helpers) needs Task 3's resolver module (it imports `make_protein_key`, `_parse_crosswalk_rows`) and C2's `gene_crosswalk.make_gene_key` (for the `gene_key` column).
- **5** (check generalization + protein check) needs Task 3 (the resolver constants `PROTEIN_CROSSWALK_ID`, `MEMBER_KEY_COLUMN`, `SUPPORTED_PROTEIN_NAMESPACES`).
- **6** (migration + verification) is last.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `science/model/src/science_model/schemas/extension-bio-protein_crosswalk-1.0.json` | Create | Minimal collection extension: `member_key_column: protein_key`, optional `protein_count`. |
| `science/model/tests/test_bio_extension_protein_crosswalk.py` | Create | Schema tests for `bio.protein_crosswalk`. |
| `~/d/science-commons/datasets/protein-crosswalk-uniprot/entity.md` | Create | The reference-collection dataset entity (unbuilt: `protein_count: 0`). |
| `~/d/science-commons/datasets/protein-crosswalk-uniprot/datapackage.yaml` | Create | The `crosswalk.csv` resource + sha256 (placeholder until built). |
| `~/d/science-commons/datasets/protein-crosswalk-uniprot/recipe/{build.py,sources.yaml,README.md}` | Create | Operator-run recipe: fetch pinned UniProt files, build `crosswalk.csv`. |
| `science/tests/fixtures/commons/protein-crosswalk/datasets/protein-crosswalk-uniprot/{entity.md,datapackage.yaml}` | Create | Hermetic fixture entity store (4-row crosswalk). |
| `science/tests/fixtures/commons/protein-crosswalk-data/protein-crosswalk-uniprot/crosswalk.csv` | Create | Hermetic fixture data file + sha256. |
| `science/src/science_tool/commons/protein_crosswalk.py` | Create | Pure resolver: `CrosswalkRow`, `ResolvedProteinMatch`, `AmbiguousProteinMatch`, `load_protein_crosswalk`, `available_protein_keys`, `to_canonical`, `make_protein_key`; constants. |
| `science/tests/test_commons_protein_crosswalk.py` | Create | Resolver tests against a hermetic fixture crosswalk. |
| `science/src/science_tool/commons/protein_crosswalk_build.py` | Create | Pure UniProt parsing (`parse_idmapping`, `parse_secondary`, `build_rows`) + build-time `fetch_text`. |
| `science/tests/test_protein_crosswalk_build.py` | Create | Parsing tests (in-memory TSV; idmapping grouping; secondary→merged; round-trip). |
| `science/src/science_tool/validate/checks/identity_context.py` | Modify | Generalize the C2 gene check into `evaluate_tier_identity`; add protein check (`order=28`). |
| `science/tests/validate/test_checks_identity_context.py` | Modify | Add protein-tier tests; keep all C2 gene tests green (refactor guard). |
| `docs/migration/2026-05-27-protein-crosswalk-identity.md` | Create | How to declare protein identity; the resolver entry point. |

---

## Task 1: `bio.protein_crosswalk/1.0` collection extension schema

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-protein_crosswalk-1.0.json`
- Test: `science/model/tests/test_bio_extension_protein_crosswalk.py`

The protein crosswalk is the collection dataset (fourth primitive instance). Its only extension-specific facts: the member-key column is `protein_key` (a `const`) and an optional `protein_count`. Mirrors `bio.gene_crosswalk`.

- [ ] **Step 1: Write the failing tests**

Create `science/model/tests/test_bio_extension_protein_crosswalk.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_crosswalk_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.protein_crosswalk/1.0",
        "id": "dataset:protein-crosswalk-uniprot",
        "type": "dataset",
        "title": "UniProt protein crosswalk (protein_key-keyed reference collection)",
        "version": "1.0.0",
        "created": "2026-05-27",
        "updated": "2026-05-27",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "member_key_column": "protein_key",
        "protein_count": 4,
    }


def test_loader_resolves_protein_crosswalk_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.protein_crosswalk", version="1.0"))
    assert schema["$id"].endswith("extension-bio-protein_crosswalk-1.0.json")


def test_minimal_valid_crosswalk_passes(base_crosswalk_entity: dict) -> None:
    EntityValidator().validate(base_crosswalk_entity)


def test_member_key_column_required(base_crosswalk_entity: dict) -> None:
    del base_crosswalk_entity["member_key_column"]
    with pytest.raises(EntityValidationError, match="member_key_column"):
        EntityValidator().validate(base_crosswalk_entity)


def test_member_key_column_must_be_protein_key(base_crosswalk_entity: dict) -> None:
    base_crosswalk_entity["member_key_column"] = "uniprot_accession"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_crosswalk_entity)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_protein_crosswalk.py -v`
Expected: FAIL (schema file missing).

- [ ] **Step 3: Create the schema**

Create `science/model/src/science_model/schemas/extension-bio-protein_crosswalk-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-protein_crosswalk-1.0.json",
  "title": "science entity bio.protein_crosswalk extension",
  "type": "object",
  "required": ["member_key_column"],
  "properties": {
    "member_key_column": {"const": "protein_key"},
    "protein_count": {"type": "integer", "minimum": 0}
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science/model && uv run --frozen pytest tests/test_bio_extension_protein_crosswalk.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/schemas/extension-bio-protein_crosswalk-1.0.json science/model/tests/test_bio_extension_protein_crosswalk.py
git commit -m "feat(bio): bio.protein_crosswalk/1.0 collection extension (protein_key-keyed)"
```

---

## Task 2: Protein crosswalk commons dataset + recipe + hermetic fixture

**Files:**
- Create: `~/d/science-commons/datasets/protein-crosswalk-uniprot/{entity.md,datapackage.yaml,recipe/build.py,recipe/sources.yaml,recipe/README.md}`
- Create: `science/tests/fixtures/commons/protein-crosswalk/datasets/protein-crosswalk-uniprot/{entity.md,datapackage.yaml}`
- Create: `science/tests/fixtures/commons/protein-crosswalk-data/protein-crosswalk-uniprot/crosswalk.csv`

Creates (a) the real commons reference-collection dataset + its operator-run recipe (committed **unbuilt** — placeholder hash, `protein_count: 0`, no `crosswalk.csv` — exactly like C2's gene-crosswalk-hgnc), and (b) a **hermetic 4-row fixture** (no network) used by Task 3 (resolver) and Task 5 (check). The acceptance gate is the hermetic fixture + green tests. The recipe's `build.py` imports the build helpers created in **Task 4**; the unbuilt dataset committed here does not run it, so this task does not depend on Task 4.

**This task spans TWO repositories:** `~/d/science-commons` (the real dataset; local-only, commit never push) and `~/d/science` (branch `feat/c3-protein-crosswalk`; the test fixture). **Study C2's `~/d/science-commons/datasets/gene-crosswalk-hgnc/` and `science/tests/fixtures/commons/gene-crosswalk{,-data}/` first** and match their conventions; if any field/path convention differs from the literal YAML below, follow C2's convention and note the deviation.

- [ ] **Step 1: Create the real commons dataset entity**

`~/d/science-commons/datasets/protein-crosswalk-uniprot/entity.md`:

```markdown
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.protein_crosswalk/1.0
id: dataset:protein-crosswalk-uniprot
type: dataset
title: "UniProt protein crosswalk — protein_key-keyed reference collection (human, reviewed)"
version: "1.0.0"
created: "2026-05-27"
updated: "2026-05-27"
tags: []
access:
  level: public
  availability: available
  verified: true
  verification_method: retrieved
  source_url: https://www.uniprot.org/help/downloads
datapackage: datapackage.yaml
origin: external
status: active
tier: use-now
update_cadence: quarterly
member_key_column: protein_key
protein_count: 0
---

# UniProt protein crosswalk

A reference collection (foundation primitive, fourth instance) whose member rows
are addressed by an opaque composite `protein_key` `"<taxon>|uniprot|<accession>"`
(e.g. `9606|uniprot|P04217`). Built from pinned, dated UniProt release files
(reviewed Swiss-Prot human idmapping + secondary accessions); see `recipe/`. The
UniProtKB accession is the canonical human protein anchor (C-D1); Ensembl protein
/ RefSeq protein / entry name are accepted inputs resolved *to* it. Each row
carries the C2 canonical `gene_key` (protein→gene join). Isoform accessions
(`P12345-2`) are a valid lower-level identity surfaced against the canonical, not
collapsed. Secondary (merged) accessions are retained with a `replacement_protein_keys`
forward pointer. Individual proteins are promoted to their own `dataset`
(`derivation.kind: member_of`, `member_key` = the `protein_key`) only on demand.
```

(Set `protein_count` to the real row count after the recipe runs.)

- [ ] **Step 2: Create the datapackage (hash filled when built)**

`~/d/science-commons/datasets/protein-crosswalk-uniprot/datapackage.yaml`:

```yaml
name: protein-crosswalk-uniprot
profile: data-package
title: "UniProt protein crosswalk — protein_key -> entry_name/ensembl/refseq + gene_key + lifecycle"
version: "1.0.0"
licenses:
  - name: CC-BY-4.0
    path: https://creativecommons.org/licenses/by/4.0/
    title: Creative Commons Attribution 4.0 International
provenance:
  - action: build
    tool: recipe/build.py
resources:
  - name: crosswalk
    path: crosswalk.csv
    format: csv
    mediatype: text/csv
    description: "One row per UniProt entry: protein_key (member key), entry_name, ensembl_protein, refseq_protein, gene_key, status, replacement_protein_keys."
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 0
```

- [ ] **Step 3: Create the pinned recipe inputs**

`~/d/science-commons/datasets/protein-crosswalk-uniprot/recipe/sources.yaml`:

```yaml
# Pinned, dated UniProt release files (immutable; the 'current_release' alias is
# discovery-only, C-D3). Discover the current dated release from
# https://www.uniprot.org/help/downloads (knowledgebase release N_M) and pin it
# here before building. v1 scope = reviewed Swiss-Prot, human (taxon 9606).
#   - idmapping_url: a reviewed-human idmapping export in long format
#     (one `accession <TAB> id_type <TAB> value` per line); the recipe parser
#     reads the UniProtKB-ID, Ensembl_PRO, RefSeq, and HGNC types.
#   - secondary_url: the UniProt secondary-accession file (sec_ac.txt), pairs of
#     `secondary primary` accessions; only those whose primary is a reviewed
#     member become merged rows.
idmapping_url: "https://ftp.uniprot.org/pub/databases/uniprot/previous_releases/release-2025_02/knowledgebase/idmapping/by_organism/HUMAN_9606_idmapping.dat.gz"
secondary_url: "https://ftp.uniprot.org/pub/databases/uniprot/previous_releases/release-2025_02/knowledgebase/complete/docs/sec_ac.txt"
```

- [ ] **Step 4: Create the recipe runner**

`~/d/science-commons/datasets/protein-crosswalk-uniprot/recipe/build.py`:

```python
"""Operator-run build of the UniProt protein crosswalk's crosswalk.csv.

Run from the dataset directory:  uv run --with httpx --with pyyaml python recipe/build.py
Network fetches the pinned dated UniProt release files; output is a few-MB CSV.
The idmapping source is expected pre-filtered to reviewed Swiss-Prot human (v1
scope); the parser is source-agnostic (it emits a row per accession it sees).
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from science_tool.commons.protein_crosswalk_build import build_rows, fetch_text

_HERE = Path(__file__).resolve().parent
_OUT = _HERE.parent / "crosswalk.csv"
_FIELDS = [
    "protein_key",
    "entry_name",
    "ensembl_protein",
    "refseq_protein",
    "gene_key",
    "status",
    "replacement_protein_keys",
]


def main() -> None:
    src = yaml.safe_load((_HERE / "sources.yaml").read_text(encoding="utf-8"))
    idmapping = fetch_text(src["idmapping_url"])  # transparently gunzips a .gz handle
    secondary = fetch_text(src["secondary_url"])
    rows = build_rows(idmapping_text=idmapping, secondary_text=secondary)
    with _OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {_OUT}")


if __name__ == "__main__":
    main()
```

(`fetch_text` transparently gunzips a `.gz` handle, so `sources.yaml` may pin the dated `.gz` files directly; the parser is pure over the decompressed text.)

- [ ] **Step 5: Write the recipe README**

`~/d/science-commons/datasets/protein-crosswalk-uniprot/recipe/README.md`:

```markdown
# UniProt protein crosswalk build

1. Pin the current dated UniProt release handles in `sources.yaml`. Discover them
   at https://www.uniprot.org/help/downloads (knowledgebase `release-<N_M>`).
   Use a dated `previous_releases/release-<N_M>/...` path, never the
   `current_release` alias (C-D3). v1 scope = reviewed Swiss-Prot, human (9606):
   the idmapping handle must be the reviewed-human idmapping (or filter the
   per-organism idmapping to the reviewed accession set before building).
2. Build: `uv run --with httpx --with pyyaml python recipe/build.py` (writes `../crosswalk.csv`).
   `fetch_text` transparently gunzips a `.gz` handle, so the dated `.gz` files can
   be pinned directly in `sources.yaml`.
3. Pin the artifact hash + size into `datapackage.yaml`:
   `python - <<'PY'\nimport hashlib,os;p="crosswalk.csv";print("sha256:"+hashlib.sha256(open(p,'rb').read()).hexdigest(),os.path.getsize(p))\nPY`
4. Update `entity.md` `protein_count` to the row count.

The member key is an opaque composite `"<taxon>|uniprot|<accession>"`. Within-cell
multi-values use `;`. Each row carries the C2 `gene_key` (from the HGNC xref).
```

- [ ] **Step 6: (Operator step — network) Populate the real crosswalk**

If network is available (`fetch_text` gunzips `.gz` handles transparently):

```bash
cd ~/d/science-commons/datasets/protein-crosswalk-uniprot
uv run --with httpx --with pyyaml python recipe/build.py
python - <<'PY'
import hashlib, os
b = open("crosswalk.csv", "rb").read()
print("sha256:" + hashlib.sha256(b).hexdigest(), len(b))
PY
# paste the printed hash + bytes into datapackage.yaml; set entity.md protein_count
```

If network is unavailable, leave the placeholder hash and `protein_count: 0`; the machinery + hermetic tests below still stand. **Do not commit `crosswalk.csv` with a placeholder hash** — either populate it fully or leave it unbuilt.

- [ ] **Step 7: Create the hermetic synthetic fixture (no network)**

`science/tests/fixtures/commons/protein-crosswalk/datasets/protein-crosswalk-uniprot/entity.md`:

```markdown
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.protein_crosswalk/1.0
id: dataset:protein-crosswalk-uniprot
type: dataset
title: "UniProt protein crosswalk (test fixture)"
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
member_key_column: protein_key
protein_count: 4
---

# UniProt protein crosswalk (test fixture)
```

`science/tests/fixtures/commons/protein-crosswalk-data/protein-crosswalk-uniprot/crosswalk.csv` (data lives under the data-root layout `<data_root>/<slug>/<logical_path>`; `ENSPSHARED` is an Ensembl-protein id shared by two rows to exercise ambiguity; `P99999` is a merged secondary accession; the two blank `replacement_protein_keys` on the approved rows are deliberate):

```csv
protein_key,entry_name,ensembl_protein,refseq_protein,gene_key,status,replacement_protein_keys
9606|uniprot|P04217,A1BG_HUMAN,ENSP00000263100;ENSPSHARED,NP_570602,9606|hgnc|HGNC:5,approved,
9606|uniprot|P31946,1433B_HUMAN,ENSP00000300161;ENSP00000493072,NP_003395,9606|hgnc|HGNC:12849,approved,
9606|uniprot|Q9NQ94,A1CF_HUMAN,ENSP00000363105;ENSPSHARED,NP_055521,9606|hgnc|HGNC:24086,approved,
9606|uniprot|P99999,,,,,merged,9606|uniprot|P04217
```

`science/tests/fixtures/commons/protein-crosswalk/datasets/protein-crosswalk-uniprot/datapackage.yaml` (fill the hash in Step 8):

```yaml
name: protein-crosswalk-uniprot
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
p = "science/tests/fixtures/commons/protein-crosswalk-data/protein-crosswalk-uniprot/crosswalk.csv"
b = open(p, "rb").read()
print("sha256:" + hashlib.sha256(b).hexdigest(), len(b))
PY
# paste the hash into the fixture datapackage.yaml `hash:` and the byte count into `bytes:`
```

- [ ] **Step 9: Commit**

```bash
cd ~/d/science
# Stage BOTH the entity-store fixture AND the data-root fixture (the resolver
# tests in Task 3 read the CSV under protein-crosswalk-data) — never leave the
# data file untracked.
git add science/tests/fixtures/commons/protein-crosswalk science/tests/fixtures/commons/protein-crosswalk-data
git commit -m "feat(commons): protein-crosswalk reference collection + recipe + test fixture"

# Commit the real commons dataset separately in ~/d/science-commons (unbuilt is fine).
cd ~/d/science-commons
git add datasets/protein-crosswalk-uniprot
git commit -m "feat: UniProt protein crosswalk reference collection (unbuilt)"
# This repo has no remote — commit only, never push.
```

---

## Task 3: Protein crosswalk resolver

**Files:**
- Create: `science/src/science_tool/commons/protein_crosswalk.py`
- Test: `science/tests/test_commons_protein_crosswalk.py`

A pure resolver over the crosswalk rows, mirroring `commons/gene_crosswalk.py`. Reads the data resource through the sha256-verified `resolve()`, exposes the `protein_key` set, and resolves a `(taxon, namespace, protein_id)` to a discriminated result. **Exact `protein_key` equality is identity (RCM-D6);** isoform inputs surface the canonical with provenance (never collapsed); merged accessions surface a forward pointer (never auto-followed); ambiguous inputs return a type with no `protein_key`. The opaque key is **never split** — taxon scoping uses the `taxon` parameter vs `_HUMAN_TAXON`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_protein_crosswalk.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.protein_crosswalk import (
    AmbiguousProteinMatch,
    ProteinCrosswalkError,
    ResolvedProteinMatch,
    available_protein_keys,
    to_canonical,
)

_FIX = Path(__file__).parent / "fixtures" / "commons" / "protein-crosswalk"
_DATA = Path(__file__).parent / "fixtures" / "commons" / "protein-crosswalk-data"


def _kw() -> dict:
    return {"commons_root": _FIX, "data_root": _DATA}


def test_available_keys_are_the_protein_keys() -> None:
    keys = available_protein_keys(**_kw())
    assert keys == {
        "9606|uniprot|P04217",
        "9606|uniprot|P31946",
        "9606|uniprot|Q9NQ94",
        "9606|uniprot|P99999",
    }


def test_resolve_by_uniprot_accession_exact() -> None:
    m = to_canonical(taxon=9606, namespace="uniprot", protein_id="P04217", **_kw())
    assert isinstance(m, ResolvedProteinMatch)
    assert m.protein_key == "9606|uniprot|P04217"
    assert m.entry_name == "A1BG_HUMAN"
    assert m.gene_key == ("9606|hgnc|HGNC:5",)
    assert m.match_type == "exact"
    assert m.isoform is None
    assert m.status == "approved"
    assert m.replacement_protein_key is None


def test_resolve_by_entry_name() -> None:
    m = to_canonical(taxon=9606, namespace="uniprot_entry_name", protein_id="1433B_HUMAN", **_kw())
    assert isinstance(m, ResolvedProteinMatch) and m.protein_key == "9606|uniprot|P31946"
    assert m.match_type == "entry_name"


def test_resolve_by_ensembl_protein() -> None:
    m = to_canonical(taxon=9606, namespace="ensembl_protein", protein_id="ENSP00000300161", **_kw())
    assert isinstance(m, ResolvedProteinMatch) and m.protein_key == "9606|uniprot|P31946"
    assert m.match_type == "ensembl_protein"


def test_resolve_by_refseq_protein() -> None:
    m = to_canonical(taxon=9606, namespace="refseq_protein", protein_id="NP_055521", **_kw())
    assert isinstance(m, ResolvedProteinMatch) and m.protein_key == "9606|uniprot|Q9NQ94"
    assert m.match_type == "refseq_protein"


def test_isoform_input_surfaces_canonical_not_collapsed() -> None:
    m = to_canonical(taxon=9606, namespace="uniprot", protein_id="P31946-2", **_kw())
    assert isinstance(m, ResolvedProteinMatch)
    assert m.protein_key == "9606|uniprot|P31946"  # the canonical member row
    assert m.match_type == "isoform"
    assert m.isoform == "P31946-2"  # the queried isoform preserved, not collapsed


def test_shared_ensembl_protein_is_ambiguous_with_no_protein_key() -> None:
    m = to_canonical(taxon=9606, namespace="ensembl_protein", protein_id="ENSPSHARED", **_kw())
    assert isinstance(m, AmbiguousProteinMatch)
    assert set(m.candidates) == {"9606|uniprot|P04217", "9606|uniprot|Q9NQ94"}
    assert not hasattr(m, "protein_key")


def test_merged_accession_surfaces_status_and_forward_pointer_not_auto_followed() -> None:
    m = to_canonical(taxon=9606, namespace="uniprot", protein_id="P99999", **_kw())
    assert isinstance(m, ResolvedProteinMatch)
    assert m.protein_key == "9606|uniprot|P99999"  # the matched (merged) row, NOT the target
    assert m.status == "merged"
    assert m.replacement_protein_key == "9606|uniprot|P04217"


def test_unknown_id_returns_none() -> None:
    assert to_canonical(taxon=9606, namespace="uniprot", protein_id="P00000", **_kw()) is None


def test_other_taxon_returns_none() -> None:
    # v1 crosswalk is human-only; a non-human taxon resolves nothing (and the
    # resolver does NOT parse the taxon out of the opaque protein_key).
    assert to_canonical(taxon=10090, namespace="uniprot", protein_id="P04217", **_kw()) is None


def test_unsupported_namespace_raises() -> None:
    with pytest.raises(ProteinCrosswalkError, match="unsupported protein namespace"):
        to_canonical(taxon=9606, namespace="entrez", protein_id="1", **_kw())


# --- pure row validation (no I/O) ---


def test_parse_rejects_duplicate_member_key() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    rows = [
        {"protein_key": "9606|uniprot|P04217", "status": "approved"},
        {"protein_key": "9606|uniprot|P04217", "status": "approved"},
    ]
    with pytest.raises(ProteinCrosswalkError, match="duplicate member key"):
        _parse_crosswalk_rows(rows)


def test_parse_rejects_blank_key() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    with pytest.raises(ProteinCrosswalkError, match="blank protein_key"):
        _parse_crosswalk_rows([{"protein_key": "  ", "status": "approved"}])


def test_parse_rejects_missing_column() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    with pytest.raises(ProteinCrosswalkError, match="missing required column"):
        _parse_crosswalk_rows([{"entry_name": "A1BG_HUMAN", "status": "approved"}])


def test_parse_rejects_unknown_status() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    with pytest.raises(ProteinCrosswalkError, match="invalid status"):
        _parse_crosswalk_rows([{"protein_key": "9606|uniprot|P04217", "status": "bogus"}])


def test_parse_rejects_merged_with_wrong_replacement_count() -> None:
    from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows

    with pytest.raises(ProteinCrosswalkError, match="merged.*requires"):
        _parse_crosswalk_rows([{"protein_key": "9606|uniprot|P99999", "status": "merged", "replacement_protein_keys": ""}])


def test_make_protein_key_is_pipe_delimited_opaque_composite() -> None:
    from science_tool.commons.protein_crosswalk import make_protein_key

    assert make_protein_key(9606, "P04217") == "9606|uniprot|P04217"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_protein_crosswalk.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.protein_crosswalk'`.

- [ ] **Step 3: Implement the resolver**

Create `science/src/science_tool/commons/protein_crosswalk.py`:

```python
"""Resolver over the protein_key-keyed UniProt protein crosswalk (Pillar C, sub-phase C3).

Fourth instance of the reference-collection primitive (after gene-sets D, the
assembly registry C1, and the gene crosswalk C2): a ``dataset`` whose member rows
are keyed by an opaque composite ``protein_key`` ``"<taxon>|uniprot|<accession>"``
(e.g. ``9606|uniprot|P04217``). The key uses ``|`` as its field delimiter; UniProt
accessions are ``[A-Z0-9]`` only, so the delimiter never collides. **The key is
opaque — never split — by everything except** ``make_protein_key`` (RCM-D6:
byte-equality is identity). Taxon scoping uses the ``taxon`` parameter
(``_HUMAN_TAXON``), never by parsing the key. Pure over pinned, sha256-verified
inputs (no network). The public API is species-aware and namespace-explicit
(taxon + namespace on every call; C-D1). An **isoform** input (``P12345-2``)
surfaces the canonical member with ``match_type='isoform'`` and the queried isoform
preserved (decision d5: isoforms are a distinct lower-level identity, NOT
collapsed). A **merged** secondary accession surfaces ``status='merged'`` +
``replacement_protein_key`` (never auto-followed). An ambiguous input returns a
distinct ``AmbiguousProteinMatch`` with no ``protein_key``. Each row carries the
C2 ``gene_key`` (protein->gene join pointer). See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D1/§8 C3).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.resolver import resolve

PROTEIN_CROSSWALK_ID = "dataset:protein-crosswalk-uniprot"
PROTEIN_CROSSWALK_RESOURCE = "crosswalk.csv"
MEMBER_KEY_COLUMN = "protein_key"
SUPPORTED_PROTEIN_NAMESPACES = frozenset({"uniprot", "uniprot_entry_name", "ensembl_protein", "refseq_protein"})

_HUMAN_TAXON = 9606  # v1 crosswalk is human-only
_VALID_STATUS = frozenset({"approved", "merged"})
_MULTIVALUE_SEP = ";"  # within-cell separator; NOT '|' (protein_key uses '|' internally)


class ProteinCrosswalkError(ValueError):
    """A crosswalk row violates the reference-collection contract, or an
    unsupported namespace/accession was requested (fail early; RCM-D1/D6)."""


def make_protein_key(taxon: int, accession: str) -> str:
    """Construct the opaque composite member key ``"<taxon>|uniprot|<accession>"``.

    The single canonical builder. ``accession`` must be a non-blank UniProt
    accession (no ``|``, which is the field delimiter). The result is opaque
    downstream. Isoform-suffixed inputs (``P12345-2``) are NOT keys: the resolver
    strips the suffix before building the canonical key.
    """
    accession = accession.strip()
    if not accession or "|" in accession:
        raise ProteinCrosswalkError(f"invalid UniProt accession {accession!r}")
    return f"{taxon}|uniprot|{accession}"


@dataclass(frozen=True, slots=True)
class CrosswalkRow:
    """One crosswalk row. Multi-value fields are already split on ';'."""

    protein_key: str
    entry_name: str
    ensembl_protein: tuple[str, ...]
    refseq_protein: tuple[str, ...]
    gene_key: tuple[str, ...]
    status: str
    replacement_protein_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedProteinMatch:
    """An input that resolves to exactly one canonical protein, with provenance.

    ``status == 'merged'`` means the matched row is a deprecated secondary
    accession; follow ``replacement_protein_key`` explicitly (never auto-followed).
    ``match_type == 'isoform'`` means an isoform accession was queried; ``isoform``
    holds it and ``protein_key`` is the canonical (not collapsed — both surfaced).
    """

    protein_key: str
    entry_name: str
    ensembl_protein: tuple[str, ...]
    refseq_protein: tuple[str, ...]
    gene_key: tuple[str, ...]
    match_type: str  # exact | entry_name | ensembl_protein | refseq_protein | isoform
    isoform: str | None  # the queried isoform accession when match_type == 'isoform', else None
    status: str  # row lifecycle: approved | merged
    replacement_protein_key: str | None


@dataclass(frozen=True, slots=True)
class AmbiguousProteinMatch:
    """An input mapping to >1 candidate (e.g. a RefSeq/Ensembl-protein id shared by
    >1 UniProt entry). It deliberately has NO ``protein_key``: the caller must not
    pick one (RCM-D6 — never collapse distinct identities)."""

    query: str
    candidates: tuple[str, ...]


ProteinMatch = ResolvedProteinMatch | AmbiguousProteinMatch


def _split_multi(cell: str) -> tuple[str, ...]:
    return tuple(part for part in (cell or "").split(_MULTIVALUE_SEP) if part)


def _parse_crosswalk_rows(rows: Iterable[dict[str, Any]]) -> list[CrosswalkRow]:
    """Validate + parse raw CSV rows; fail early on a broken collection (RCM-D1/D6).

    Every row needs a present, non-blank, UNIQUE ``protein_key`` and a known
    ``status``. A ``merged`` row must carry exactly one replacement (a secondary
    accession is a one-to-one redirect). Pure (no I/O).
    """
    out: list[CrosswalkRow] = []
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if MEMBER_KEY_COLUMN not in row:
            raise ProteinCrosswalkError(f"row {i}: missing required column {MEMBER_KEY_COLUMN!r}")
        key = (row.get(MEMBER_KEY_COLUMN) or "").strip()
        if not key:
            raise ProteinCrosswalkError(f"row {i}: blank {MEMBER_KEY_COLUMN} (member key)")
        if key in seen:
            raise ProteinCrosswalkError(f"duplicate member key {MEMBER_KEY_COLUMN}={key!r}")
        seen.add(key)
        status = (row.get("status") or "").strip()
        if status not in _VALID_STATUS:
            raise ProteinCrosswalkError(f"row {i}: invalid status {status!r} (expected one of {sorted(_VALID_STATUS)})")
        replacements = _split_multi(row.get("replacement_protein_keys", ""))
        if status == "merged" and len(replacements) != 1:
            raise ProteinCrosswalkError(
                f"row {i}: status 'merged' requires exactly 1 replacement_protein_key, got {len(replacements)}"
            )
        out.append(
            CrosswalkRow(
                protein_key=key,
                entry_name=(row.get("entry_name") or "").strip(),
                ensembl_protein=_split_multi(row.get("ensembl_protein", "")),
                refseq_protein=_split_multi(row.get("refseq_protein", "")),
                gene_key=_split_multi(row.get("gene_key", "")),
                status=status,
                replacement_protein_keys=replacements,
            )
        )
    return out


def load_protein_crosswalk(
    *,
    registry_id: str = PROTEIN_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[CrosswalkRow]:
    """Load + sha256-verify the crosswalk rows. Raises CommonsError if absent,
    ProteinCrosswalkError if a row violates the collection contract."""
    resolved = resolve(registry_id, PROTEIN_CROSSWALK_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as fh:
        return _parse_crosswalk_rows(csv.DictReader(fh))


def available_protein_keys(
    *,
    registry_id: str = PROTEIN_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> set[str]:
    """The set of protein_key member keys for `registry_id` (used by downstream
    payload-resolution audits; the validate check does not call this)."""
    return {
        r.protein_key
        for r in load_protein_crosswalk(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    }


def _match_rows(
    rows: list[CrosswalkRow], taxon: int, namespace: str, protein_id: str
) -> tuple[list[CrosswalkRow], str, str | None]:
    """Return (matched_rows, match_type, isoform). Pure; `namespace` already validated.

    The v1 crosswalk is human-only; a non-human taxon matches nothing. We gate on
    the `taxon` parameter rather than parse it out of the opaque protein_key.
    """
    if taxon != _HUMAN_TAXON:
        return [], "exact", None
    if namespace == "uniprot":
        if "-" in protein_id:  # isoform accession, e.g. P12345-2
            canonical = protein_id.split("-", 1)[0]
            target = make_protein_key(taxon, canonical)
            return [r for r in rows if r.protein_key == target], "isoform", protein_id
        target = make_protein_key(taxon, protein_id)
        return [r for r in rows if r.protein_key == target], "exact", None
    if namespace == "uniprot_entry_name":
        return [r for r in rows if r.entry_name and r.entry_name == protein_id], "entry_name", None
    if namespace == "ensembl_protein":
        return [r for r in rows if protein_id in r.ensembl_protein], "ensembl_protein", None
    # refseq_protein
    return [r for r in rows if protein_id in r.refseq_protein], "refseq_protein", None


def to_canonical(
    *,
    taxon: int,
    namespace: str,
    protein_id: str,
    registry_id: str = PROTEIN_CROSSWALK_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ProteinMatch | None:
    """Resolve a protein id in `namespace` to its canonical protein (RCM-D6).

    Returns ``ResolvedProteinMatch`` for a unique hit (carrying ``status`` +
    ``replacement_protein_key`` + ``isoform`` provenance and the ``gene_key``
    join), ``AmbiguousProteinMatch`` when the input maps to >1 candidate (no
    ``protein_key`` — the caller must not guess), or ``None`` when nothing matches.
    Raises ``ProteinCrosswalkError`` for an unsupported namespace (fail early).
    `protein_id` is named to avoid shadowing the ``id`` builtin (ruff A002)."""
    if namespace not in SUPPORTED_PROTEIN_NAMESPACES:
        raise ProteinCrosswalkError(
            f"unsupported protein namespace {namespace!r}; expected one of {sorted(SUPPORTED_PROTEIN_NAMESPACES)}"
        )
    rows = load_protein_crosswalk(registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    matched, match_type, isoform = _match_rows(rows, taxon, namespace, protein_id)
    if not matched:
        return None
    if len(matched) > 1:
        return AmbiguousProteinMatch(query=protein_id, candidates=tuple(sorted(r.protein_key for r in matched)))
    row = matched[0]
    return ResolvedProteinMatch(
        protein_key=row.protein_key,
        entry_name=row.entry_name,
        ensembl_protein=row.ensembl_protein,
        refseq_protein=row.refseq_protein,
        gene_key=row.gene_key,
        match_type=match_type,
        isoform=isoform,
        status=row.status,
        replacement_protein_key=(row.replacement_protein_keys[0] if row.replacement_protein_keys else None),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_protein_crosswalk.py -v`
Expected: all PASS. (If a `DataIntegrityError` fires, the fixture CSV hash in Task 2 Step 8 was not pinned correctly — re-run the sha256 step.)

- [ ] **Step 5: Ruff + commit**

```bash
cd ~/d/science/science && uv run --frozen ruff check src/science_tool/commons/protein_crosswalk.py tests/test_commons_protein_crosswalk.py
cd ~/d/science
git add science/src/science_tool/commons/protein_crosswalk.py science/tests/test_commons_protein_crosswalk.py
git commit -m "feat(commons): UniProt protein crosswalk resolver (discriminated result, isoform-surfaced, RCM-D6)"
```

---

## Task 4: UniProt parsing build helpers

**Files:**
- Create: `science/src/science_tool/commons/protein_crosswalk_build.py`
- Test: `science/tests/test_protein_crosswalk_build.py`

Pure parsing of the two UniProt release files into crosswalk rows. The idmapping long-format file (one `accession <TAB> id_type <TAB> value` per line) is grouped by accession; the secondary-accession file becomes `merged` rows. The single canonical key builder `make_protein_key` lives in `protein_crosswalk.py` (Task 3) and is imported here; the C2 `make_gene_key` is imported to build the `gene_key` column from UniProt's HGNC xref. The round-trip test imports the resolver's `_parse_crosswalk_rows` to assert the build output and the resolver share one contract.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_protein_crosswalk_build.py`:

```python
from __future__ import annotations

import csv
import io

from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows, make_protein_key
from science_tool.commons.protein_crosswalk_build import (
    build_rows,
    fetch_text,
    parse_idmapping,
    parse_secondary,
)

_IDMAPPING = (
    "P04217\tUniProtKB-ID\tA1BG_HUMAN\n"
    "P04217\tEnsembl_PRO\tENSP00000263100\n"
    "P04217\tRefSeq\tNP_570602\n"
    "P04217\tHGNC\tHGNC:5\n"
    "P31946\tUniProtKB-ID\t1433B_HUMAN\n"
    "P31946\tEnsembl_PRO\tENSP00000300161\n"
    "P31946\tEnsembl_PRO\tENSP00000493072\n"
    "P31946\tHGNC\tHGNC:12849\n"
)

_SECONDARY = (
    "This is a header preamble line that must be ignored.\n"
    "Secondary AC     Primary AC\n"
    "P99999       P04217\n"
    "Q88888       Q00000\n"  # primary not in the reviewed set -> dropped
)


def test_make_protein_key_is_pipe_delimited_opaque_composite() -> None:
    assert make_protein_key(9606, "P04217") == "9606|uniprot|P04217"


def test_parse_idmapping_groups_by_accession_and_builds_gene_key() -> None:
    rows = parse_idmapping(_IDMAPPING)
    p31946 = next(r for r in rows if r["protein_key"] == "9606|uniprot|P31946")
    assert p31946["entry_name"] == "1433B_HUMAN"
    assert p31946["ensembl_protein"] == "ENSP00000300161;ENSP00000493072"  # multi-value joined on ';'
    assert p31946["status"] == "approved"
    p04217 = next(r for r in rows if r["protein_key"] == "9606|uniprot|P04217")
    assert p04217["refseq_protein"] == "NP_570602"
    assert p04217["gene_key"] == "9606|hgnc|HGNC:5"  # built from the HGNC xref via make_gene_key


def test_parse_secondary_emits_merged_rows_for_known_primaries_only() -> None:
    primary_keys = {"9606|uniprot|P04217"}
    rows = parse_secondary(_SECONDARY, primary_keys=primary_keys)
    assert len(rows) == 1
    merged = rows[0]
    assert merged["protein_key"] == "9606|uniprot|P99999"
    assert merged["status"] == "merged"
    assert merged["replacement_protein_keys"] == "9606|uniprot|P04217"


def test_build_rows_round_trips_through_the_resolver_parser() -> None:
    # The build output must parse cleanly back through the resolver's row parser
    # (same protein_key column, same ';' multi-value separator) — shared contract.
    rows = build_rows(idmapping_text=_IDMAPPING, secondary_text=_SECONDARY)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    parsed = _parse_crosswalk_rows(csv.DictReader(buf))
    assert len(parsed) == len(rows) == 3  # 2 primary + 1 merged


def test_fetch_text_is_callable_without_network() -> None:
    # Importing the module does not require a network call.
    assert callable(fetch_text)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_protein_crosswalk_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.protein_crosswalk_build'`.

- [ ] **Step 3: Implement the build helpers**

Create `science/src/science_tool/commons/protein_crosswalk_build.py`:

```python
"""UniProt parsing for the protein crosswalk (Pillar C, C3).

Parses the UniProt idmapping long-format file (one ``accession <TAB> id_type
<TAB> value`` per line) into approved crosswalk rows, and the secondary-accession
file into ``merged`` rows with a forward pointer. Each approved row carries the C2
``gene_key`` built from UniProt's HGNC cross-reference. ``fetch_text`` is the only
network call (build-time only); all parsing is pure. The v1 scope (reviewed
Swiss-Prot, human) is a source-file choice — the parser is source-agnostic (it
emits one row per accession it sees). See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D1/C-D3).
"""

from __future__ import annotations

import csv
import io
from collections import OrderedDict
from typing import Any

from science_tool.commons.gene_crosswalk import make_gene_key
from science_tool.commons.protein_crosswalk import make_protein_key

_HUMAN_TAXON = 9606
_OUT_SEP = ";"  # within-cell multi-value separator; NOT '|' (protein_key uses '|')

# UniProt idmapping id_types this build consumes.
_ID_ENTRY_NAME = "UniProtKB-ID"
_ID_ENSEMBL_PRO = "Ensembl_PRO"
_ID_REFSEQ = "RefSeq"
_ID_HGNC = "HGNC"


def parse_idmapping(dat_text: str) -> list[dict[str, Any]]:
    """Parse the UniProt idmapping long format (tab-separated) into approved rows.

    Groups lines by accession (column 0), collecting the entry name, Ensembl
    protein ids, RefSeq protein ids, and HGNC ids. The HGNC ids become the C2
    ``gene_key`` join via ``make_gene_key``. Multi-valued fields are ';'-joined.
    """
    by_ac: OrderedDict[str, dict[str, Any]] = OrderedDict()
    reader = csv.reader(io.StringIO(dat_text), delimiter="\t")
    for rec in reader:
        if len(rec) != 3:
            continue
        ac, id_type, value = rec[0].strip(), rec[1].strip(), rec[2].strip()
        if not ac or not value:
            continue
        bucket = by_ac.setdefault(ac, {"entry_name": "", "ensembl": [], "refseq": [], "hgnc": []})
        if id_type == _ID_ENTRY_NAME:
            bucket["entry_name"] = value
        elif id_type == _ID_ENSEMBL_PRO:
            bucket["ensembl"].append(value)
        elif id_type == _ID_REFSEQ:
            bucket["refseq"].append(value)
        elif id_type == _ID_HGNC and value.startswith("HGNC:"):
            bucket["hgnc"].append(value)
    rows: list[dict[str, Any]] = []
    for ac, b in by_ac.items():
        gene_keys = [make_gene_key(_HUMAN_TAXON, h) for h in b["hgnc"]]
        rows.append(
            {
                "protein_key": make_protein_key(_HUMAN_TAXON, ac),
                "entry_name": b["entry_name"],
                "ensembl_protein": _OUT_SEP.join(b["ensembl"]),
                "refseq_protein": _OUT_SEP.join(b["refseq"]),
                "gene_key": _OUT_SEP.join(gene_keys),
                "status": "approved",
                "replacement_protein_keys": "",
            }
        )
    return rows


def parse_secondary(sec_text: str, *, primary_keys: set[str]) -> list[dict[str, Any]]:
    """Parse the UniProt secondary-accession file into ``merged`` rows.

    Each data line is two whitespace-separated tokens ``secondary primary``;
    header/preamble lines (other token counts) are skipped. Only secondaries whose
    primary resolves to a known reviewed member (`primary_keys`) become rows — a
    merged secondary is a one-to-one redirect to its primary protein_key.
    """
    rows: list[dict[str, Any]] = []
    for line in sec_text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        secondary, primary = parts[0].strip(), parts[1].strip()
        if not secondary or not primary or "|" in secondary or "|" in primary:
            continue
        primary_key = make_protein_key(_HUMAN_TAXON, primary)
        if primary_key not in primary_keys:
            continue
        rows.append(
            {
                "protein_key": make_protein_key(_HUMAN_TAXON, secondary),
                "entry_name": "",
                "ensembl_protein": "",
                "refseq_protein": "",
                "gene_key": "",
                "status": "merged",
                "replacement_protein_keys": primary_key,
            }
        )
    return rows


def build_rows(*, idmapping_text: str, secondary_text: str) -> list[dict[str, Any]]:
    """Merge approved (idmapping) + merged (secondary-accession) rows.

    Secondary rows are restricted to those whose primary is a known approved
    member, so the crosswalk never points a merged row at a missing primary.
    """
    primary = parse_idmapping(idmapping_text)
    primary_keys = {r["protein_key"] for r in primary}
    merged = parse_secondary(secondary_text, primary_keys=primary_keys)
    return primary + merged


def fetch_text(url: str) -> str:
    """Fetch a text release file, transparently gunzipping a gzip body (UniProt
    handles are ``.gz``). Build-time only; never called at resolve time."""
    import gzip

    import httpx

    resp = httpx.get(url, timeout=120.0, follow_redirects=True)
    resp.raise_for_status()
    data = resp.content
    if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_protein_crosswalk_build.py -v`
Expected: all PASS.

- [ ] **Step 5: Ruff + commit**

```bash
cd ~/d/science/science && uv run --frozen ruff check src/science_tool/commons/protein_crosswalk_build.py tests/test_protein_crosswalk_build.py
cd ~/d/science
git add science/src/science_tool/commons/protein_crosswalk_build.py science/tests/test_protein_crosswalk_build.py
git commit -m "feat(commons): UniProt protein-crosswalk parsing helpers (C-D1/C-D3)"
```

---

## Task 5: Generalize the identity check + add the protein check (declaration-level)

**Files:**
- Modify: `science/src/science_tool/validate/checks/identity_context.py`
- Test: `science/tests/validate/test_checks_identity_context.py`

The C2 gene check and the C3 protein check are identical in logic (malformed → namespace-unsupported → declared_unresolved → registry-unavailable/invalid; raw-frontmatter `_*_defect` re-enforcement). DRY them: extract a tier-parameterized `evaluate_tier_identity` (driven by a `_TierSpec`), rewrite C2's `evaluate_gene_identity` as a thin wrapper over it (C2's existing tests are the refactor guard), and add a protein wrapper + `check_protein_identity` (`order=28`). **Declaration-level only — no data payload is read.**

The refactor preserves every C2 rule string (`identity.gene-malformed`, `-namespace-unsupported`, `-declared-unresolved`, `-registry-unavailable`, `-registry-invalid`) and message, so the C2 gene tests stay green unchanged. The protein tier uses the `identity.protein-*` rule prefix.

- [ ] **Step 1: Confirm no C2 test imports the private gene helpers (they will be removed/renamed)**

Run: `cd ~/d/science && grep -n "_gene_decl\|_gene_defect\|_is_gene_crosswalk" science/tests/validate/test_checks_identity_context.py`
Expected: no matches (the C2 tests use the public `evaluate_gene_identity` + `Severity`, not the private helpers). If there ARE matches, STOP and report — the refactor below removes those private names and the tests would break.

- [ ] **Step 2: Write the failing protein tests**

Append to `science/tests/validate/test_checks_identity_context.py`:

```python
from science_tool.validate.checks.identity_context import evaluate_protein_identity

_PROTEIN_REGISTRY = "dataset:protein-crosswalk-uniprot"
_VALID_PROTEIN_META = {
    "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.protein_crosswalk/1.0",
    "member_key_column": "protein_key",
}
_PROTEIN_META_BY_ID = {_PROTEIN_REGISTRY: _VALID_PROTEIN_META}


def _protein_ds(protein, id_="dataset:p") -> dict:
    return {
        "type": "dataset",
        "id": id_,
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.proteomics/1.0+bio.identity_context/1.0",
        "_path": "data/p/entity.md",
        "identity_context": {"taxon": 9606, "molecular_ids": {"protein": protein}},
    }


def test_protein_supported_namespace_with_valid_registry_passes_silently() -> None:
    ds = _protein_ds({"namespace": "uniprot", "canonical": True})
    assert list(evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)) == []


def test_protein_default_registry_used_when_unspecified() -> None:
    ds = _protein_ds({"namespace": "ensembl_protein"})
    assert list(evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)) == []


def test_protein_unsupported_namespace_errors() -> None:
    ds = _protein_ds({"namespace": "entrez"})
    errs = [r for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-namespace-unsupported"


def test_protein_declared_unresolved_infos() -> None:
    ds = _protein_ds({"namespace": "uniprot", "resolution_status": "declared_unresolved"})
    res = list(evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID))
    assert not [r for r in res if r.severity is Severity.ERROR]
    assert [r for r in res if r.rule == "identity.protein-declared-unresolved"]


def test_protein_declared_unresolved_with_unsupported_namespace_still_errors() -> None:
    ds = _protein_ds({"namespace": "entrez", "resolution_status": "declared_unresolved"})
    errs = [r for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-namespace-unsupported"


def test_protein_wrong_registry_type_errors() -> None:
    meta = {
        "dataset:gene-crosswalk-hgnc": {
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
            "member_key_column": "gene_key",
        }
    }
    ds = _protein_ds({"namespace": "uniprot", "registry": "dataset:gene-crosswalk-hgnc"})
    errs = [r for r in evaluate_protein_identity([ds], registry_meta_by_id=meta) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-registry-invalid"


def test_protein_unloadable_registry_infos_not_errors() -> None:
    ds = _protein_ds({"namespace": "uniprot"})
    res = list(evaluate_protein_identity([ds], registry_meta_by_id={_PROTEIN_REGISTRY: None}))
    assert not [r for r in res if r.severity is Severity.ERROR]
    assert [r for r in res if r.rule == "identity.protein-registry-unavailable"]


def test_protein_malformed_registry_errors() -> None:
    ds = _protein_ds({"namespace": "uniprot", "registry": "protein-crosswalk-uniprot"})
    errs = [r for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-malformed"


def test_protein_bad_resolution_status_errors() -> None:
    ds = _protein_ds({"namespace": "uniprot", "resolution_status": "maybe"})
    errs = [r for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-malformed"


def test_protein_not_a_dict_errors() -> None:
    ds = _protein_ds("uniprot")
    errs = [r for r in evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID) if r.severity is Severity.ERROR]
    assert len(errs) == 1 and errs[0].rule == "identity.protein-malformed"


def test_dataset_without_protein_decl_ignored() -> None:
    ds = {
        "type": "dataset",
        "id": "dataset:q",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.proteomics/1.0+bio.identity_context/1.0",
        "_path": "data/q/entity.md",
        "identity_context": {"taxon": 9606},
    }
    assert list(evaluate_protein_identity([ds], registry_meta_by_id=_PROTEIN_META_BY_ID)) == []
```

- [ ] **Step 3: Run the new protein tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_context.py -k protein -v`
Expected: FAIL with `ImportError: cannot import name 'evaluate_protein_identity'`.

- [ ] **Step 4: Add the new imports**

In `science/src/science_tool/validate/checks/identity_context.py`, add `from dataclasses import dataclass` to the stdlib imports (near `from pathlib import Path`), and add the protein-crosswalk constants import next to the existing `gene_crosswalk` import:

```python
from science_tool.commons.protein_crosswalk import (
    PROTEIN_CROSSWALK_ID,
    MEMBER_KEY_COLUMN as _PROTEIN_KEY_COLUMN,
    SUPPORTED_PROTEIN_NAMESPACES,
)
```

- [ ] **Step 5: Replace the C2 gene section with the generalized tier check**

Replace the entire C2 gene section — from the comment `# --- C2: gene identity (check 2 — declaration-level resolvability) ---` through the end of `check_gene_identity` (the last function in the file) — with the following. This keeps `_load_registry_meta` (verbatim, unchanged) and `evaluate_gene_identity` (now a thin wrapper) so the C2 tests still import and pass:

```python
# --- C2/C3: molecular-id tier identity (declaration-level resolvability) ---


@dataclass(frozen=True, slots=True)
class _TierSpec:
    """Per-tier parameters for the shared declaration-level identity check."""

    tier: str  # the molecular_ids.<tier> key, e.g. "gene" | "protein"
    supported_namespaces: frozenset[str]
    default_registry: str
    key_column: str  # the crosswalk collection's member_key_column const
    profile_token: str  # e.g. "+bio.gene_crosswalk/"
    rule_prefix: str  # e.g. "identity.gene"


def _tier_decl(fm: dict[str, Any], tier: str) -> Any:
    """The raw identity_context.molecular_ids.<tier> declaration, or None."""
    idc = fm.get("identity_context") or {}
    mids = idc.get("molecular_ids") if isinstance(idc, dict) else None
    return mids.get(tier) if isinstance(mids, dict) else None


def _tier_defect(decl: dict[str, Any]) -> str | None:
    """Return a defect message if the raw tier declaration is malformed, else None.

    Raw authored frontmatter bypasses the JSON schema (the closed graph Entity
    drops extension fields), so the schema-critical fields are re-enforced here,
    mirroring C1's `_assembly_defect`: `namespace` required + non-blank; optional
    `registry` a `dataset:` reference; optional `resolution_status` a valid state.
    Tier-independent. Without it, `maybe` would pass like `resolved` and a
    non-`dataset:` registry would degrade to a misleading INFO.
    """
    namespace = decl.get("namespace")
    if not isinstance(namespace, str) or not namespace.strip():
        return "missing or blank namespace"
    registry = decl.get("registry")
    if registry is not None and (not isinstance(registry, str) or not registry.startswith("dataset:")):
        return "registry must be a 'dataset:' reference"
    if decl.get("resolution_status") not in (None, "resolved", "declared_unresolved"):
        return "resolution_status must be 'resolved' or 'declared_unresolved'"
    return None


def _is_crosswalk(meta: dict[str, Any], *, profile_token: str, key_column: str) -> bool:
    profile = str(meta.get("schema_profile") or "")
    return profile_token in f"+{profile}" and meta.get("member_key_column") == key_column


def evaluate_tier_identity(
    datasets: Iterable[dict[str, Any]],
    *,
    spec: _TierSpec,
    registry_meta_by_id: dict[str, dict[str, Any] | None],
) -> Iterator[Result]:
    """Pure core of the declaration-level identity check, parameterized per tier.

    For each dataset declaring identity_context.molecular_ids.<spec.tier>, verify
    the namespace is crosswalk-supported and the declared registry resolves to the
    tier's crosswalk collection (member_key_column: spec.key_column). No data
    payload is read. Namespace support is validated BEFORE the declared_unresolved
    escape (every tier namespace is in scope, so an unsupported one is a real
    error). `registry_meta_by_id` maps each declared (or defaulted) registry id to
    its entity metadata, or None when it was attempted but could not be loaded
    (-> INFO, never a false ERROR). A loaded registry of the WRONG type is an
    ERROR. Unlike check 1 this does not resolve a member key: a declaration names
    a namespace, not a single key.
    """
    reported_registries: set[str] = set()
    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        decl = _tier_decl(fm, spec.tier)
        if decl is None:
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        loc = f"identity_context.molecular_ids.{spec.tier}"
        if not isinstance(decl, dict):
            yield _result(Severity.ERROR, path, f"{ident}: {loc} must be an object", f"{spec.rule_prefix}-malformed")
            continue
        defect = _tier_defect(decl)
        if defect is not None:
            yield _result(
                Severity.ERROR, path, f"{ident}: malformed {loc} -- {defect}", f"{spec.rule_prefix}-malformed"
            )
            continue
        namespace = str(decl["namespace"])  # _tier_defect guaranteed present + non-blank str
        if namespace not in spec.supported_namespaces:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: {spec.tier} namespace {namespace!r} is not crosswalk-supported "
                f"(expected one of {sorted(spec.supported_namespaces)})",
                f"{spec.rule_prefix}-namespace-unsupported",
            )
            continue
        if decl.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: {spec.tier} identity declared_unresolved (honoured, RCM-D2)",
                f"{spec.rule_prefix}-declared-unresolved",
            )
            continue
        registry_id = decl["registry"] if isinstance(decl.get("registry"), str) else spec.default_registry
        meta = registry_meta_by_id.get(registry_id)
        if meta is None:
            if registry_id not in reported_registries:
                reported_registries.add(registry_id)
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: {spec.tier} registry {registry_id!r} unavailable; "
                    f"declared {spec.tier} namespace cannot be verified",
                    f"{spec.rule_prefix}-registry-unavailable",
                )
            continue
        if not _is_crosswalk(meta, profile_token=spec.profile_token, key_column=spec.key_column):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: {spec.tier} registry {registry_id!r} is not a {spec.profile_token[1:-1]} collection "
                f"with member_key_column={spec.key_column!r}",
                f"{spec.rule_prefix}-registry-invalid",
            )
        # supported namespace + valid crosswalk -> passes silently.


def _load_registry_meta(
    registry_id: str,
    *,
    local_by_id: dict[str, dict[str, Any]],
    commons_cache: dict[str, dict[str, Any] | None],
) -> dict[str, Any] | None:
    """Load a registry's identifying metadata (schema_profile + member_key_column).

    Project-local datasets first, then the commons directly. Returns None when the
    registry cannot be loaded (commons not configured/available, or absent) -- the
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


def _run_tier_check(ctx: ValidateContext, spec: _TierSpec) -> Iterator[Result]:
    """Gather raw frontmatter, load metadata for each registry a supported,
    non-declared_unresolved tier declares (or defaults to), then evaluate."""
    datasets = _dataset_frontmatters(ctx)
    local_by_id = {fm["id"]: fm for fm in datasets if isinstance(fm.get("id"), str) and fm["id"]}
    declared: set[str] = set()
    for fm in datasets:
        decl = _tier_decl(fm, spec.tier)
        if not isinstance(decl, dict) or _tier_defect(decl) is not None:
            continue  # malformed tiers are errored by the evaluator; load no registry for them
        if decl.get("resolution_status") == "declared_unresolved":
            continue
        if str(decl["namespace"]) in spec.supported_namespaces:
            declared.add(decl["registry"] if isinstance(decl.get("registry"), str) else spec.default_registry)
    commons_cache: dict[str, dict[str, Any] | None] = {}
    registry_meta_by_id = {
        registry_id: _load_registry_meta(registry_id, local_by_id=local_by_id, commons_cache=commons_cache)
        for registry_id in declared
    }
    yield from evaluate_tier_identity(datasets, spec=spec, registry_meta_by_id=registry_meta_by_id)


_GENE_SPEC = _TierSpec(
    tier="gene",
    supported_namespaces=SUPPORTED_GENE_NAMESPACES,
    default_registry=GENE_CROSSWALK_ID,
    key_column=_GENE_KEY_COLUMN,
    profile_token="+bio.gene_crosswalk/",
    rule_prefix="identity.gene",
)

_PROTEIN_SPEC = _TierSpec(
    tier="protein",
    supported_namespaces=SUPPORTED_PROTEIN_NAMESPACES,
    default_registry=PROTEIN_CROSSWALK_ID,
    key_column=_PROTEIN_KEY_COLUMN,
    profile_token="+bio.protein_crosswalk/",
    rule_prefix="identity.protein",
)


def evaluate_gene_identity(
    datasets: Iterable[dict[str, Any]], *, registry_meta_by_id: dict[str, dict[str, Any] | None]
) -> Iterator[Result]:
    """C2 gene declaration-level evaluator (thin wrapper over the generalized core)."""
    yield from evaluate_tier_identity(datasets, spec=_GENE_SPEC, registry_meta_by_id=registry_meta_by_id)


def evaluate_protein_identity(
    datasets: Iterable[dict[str, Any]], *, registry_meta_by_id: dict[str, dict[str, Any] | None]
) -> Iterator[Result]:
    """C3 protein declaration-level evaluator (thin wrapper over the generalized core)."""
    yield from evaluate_tier_identity(datasets, spec=_PROTEIN_SPEC, registry_meta_by_id=registry_meta_by_id)


@Check(section="gene identity", order=27)
def check_gene_identity(ctx: ValidateContext) -> Iterator[Result]:
    yield from _run_tier_check(ctx, _GENE_SPEC)


@Check(section="protein identity", order=28)
def check_protein_identity(ctx: ValidateContext) -> Iterator[Result]:
    yield from _run_tier_check(ctx, _PROTEIN_SPEC)
```

- [ ] **Step 6: Run the protein tests AND the C2 gene tests to verify all pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_context.py -v`
Expected: all PASS — the C1 checks 1 & 3 tests, ALL the C2 gene tests (unchanged — the refactor guard), and the new protein tests. If any C2 gene test fails, the refactor changed gene behavior — STOP and fix the generalized helper (do not edit the C2 tests).

- [ ] **Step 7: Run the full validate suite (confirm registration is clean)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate -q`
Expected: PASS. (`test_checks_basic.py` asserts only the first 6 checks, so `order=28` needs no inventory update.)

- [ ] **Step 8: Ruff + commit**

```bash
cd ~/d/science/science && uv run --frozen ruff check src/science_tool/validate/checks/identity_context.py tests/validate/test_checks_identity_context.py
cd ~/d/science
git add science/src/science_tool/validate/checks/identity_context.py science/tests/validate/test_checks_identity_context.py
git commit -m "refactor(validate): generalize identity check into evaluate_tier_identity; add protein check (order=28, C3)"
```

---

## Task 6: Migration note, lint, and final C3 verification

**Files:**
- Create: `docs/migration/2026-05-27-protein-crosswalk-identity.md`

C3 makes `identity_context.molecular_ids.protein` resolvable. The migration is light: document the structured protein declaration and the resolver entry point. Like C1/C2, there is no live downstream consumer yet (the check is exercised by fixtures until a protein-bearing dataset adopts `identity_context`).

- [ ] **Step 1: Write the migration note**

Create `docs/migration/2026-05-27-protein-crosswalk-identity.md`:

````markdown
# Declaring protein identity (C3)

A dataset whose data are protein-keyed declares its protein id space via the
`bio.identity_context/1.0` extension's `molecular_ids.protein` tier:

```yaml
identity_context:
  taxon: 9606
  molecular_ids:
    protein:
      namespace: uniprot       # uniprot | uniprot_entry_name | ensembl_protein | refseq_protein
      canonical: true
      registry: dataset:protein-crosswalk-uniprot   # optional; this is the default
      resolution_status: resolved                    # or declared_unresolved (RCM-D2)
```

`science validate` (the protein check, declaration-level) verifies the namespace
is crosswalk-supported and that `registry` resolves to a `bio.protein_crosswalk/1.0`
collection (`member_key_column: protein_key`). A registry of the wrong type errors;
an unloadable one is reported INFO (cannot verify). The gene and protein checks
share one generalized core (`evaluate_tier_identity`).

Payload-level mapping (resolving the actual protein-id column of a dataset) is
**not** done by `science validate`; use the resolver:

```python
from science_tool.commons.protein_crosswalk import to_canonical
m = to_canonical(taxon=9606, namespace="uniprot", protein_id="P04217")
# -> ResolvedProteinMatch(protein_key="9606|uniprot|P04217", gene_key=("9606|hgnc|HGNC:5",), ...), or
#    AmbiguousProteinMatch(candidates=(...)) when an input maps to >1 protein, or None.
```

The canonical key is the opaque composite `"<taxon>|uniprot|<accession>"`. Each row
carries the C2 `gene_key` (protein→gene join). An isoform input (`P12345-2`) surfaces
the canonical protein with `match_type="isoform"` and the queried isoform preserved
(never collapsed). Merged secondary accessions resolve with `status="merged"` + a
`replacement_protein_key` forward pointer (never auto-followed). Shared RefSeq/Ensembl-
protein ids return `AmbiguousProteinMatch` (no single key — never guess). Multi-species
support is deferred but the API is taxon-explicit from the start.
````

- [ ] **Step 2: Ruff lint + format both packages**

```bash
cd ~/d/science/science && uv run --frozen ruff check . && uv run --frozen ruff format --check .
cd ~/d/science/science/model && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: clean for the C3 files. If `ruff format --check` reports diffs in files you created, run `uv run --frozen ruff format <file>` and re-commit. Watch for ruff A002 (`protein_id`, not `id`, is used deliberately). (Pre-existing non-C3 lint/format diffs on `main` are out of scope — only the C3 files must be clean.)

- [ ] **Step 3: Full test sweep of both packages**

```bash
cd ~/d/science/science/model && uv run --frozen pytest -q
cd ~/d/science/science && uv run --frozen pytest -q
```
Expected: PASS in both. (Note: 4 failures pre-exist on `main` and are unrelated to C3 — `test_graph_migrate`, `test_health::test_json_output` ×2, `test_tasks_blockers_json_unresolved`, all "Extra data" JSON-stdout issues. Confirm any failures are exactly these before attributing them to C3; the `science/model` package must be fully green.)

- [ ] **Step 4: Smoke-test `science validate`**

Run: `cd ~/d/science && uv run --frozen science validate --verbose` against a project (or rely on the suite). Expected: the protein check runs under section "protein identity" without raising; a dataset declaring `molecular_ids.protein` with a bad namespace surfaces `identity.protein-namespace-unsupported`. (Acceptable to rely on the Task 5 tests if no project is handy; note which in the report.)

- [ ] **Step 5: Final commit**

```bash
cd ~/d/science
git add docs/migration/2026-05-27-protein-crosswalk-identity.md
git commit -m "docs(bio): protein-crosswalk identity migration note (C3)"

# If ruff reformatted any C3 files, stage them explicitly — never `git add -A`.
git status --short
git add \
  science/src/science_tool/commons/protein_crosswalk.py \
  science/src/science_tool/commons/protein_crosswalk_build.py \
  science/src/science_tool/validate/checks/identity_context.py \
  science/tests/test_protein_crosswalk_build.py \
  science/tests/test_commons_protein_crosswalk.py \
  science/tests/validate/test_checks_identity_context.py
git commit -m "chore(c3): ruff format C3 modules" || echo "nothing to commit"
```

---

## Self-Review (completed by plan author)

**Spec coverage** (against C design §8 C3, C-D1/C-D3, decision d5, primitive RCM-D1/D2/D6):
- *Protein crosswalk as a reference collection (fourth primitive instance), UniProtKB-anchored* → Task 1 (`bio.protein_crosswalk` `member_key_column: protein_key`) + Task 2 (commons dataset + recipe + fixture) ✓
- *Species-aware `{taxon, namespace, id}` identity, UniProtKB accession anchor, entry-name/Ensembl-protein/RefSeq-protein inputs* → Task 3 (`to_canonical(*, taxon, namespace, protein_id)`, `SUPPORTED_PROTEIN_NAMESPACES`, composite `protein_key`) ✓
- *Isoforms a non-collapsed lower-level identity (d5)* → Task 3 (`match_type="isoform"` + `isoform` field; canonical surfaced, not collapsed; isoforms are not member rows) ✓
- *UniProt idmapping + secondary-accession source (C-D3, dated/immutable)* → Task 4 (parsing) + Task 2 (recipe `sources.yaml`/`build.py`) ✓
- *protein↔gene (§6)* → Task 4 (`gene_key` built from HGNC xref via `make_gene_key`) + Task 3 (`gene_key` surfaced on `ResolvedProteinMatch`) ✓
- *Declaration-level protein check* → Task 5 (`evaluate_tier_identity` generalization + `check_protein_identity` order=28; supported namespace before declared_unresolved; wrong type ERROR, unloadable INFO) ✓
- *Merged/deprecated accessions mapped-through-with-provenance, never dropped/guessed* → realized as the **resolver contract** (Task 3: `status="merged"` + `replacement_protein_key`, surfaced not auto-followed; `AmbiguousProteinMatch` for shared ids) + Task 4 (`parse_secondary`) ✓
- *RCM-D6 exact equality / never collapse distinct keys / opaque key* → Task 3 (`AmbiguousProteinMatch` has no `protein_key`; merge surfaced not followed; isoform surfaced not collapsed; `_parse_crosswalk_rows` rejects duplicate keys + merged-count mismatch; taxon gated on a parameter, key never split) ✓
- *DRY: gene + protein checks share one core* → Task 5 (`evaluate_tier_identity` + `_TierSpec`; gene rewrapped, its tests guard the refactor) ✓

**Type consistency:** `make_protein_key(taxon, accession) -> str`; `CrosswalkRow(protein_key, entry_name, ensembl_protein: tuple, refseq_protein: tuple, gene_key: tuple, status, replacement_protein_keys: tuple)`; `ResolvedProteinMatch(protein_key, entry_name, ensembl_protein, refseq_protein, gene_key, match_type, isoform, status, replacement_protein_key)`; `AmbiguousProteinMatch(query, candidates)`; `to_canonical(*, taxon, namespace, protein_id, registry_id, commons_root, data_root) -> ProteinMatch | None`; `_match_rows(rows, taxon, namespace, protein_id) -> (rows, match_type, isoform)`; constants `PROTEIN_CROSSWALK_ID`, `PROTEIN_CROSSWALK_RESOURCE`, `MEMBER_KEY_COLUMN`, `SUPPORTED_PROTEIN_NAMESPACES`, `_HUMAN_TAXON`, `_VALID_STATUS` (`approved|merged`). Build: `parse_idmapping(dat_text)`, `parse_secondary(sec_text, *, primary_keys)`, `build_rows(*, idmapping_text, secondary_text)`, `fetch_text(url)`. Check: `_TierSpec(tier, supported_namespaces, default_registry, key_column, profile_token, rule_prefix)`, `_tier_decl(fm, tier)`, `_tier_defect(decl)`, `_is_crosswalk(meta, *, profile_token, key_column)`, `evaluate_tier_identity(datasets, *, spec, registry_meta_by_id)`, `_load_registry_meta(...)` (unchanged), `_run_tier_check(ctx, spec)`, `evaluate_gene_identity`/`evaluate_protein_identity` (wrappers), `check_gene_identity` (order=27), `check_protein_identity` (order=28). Rules: `identity.gene-*` (preserved) and `identity.protein-*`.

**Two design→implementation reconciliations (deliberate):** (a) No `identity_context` schema change — C2 already generalized `molecular_ids.<tier>` to carry `registry`/`resolution_status`, so the `protein` tier validates already (one fewer task than C2). (b) The check is generalized rather than cloned (user decision): C2's `evaluate_gene_identity` becomes a wrapper over `evaluate_tier_identity`; its existing tests are the refactor guard, and every C2 rule string + message is preserved verbatim so they stay green.

**Out of scope (per C phasing):** variant/liftover (C4) tier; TrEMBL (unreviewed) proteins; isoform *member rows* (isoforms surfaced via suffix relation only); transcript (ENST) and Entrez-gene input namespaces; deleted-accession (`delac`) → withdrawn; non-human species (API is taxon-ready, data is human-only); promoting a protein to its own `member_of` dataset (no evidence-bearing protein yet); payload-level id-column auditing as a CLI; runtime cross-validation of `gene_key` against the C2 crosswalk. Populating the real UniProt crosswalk is an operator-run recipe step (network); the acceptance gate is the hermetic fixture + green tests.

---

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task with two-stage review between tasks (REQUIRED SUB-SKILL: superpowers:subagent-driven-development). Tasks are in dependency order (1→6); dispatch them in order. Implement on a `feat/c3-protein-crosswalk` branch, not `main`.
2. **Inline Execution** — execute tasks in this session with checkpoints (REQUIRED SUB-SKILL: superpowers:executing-plans).
