# Reactome Commons Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Implemented and merged locally on 2026-05-30 across `~/d/science-commons`,
`~/d/health/meta`, and `~/d/health/comparisons/pan-disease`.

**Implementation outcome:**

- Built `dataset:gene-crosswalk-hgnc` from pinned HGNC inputs (`gene_count: 49359`) and committed the
  real `crosswalk.csv` hash/bytes in `~/d/science-commons`.
- Fetched Reactome release 96 from `https://download.reactome.org/96/` (Zenodo record
  `https://zenodo.org/records/19581589`), then built and promoted `dataset:reactome` as a
  `bio.geneset` commons dataset.
- Reactome build outputs: `n_sets: 2819`; `set_size_summary: {min: 1, median: 15.0, max: 2606}`;
  resolution counts `approved: 137108`, `unresolved: 2676`, `ambiguous: 0`, `deprecated: 0`,
  `dropped_empty: 26`.
- Updated `~/d/health/meta` with the Reactome recipe, dataset overlay, and D1-aligned design doc.
- Removed the duplicate pan-disease local Reactome stub so `dataset:reactome` resolves through commons.

**Verification outcome:**

- Reactome recipe unit tests passed in `~/d/health/meta`.
- C2 gene-crosswalk tests passed in `~/d/science`.
- Targeted D1/B1/B2 Reactome-adjacent science tests and ruff checks passed.
- Full `science validate` in `~/d/health/meta` and `~/d/health/comparisons/pan-disease` still reports
  pre-existing project-wide validation backlog, but filtered Reactome checks showed no new Reactome
  unresolved-reference or code metadata defects.
- Review follow-up: gene-set member reads now fall back to the hash-verified commons data resolver when
  promoted dataset resources are not colocated next to `datapackage.yaml`, so D1 row stats can be checked
  against data-root-backed resources. The Reactome recipe also has a `--verify-entity` guard that fails if
  built `n_sets` or `set_size_summary` differs from the committed entity frontmatter.

**Remaining follow-ups:**

- The Reactome data cache and C2 gene-crosswalk data copy were placed under durable local storage at
  `~/d/science-commons-data/`, and the per-machine `reactome` and `gene-crosswalk-hgnc` data overrides
  were corrected to point there.
- D2 promoted pathway datasets, Reactome curation PMID ingestion, Reactome/MSigDB concordance, non-human
  Reactome, and non-tabular ontology support remain deferred.

**Goal:** Ingest human Reactome into `~/d/science-commons` as the first real `bio.geneset` commons dataset that exercises the implemented C/A/B/D foundation.

**Architecture:** The implementation uses the current D1 contract: `members_resource` is a CSV resource with one row per pathway and columns `set_key`, `name`, and semicolon-delimited `member_ids`. Reactome publishes Entrez-to-pathway membership, so the D1 membership table declares `identifier_space.namespace: entrez`; a separate long-form canonical panel resolves those Entrez ids through a single loaded C2 crosswalk index into `gene_key` and `symbol`. B2 is already implemented, so this pass carries row-level `dataset_usage` where Reactome source datasets are known, but does not implement D2 promoted pathway datasets.

**Tech Stack:** Python stdlib (`csv`, `hashlib`, `urllib.request`, `zipfile`/`tarfile` as needed), `pyyaml`, the local `science` package, `science_tool.commons.gene_crosswalk.load_gene_crosswalk`, commons dataset promotion/resolution commands.

---

## Current-Code Alignment

- The health/meta design at `~/d/health/meta/doc/plans/2026-05-25-reactome-commons-ingestion-design.md` is the starting point, but it must be read with this correction: D1 does **not** accept a long-form `gene_set_panel` as the collection member table. The required `members_resource` is one row per set.
- The implemented `bio.geneset` validator reads CSV rows via `science_tool.commons.geneset_resources.read_member_rows`; use CSV for the D1 members table. Auxiliary resources may also be CSV.
- The implemented gene crosswalk resolver returns an opaque `gene_key`. Do not split `gene_key` to recover `HGNC:<id>`. Use `identifier_space.namespace: entrez` for `sets.csv.member_ids`, and put `gene_key` in the auxiliary canonical panel.
- `resolution_status: resolved` means the declared Entrez member namespace has a live C2 registry and the recipe resolved the auxiliary canonical panel. It does not mean `sets.csv.member_ids` are rewritten to `gene_key`.
- Do not call `to_canonical(...)` once per Entrez id. That function reloads and hash-verifies the C2 CSV on each call. The recipe must call `load_gene_crosswalk()` once, build an in-memory Entrez index, and pass that index into pure table builders.
- `dataset:gene-crosswalk-hgnc` exists in `~/d/science-commons` with real bytes and metadata; Reactome promotion used this built C2 registry.
- The pan-disease `~/d/health/comparisons/pan-disease/doc/datasets/data-reactome.md` local pre-commons stub has been removed; child-project refs now resolve through commons.

## File Map

- Modify: `~/d/health/meta/doc/plans/2026-05-25-reactome-commons-ingestion-design.md`
  - Bring the design into line with D1/B2/C2 as implemented.
- Create: `~/d/health/meta/code/scripts/external/reactome/fetch.py`
  - Fetch pinned Reactome source files and maintain `lockfile.yaml`.
- Create: `~/d/health/meta/code/scripts/external/reactome/build.py`
  - Build normalized CSV resources under `$SCIENCE_COMMONS_DATA_ROOT/reactome/`.
- Create: `~/d/health/meta/code/scripts/external/reactome/build_datapackage.py`
  - Render `datapackage.yaml` with hashes and byte counts.
- Create: `~/d/health/meta/code/scripts/external/reactome/README.md`
  - Operator instructions for a pinned rebuild.
- Create: `~/d/health/meta/tests/test_reactome_recipe.py`
  - Pure tests for parsing, human-species filtering, C2 resolution handling, and output table shape.
- Create: `~/d/health/meta/doc/datasets/data-reactome.md`
  - Project-side dataset record used for promotion.
- Create after promotion: `~/d/science-commons/datasets/reactome/{entity.md,datapackage.yaml,recipe/...}`
  - Canonical commons dataset triplet.
- Delete after commons validation: `~/d/health/comparisons/pan-disease/doc/datasets/data-reactome.md`
  - Remove the duplicate local stub once commons resolves `dataset:reactome`.

## Task 1: Refresh The Health/Meta Design

**Files:**
- Modify: `~/d/health/meta/doc/plans/2026-05-25-reactome-commons-ingestion-design.md`

- [ ] **Step 1: Replace the stale membership decision**

Change the identifier strategy to:

```markdown
- **Identifier strategy (implemented D1 shape):** Reactome membership is published as Entrez gene ids,
  and the implemented `bio.geneset` D1 row contract requires one row per set with semicolon-delimited
  `member_ids`. The collection therefore declares `identifier_space: {tier: gene, namespace: entrez,
  registry: dataset:gene-crosswalk-hgnc, resolution_status: resolved}`. Here `resolved` means the Entrez
  namespace resolves against a live C2 registry; the D1 member ids remain Entrez. The recipe resolves each
  Entrez id through a one-pass C2 index at build time and writes the canonical `gene_key` + display `symbol`
  into the auxiliary `gene_set_panel` resource. `gene_key` remains opaque and is never split to recover an
  HGNC id.
```

- [ ] **Step 2: Replace the resource list**

Use this resource list:

```markdown
1. **`sets`** — the D1 `members_resource`. CSV with one row per retained human pathway:
   `set_key`, `name`, `member_ids`, `source_pmids`, `dataset_usage`. `member_ids` is a semicolon-delimited
   list of retained Entrez ids whose C2 resolution was unique and approved. A pathway with zero retained
   ids is excluded from `sets` and counted in `resolution_report` as `dropped_empty`. `source_pmids` is
   empty in the first pass. `dataset_usage` is empty in the first pass; when populated later it must be a
   JSON array string such as `[{ "ref": "dataset:study-a", "role": "set_definition_source",
   "overlap": "full" }]`, matching the D1 parser. The canonical collection is faithful and does not apply
   enrichment-style size filters; consumers can apply 5-500 or other windows at analysis time.
2. **`ncbi_gene_pathway`** — faithful normalized CSV mirror of the human rows from
   `NCBI2Reactome_All_Levels.txt`: `entrez_id`, `pathway_id`, `pathway_url`, `pathway_name`,
   `evidence_code`, `species`.
3. **`pathways`** — human pathway catalog CSV: `set_key`, `name`, `species`, `is_top_level`.
4. **`pathway_relations`** — human pathway hierarchy CSV: `parent_pathway_id`, `child_pathway_id`.
5. **`gene_set_panel`** — long-form canonical CSV for analysis: `set_key`, `name`, `entrez_id`,
   `gene_key`, `symbol`, `match_type`.
6. **`resolution_report`** — CSV counts by `set_key`: `approved`, `unresolved`, `ambiguous`,
   `deprecated`, `retained`, and `dropped_empty`.
```

- [ ] **Step 3: Replace parquet references with CSV**

Search:

```bash
rtk rg -n "parquet|hgnc_id|identifier_space: hgnc|gene_set_panel.pathway_id" doc/plans/2026-05-25-reactome-commons-ingestion-design.md
```

Expected after edits: no `parquet`, no `identifier_space: hgnc`, and no claim that the D1 member table is long-form.

- [ ] **Step 4: Commit**

```bash
rtk git add doc/plans/2026-05-25-reactome-commons-ingestion-design.md
rtk git commit -m "docs: align Reactome plan with D1 geneset contract"
```

## Task 2: Ensure The C2 Gene Crosswalk Is Built

**Files:**
- Modify if placeholder: `~/d/science-commons/datasets/gene-crosswalk-hgnc/crosswalk.csv`
- Modify if placeholder: `~/d/science-commons/datasets/gene-crosswalk-hgnc/datapackage.yaml`
- Modify if placeholder: `~/d/science-commons/datasets/gene-crosswalk-hgnc/entity.md`

- [ ] **Step 1: Check whether C2 is still placeholder**

```bash
rtk rg -n "sha256:0000000000000000000000000000000000000000000000000000000000000000|gene_count: 0|bytes: 0" ~/d/science-commons/datasets/gene-crosswalk-hgnc
```

Expected if already built: no output. If there is output, continue this task before Reactome.

- [ ] **Step 2: Build the crosswalk from its pinned sources**

Run from the dataset directory:

```bash
cd ~/d/science-commons/datasets/gene-crosswalk-hgnc
rtk uv run --frozen --project ~/d/science/science python recipe/build.py
```

Expected: `wrote <N> rows to .../crosswalk.csv`, with `N > 0`.

- [ ] **Step 3: Update hash, bytes, and gene count**

Use the science helper rather than ad hoc hashing:

```bash
cd ~/d/science-commons/datasets/gene-crosswalk-hgnc
rtk uv run --frozen --project ~/d/science/science python -c "from pathlib import Path; from science_tool.commons.datapackage import stream_sha256_and_bytes; p=Path('crosswalk.csv'); h,b=stream_sha256_and_bytes(p); n=sum(1 for _ in p.open(encoding='utf-8'))-1; print(h); print(b); print(n)"
```

Edit `datapackage.yaml` so the `crosswalk.csv` resource has the printed `hash` and `bytes`. Edit
`entity.md` so `gene_count` is the printed row count.

- [ ] **Step 4: Verify C2 resolution works**

```bash
cd ~/d/science
rtk uv run --frozen --project science pytest science/tests/test_commons_gene_crosswalk.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science-commons
rtk git add datasets/gene-crosswalk-hgnc
rtk git commit -m "data: build HGNC gene crosswalk"
```

## Task 3: Write Recipe Unit Tests

**Files:**
- Create: `~/d/health/meta/tests/test_reactome_recipe.py`

- [ ] **Step 1: Add tests for pure build helpers**

Create tests covering these fixtures:

```python
NCBI_ROWS = [
    ["101", "R-HSA-1", "https://reactome.org/content/detail/R-HSA-1", "Cell cycle", "IEA", "Homo sapiens"],
    ["102", "R-HSA-1", "https://reactome.org/content/detail/R-HSA-1", "Cell cycle", "TAS", "Homo sapiens"],
    ["104", "R-HSA-2", "https://reactome.org/content/detail/R-HSA-2", "Signal transduction", "TAS", "Homo sapiens"],
    ["105", "R-HSA-3", "https://reactome.org/content/detail/R-HSA-3", "Empty after resolution", "TAS", "Homo sapiens"],
    ["103", "R-MMU-1", "https://reactome.org/content/detail/R-MMU-1", "Mouse pathway", "TAS", "Mus musculus"],
]

PATHWAY_ROWS = [
    ["R-HSA-1", "Cell cycle", "Homo sapiens"],
    ["R-HSA-2", "Signal transduction", "Homo sapiens"],
    ["R-HSA-3", "Empty after resolution", "Homo sapiens"],
    ["R-MMU-1", "Mouse pathway", "Mus musculus"],
]

RELATION_ROWS = [["R-HSA-2", "R-HSA-1"], ["R-MMU-1", "R-HSA-1"]]
```

Assert:

- non-human rows are filtered;
- `sets` has one row per retained pathway;
- `sets.member_ids` is semicolon-delimited Entrez ids;
- `gene_set_panel` carries `gene_key` and `symbol`;
- unresolved, ambiguous, and deprecated Entrez ids are counted in `resolution_report`, not silently dropped;
- pathways with zero retained approved Entrez ids are excluded from `sets` and counted as `dropped_empty`;
- the computed `n_sets` and `set_size_summary` object (`min`, `median`, `max`) match the `sets` rows.

Use an injected fake resolver/index in the tests. Do not depend on the real commons C2 files for these unit
tests. A minimal fixture can be:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from scripts.external.reactome.build import GeneResolution

GENE_INDEX = {
    "101": GeneResolution(status="approved", gene_key="9606|hgnc|HGNC:101", symbol="GENE101", match_type="exact"),
    "102": GeneResolution(status="ambiguous"),
    "104": GeneResolution(status="deprecated"),
}
```

In this fixture, `R-HSA-1` is retained with `member_ids == "101"`, while `R-HSA-2` and `R-HSA-3` are
excluded from `sets` and reported as `dropped_empty`.

- [ ] **Step 2: Run the tests and confirm failure**

```bash
cd ~/d/health/meta
rtk uv run --with pytest pytest tests/test_reactome_recipe.py -q
```

Expected: FAIL because `code/scripts/external/reactome/build.py` does not exist.

## Task 4: Implement `build.py`

**Files:**
- Create: `~/d/health/meta/code/scripts/external/reactome/build.py`

- [ ] **Step 1: Implement pure table builders**

Expose pure functions with these names so tests can import them:

```python
def normalize_ncbi_rows(rows: list[list[str]]) -> list[dict[str, str]]: ...
def normalize_pathways(rows: list[list[str]], relations: list[list[str]]) -> list[dict[str, str]]: ...
def normalize_relations(rows: list[list[str]], pathway_ids: set[str]) -> list[dict[str, str]]: ...
def build_gene_index(crosswalk_rows: list[CrosswalkRow]) -> dict[str, GeneResolution]: ...
def build_reactome_tables(..., gene_index: Mapping[str, GeneResolution]) -> ReactomeTables: ...
def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None: ...
```

Define the local result types in `build.py`:

```python
from dataclasses import dataclass
from typing import Literal

ResolutionStatus = Literal["approved", "unresolved", "ambiguous", "deprecated"]

@dataclass(frozen=True, slots=True)
class GeneResolution:
    status: ResolutionStatus
    gene_key: str = ""
    symbol: str = ""
    match_type: str = ""

@dataclass(frozen=True, slots=True)
class ReactomeTables:
    sets: list[dict[str, str]]
    ncbi_gene_pathway: list[dict[str, str]]
    pathways: list[dict[str, str]]
    pathway_relations: list[dict[str, str]]
    gene_set_panel: list[dict[str, str]]
    resolution_report: list[dict[str, str]]
    summary: dict[str, object]
```

`build_gene_index` must group non-blank C2 `CrosswalkRow.entrez_id` values in memory:

- no entry for an Entrez id means `unresolved`;
- more than one row for an Entrez id means `ambiguous`;
- exactly one row with `status == "split"` means `ambiguous`, matching `to_canonical`'s no-guess behavior;
- exactly one row with `status == "approved"` means `approved`;
- exactly one row with any other status means `deprecated`.

The CLI path loads C2 once:

```python
from science_tool.commons.gene_crosswalk import load_gene_crosswalk

gene_index = build_gene_index(load_gene_crosswalk())
tables = build_reactome_tables(..., gene_index=gene_index)
```

`build_reactome_tables` must never call `to_canonical(...)` in a per-id loop. Accept only `approved`
resolutions into `sets.member_ids` and `gene_set_panel`; exclude any pathway with zero retained members from
`sets`; include that pathway in `resolution_report` with `dropped_empty: 1`.

- [ ] **Step 2: Implement the CLI**

The CLI reads source files from `$SCIENCE_COMMONS_DATA_ROOT/reactome/_src/` unless `--source-dir` is
provided, writes CSV outputs to `$SCIENCE_COMMONS_DATA_ROOT/reactome/` unless `--output-dir` is provided,
and writes `build-summary.yaml` with this explicit shape:

```yaml
n_sets: 1234
set_size_summary:
  min: 5
  median: 42.0
  max: 500
resolution_counts:
  approved: 12000
  unresolved: 42
  ambiguous: 3
  deprecated: 7
  dropped_empty: 12
```

- [ ] **Step 3: Run tests**

```bash
cd ~/d/health/meta
rtk uv run --with pytest pytest tests/test_reactome_recipe.py -q
```

Expected: PASS.

## Task 5: Implement Fetch And Datapackage Rendering

**Files:**
- Create: `~/d/health/meta/code/scripts/external/reactome/fetch.py`
- Create: `~/d/health/meta/code/scripts/external/reactome/build_datapackage.py`
- Create: `~/d/health/meta/code/scripts/external/reactome/README.md`

- [ ] **Step 1: Implement `fetch.py`**

`fetch.py` should:

- accept `--release`, `--base-url`, and `--output-dir`;
- require either an existing `lockfile.yaml` or an explicit release/base URL on first run;
- reject mutable Reactome convenience URLs such as `download/current/`; `--base-url` must point at an archived release URL, with lockfile sha256 values as the integrity backstop;
- download `NCBI2Reactome_All_Levels.txt`, `ReactomePathways.txt`, and `ReactomePathwaysRelation.txt`;
- write sha256 values and source URLs into `lockfile.yaml`;
- on later runs, reuse `lockfile.yaml` and verify hashes.

- [ ] **Step 2: Implement `build_datapackage.py`**

Use `science_tool.commons.datapackage.stream_sha256_and_bytes` to render resources:

```yaml
resources:
  - name: sets
    path: sets.csv
    format: csv
    mediatype: text/csv
  - name: ncbi_gene_pathway
    path: ncbi_gene_pathway.csv
    format: csv
    mediatype: text/csv
  - name: pathways
    path: pathways.csv
    format: csv
    mediatype: text/csv
  - name: pathway_relations
    path: pathway_relations.csv
    format: csv
    mediatype: text/csv
  - name: gene_set_panel
    path: gene_set_panel.csv
    format: csv
    mediatype: text/csv
  - name: resolution_report
    path: resolution_report.csv
    format: csv
    mediatype: text/csv
```

Each rendered resource must include `hash` and `bytes`.

- [ ] **Step 3: Document the operator flow**

`README.md` should show:

```bash
cd ~/d/health/meta
rtk uv run --frozen python code/scripts/external/reactome/fetch.py --release <release> --base-url <archived-release-url>
rtk uv run --frozen python code/scripts/external/reactome/build.py
rtk uv run --frozen python code/scripts/external/reactome/build_datapackage.py
```

The README must state that `download/current/` is discovery-only and must not be used as `--base-url`.

## Task 6: Create The Health/Meta Dataset Record

**Files:**
- Create: `~/d/health/meta/doc/datasets/data-reactome.md`

- [ ] **Step 1: Add the entity frontmatter**

Use this shape after the recipe writes `build-summary.yaml`:

```yaml
---
schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0
id: dataset:reactome
type: dataset
title: Reactome human pathway gene-set collection
status: active
origin: external
source_class: reference
tier: use-now
datapackage: code/scripts/external/reactome/datapackage.yaml
access:
  level: public
  availability: available
  verified: true
  verification_method: retrieved
member_key_column: set_key
members_resource: sets
n_sets: <from build-summary.yaml>
set_size_summary:
  min: <from build-summary.yaml set_size_summary.min>
  median: <from build-summary.yaml set_size_summary.median>
  max: <from build-summary.yaml set_size_summary.max>
identifier_space:
  tier: gene
  namespace: entrez
  registry: dataset:gene-crosswalk-hgnc
  resolution_status: resolved
created: "2026-05-30"
updated: "2026-05-30"
---
```

The body should say Reactome is a curated reference collection, Entrez-keyed at the D1 member surface, with
canonical C2 `gene_key` resolution in `gene_set_panel.csv`.

- [ ] **Step 2: Validate health/meta**

```bash
cd ~/d/health/meta
rtk uv run --frozen science validate --verbose
```

Expected: no new Reactome-related errors.

## Task 7: Build, Promote, And Verify Commons Reactome

**Files:**
- Create: `~/d/science-commons/datasets/reactome/entity.md`
- Create: `~/d/science-commons/datasets/reactome/datapackage.yaml`
- Create: `~/d/science-commons/datasets/reactome/recipe/...`
- Create data files under `$SCIENCE_COMMONS_DATA_ROOT/reactome/`

- [ ] **Step 1: Run the recipe**

```bash
cd ~/d/health/meta
rtk uv run --frozen python code/scripts/external/reactome/fetch.py --release <release> --base-url <archived-release-url>
rtk uv run --frozen python code/scripts/external/reactome/build.py
rtk uv run --frozen python code/scripts/external/reactome/build_datapackage.py
```

- [ ] **Step 2: Promote the dataset**

```bash
cd ~/d/health/meta
rtk uv run --frozen science commons promote dataset --from meta --slug reactome --mixin bio.geneset
rtk uv run --frozen science commons promote dataset --from meta --slug reactome --mixin bio.geneset --apply
```

- [ ] **Step 3: Copy the real recipe into commons**

Copy `code/scripts/external/reactome/` into `~/d/science-commons/datasets/reactome/recipe/`, preserving
`lockfile.yaml`.

- [ ] **Step 4: Resolve data**

```bash
cd ~/d/science
rtk uv run --frozen --project science science commons data resolve dataset:reactome sets.csv
rtk uv run --frozen --project science science commons data resolve dataset:reactome gene_set_panel.csv
```

Expected: both commands print hash-verified absolute paths.

- [ ] **Step 5: Commit commons**

```bash
cd ~/d/science-commons
rtk git add datasets/reactome
rtk git commit -m "data: add Reactome geneset collection"
```

## Task 8: Remove The Pan-Disease Local Stub

**Files:**
- Delete: `~/d/health/comparisons/pan-disease/doc/datasets/data-reactome.md`

- [ ] **Step 1: Delete the duplicate local entity**

After commons `dataset:reactome` resolves, remove the pan-disease stub so child-project refs use the shared
commons dataset.

- [ ] **Step 2: Validate pan-disease refs**

```bash
cd ~/d/health/comparisons/pan-disease
rtk uv run --frozen science validate --verbose
```

Expected: no unresolved `dataset:reactome` refs.

- [ ] **Step 3: Commit pan-disease**

```bash
cd ~/d/health/comparisons/pan-disease
rtk git add doc/datasets/data-reactome.md
rtk git commit -m "docs: rely on commons Reactome dataset"
```

## Task 9: Final Verification

Run:

```bash
cd ~/d/health/meta
rtk uv run --frozen science validate --verbose

cd ~/d/health/comparisons/pan-disease
rtk uv run --frozen science validate --verbose

cd ~/d/science
rtk uv run --frozen --project science pytest science/tests/test_commons_geneset.py science/tests/validate/test_checks_genesets.py science/tests/test_dataset_usage_materialize.py science/tests/test_dataset_independence.py -q
rtk uv run --frozen --project science ruff check science/src/science_tool/commons/geneset.py science/src/science_tool/validate/checks/genesets.py

cd ~/d/science-commons
rtk git status --short
```

Expected:

- health/meta validation has no new Reactome defects;
- pan-disease validation resolves `dataset:reactome` through commons;
- science regression tests pass;
- science-commons has only the intentional Reactome/C2 data changes before commit, and is clean after commit.

## Self-Review Notes

- **Spec coverage:** The plan covers D1 members-resource shape, C2 resolution, B row-level provenance hooks,
  commons promotion, Health project compatibility, and pan-disease stub migration.
- **Review corrections incorporated:** C2 is loaded once into an in-memory Entrez index; pure tests inject a
  fake `GeneResolution` index; zero-retained pathways are excluded from `sets`; the canonical collection
  does not apply enrichment-style size filters; `set_size_summary` is the explicit `{min, median, max}`
  object; `dataset_usage` remains a JSON array string; archived Reactome URLs are required for fetches.
- **Resolved blocker:** Reactome promotion required a built `dataset:gene-crosswalk-hgnc`; that C2
  registry is now built and pinned.
- **Deferred:** D2 promoted pathway datasets, Reactome curation PMID ingestion, Reactome/MSigDB concordance,
  non-human Reactome, and non-tabular ontology support.
