# Bio Identity P5 MM30/t665 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the bio identity adoption layer on MM30's t665 mixed-build cytoband-proxy workflow, while creating the migration scaffold needed for the wider MM30 backlog.

**Architecture:** `~/d/science` owns this cross-repo coordination plan. The implementation work happens in an isolated MM30 worktree, using the already-merged Science CLI and the P4 commons artifacts. P5a lands a narrow t665 vertical slice; P5b lands inventory/reporting and migration-window policy; P5c is intentionally gated on review of the P5a/P5b results.

**Tech Stack:** Python 3.12, pytest, YAML frontmatter, Science CLI (`science dataset identity resolve|show|suggest`, `science dataset register-run`, `science validate`), Snakemake, `~/d/science-commons` pinned data artifacts.

---

## Preconditions

- This plan lives in `~/d/science/.worktrees/bio-identity-p5-mm30-replan`.
- Execute implementation in a new MM30 worktree, not the dirty MM30 `main` checkout.
- Use `~/d/` paths in docs and commands. Do not write machine-specific absolute checkout paths into repo files.
- Use both commons roots for resolver commands:

```bash
export SCIENCE_COMMONS_ROOT=~/d/science-commons
export SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data
```

- Do not use live MyGene, Ensembl REST, UCSC, or other network lookup for identity resolution.
- Do not resolve `hg19` to the current NCBI `GRCh37` row or `hg38` to the current NCBI `GRCh38` row unless an exact row-bound registry alias supports that source.
- Keep MM30 unrelated dirty files untouched.

## File Structure

`~/d/science`:

- `docs/plans/2026-07-03-bio-identity-p5-mm30-t665-design.md` - completed design/spec.
- `docs/plans/2026-07-03-bio-identity-p5-mm30-t665-implementation-plan.md` - this plan.
- `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md` - update only after P5a/P5b lands.

MM30 worktree:

- `entities/datasets/gse131651-shah2019-nsd2.md` - add entity-authoritative human taxon, hg38 assembly declaration, and gene namespace declaration.
- `entities/datasets/gse87585-wu2017.md` - add entity-authoritative human taxon and hg19 assembly declaration.
- `entities/workflows/gse131651-3d-locus-ledger.md` - add `outputs[].identity` structured cytoband proxy contract.
- `scripts/shared/datapackage.py` - ensure hardcoded `species` / `taxonomy_id` are not treated as biological identity authority; preserve old `mm30` descriptive fields if existing consumers require them.
- `doc/reports/bio-identity-p5-migration-report.md` - add the P5a/P5b adoption report.
- `tests/` - add focused tests for t665 identity metadata, resolver preflight behavior, and datapackage helper behavior.

Generated / runtime surfaces:

- t665 output datapackage under `results/gse131651-3d-locus-ledger/$RUN_ID/datapackage.yaml` - must exist before registration can write the derived stamp.
- derived dataset entity minted or updated by `science dataset register-run` - should carry the t665 output `identity_context`.

## Task 1: Create MM30 Worktree And Baseline Evidence

**Files:**
- No file edits; this task records baseline state.

- [ ] **Step 1: Create an isolated MM30 worktree**

Run from the MM30 repository root:

```bash
mkdir -p .worktrees
git worktree add .worktrees/bio-identity-p5-t665 -b bio-identity-p5-t665
```

Expected: a new worktree exists at `.worktrees/bio-identity-p5-t665` under the MM30 repository root.

- [ ] **Step 2: Define shared shell variables for this session**

Run from the MM30 worktree:

```bash
export MM30_WORKTREE="$PWD"
export SCIENCE_COMMONS_ROOT=~/d/science-commons
export SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data
```

Expected: no output.

- [ ] **Step 3: Confirm MM30 worktree cleanliness**

Run from the MM30 worktree:

```bash
git status --short
```

Expected: no output. If there is output, stop and resolve the worktree setup before editing.

- [ ] **Step 4: Capture current t665 identity absence**

Run from the MM30 worktree:

```bash
rg -n "identity_context|science.identity_context|outputs:|gse131651|gse87585|hg19|hg38|taxonomy_id|Homo sapiens" \
  entities/datasets/gse131651-shah2019-nsd2.md \
  entities/datasets/gse87585-wu2017.md \
  entities/workflows/gse131651-3d-locus-ledger.md \
  scripts/shared/datapackage.py \
  workflows/stages/three_d_genome.smk \
  scripts/analyses/t665_gse131651_3d_locus_ledger.py
```

Expected: current prose/config/script references are visible, and no `identity_context` block exists on the two source dataset entities or the workflow output.

- [ ] **Step 5: Run a baseline focused validation**

Run from `~/d/science` or the Science worktree with the MM30 worktree selected:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen science validate --project-root "$MM30_WORKTREE" --format text
```

Expected: record the current warnings/errors. Pre-existing unrelated failures may be present; touched t665 identity errors must not be accepted silently during final validation.

- [ ] **Step 6: Commit nothing**

This task is evidence-gathering only. Do not commit.

## Task 2: Prove Resolver Preflight Is Reading Commons Bytes

**Files:**
- Create: `tests/test_bio_identity_p5_preflight.py`

- [ ] **Step 1: Add a focused positive-control test**

Create `tests/test_bio_identity_p5_preflight.py` with this content:

```python
from __future__ import annotations

import os
from pathlib import Path

from science_tool.commons.identity_resolve import resolve_assembly_label


def test_science_commons_assembly_registry_positive_control() -> None:
    commons_root = Path(os.environ["SCIENCE_COMMONS_ROOT"]).expanduser()
    data_root = Path(os.environ["SCIENCE_COMMONS_DATA_ROOT"]).expanduser()

    digest = resolve_assembly_label(
        "GRCh38",
        "dataset:assembly-registry",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert digest == "XemD97fxYMS4q-FBm_n5CHQgmzh1_67a"


def test_current_registry_does_not_resolve_hg19_alias() -> None:
    commons_root = Path(os.environ["SCIENCE_COMMONS_ROOT"]).expanduser()
    data_root = Path(os.environ["SCIENCE_COMMONS_DATA_ROOT"]).expanduser()

    digest = resolve_assembly_label(
        "hg19",
        "dataset:assembly-registry",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert digest is None
```

- [ ] **Step 2: Run the positive-control tests**

Run from the MM30 worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py -q
```

Expected: both tests pass. If `GRCh38` does not resolve, stop; the commons data root is misconfigured or the P4 artifact is missing.

- [ ] **Step 3: Confirm the false-positive failure mode**

Run from the MM30 worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=/tmp/missing-science-commons-data \
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py::test_science_commons_assembly_registry_positive_control -q
```

Expected: the test fails because `GRCh38` does not resolve. This proves the positive control catches misconfigured data roots.

- [ ] **Step 4: Re-run with the correct roots**

Run from the MM30 worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_bio_identity_p5_preflight.py
git commit -m "Test bio identity resolver preflight"
```

## Task 3: Add t665 Source Dataset Identity Declarations

**Files:**
- Modify: `entities/datasets/gse131651-shah2019-nsd2.md`
- Modify: `entities/datasets/gse87585-wu2017.md`
- Modify: `tests/test_bio_identity_p5_preflight.py`

- [ ] **Step 1: Extend tests for source entity identity**

Append these tests to `tests/test_bio_identity_p5_preflight.py`:

```python
import yaml


def _frontmatter(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    assert text.startswith("---")
    return yaml.safe_load(text.split("---", 2)[1])


def test_gse131651_declares_human_hg38_identity() -> None:
    frontmatter = _frontmatter("entities/datasets/gse131651-shah2019-nsd2.md")
    identity = frontmatter["identity_context"]

    assert identity["taxon"] == 9606
    assert identity["assembly"] == {
        "label": "hg38",
        "registry": "dataset:assembly-registry",
        "resolution_status": "declared_unresolved",
        "seqcol_digest": "UNKNOWN",
    }
    assert identity["molecular_ids"]["gene"] == {
        "namespace": "hgnc_symbol",
        "registry": "dataset:gene-crosswalk-hgnc",
        "resolution_status": "resolved",
    }


def test_gse87585_declares_human_hg19_identity() -> None:
    frontmatter = _frontmatter("entities/datasets/gse87585-wu2017.md")
    identity = frontmatter["identity_context"]

    assert identity["taxon"] == 9606
    assert identity["assembly"] == {
        "label": "hg19",
        "registry": "dataset:assembly-registry",
        "resolution_status": "declared_unresolved",
        "seqcol_digest": "UNKNOWN",
    }
```

- [ ] **Step 2: Run tests and verify they fail**

Run from the MM30 worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py::test_gse131651_declares_human_hg38_identity tests/test_bio_identity_p5_preflight.py::test_gse87585_declares_human_hg19_identity -q
```

Expected: both tests fail with missing `identity_context`.

- [ ] **Step 3: Add identity to `gse131651-shah2019-nsd2.md`**

Add this frontmatter block after `id: dataset:gse131651-shah2019-nsd2`:

```yaml
identity_context:
  taxon: 9606
  assembly:
    label: hg38
    registry: dataset:assembly-registry
    resolution_status: declared_unresolved
    seqcol_digest: UNKNOWN
  molecular_ids:
    gene:
      namespace: hgnc_symbol
      registry: dataset:gene-crosswalk-hgnc
      resolution_status: resolved
```

- [ ] **Step 4: Add identity to `gse87585-wu2017.md`**

Add this frontmatter block after `id: dataset:gse87585-wu2017`:

```yaml
identity_context:
  taxon: 9606
  assembly:
    label: hg19
    registry: dataset:assembly-registry
    resolution_status: declared_unresolved
    seqcol_digest: UNKNOWN
```

- [ ] **Step 5: Run focused source identity tests**

Run from the MM30 worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 6: Confirm `science dataset identity show` reads the declarations**

Run from `~/d/science` or the Science worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen science dataset identity show dataset:gse131651-shah2019-nsd2 --project-root "$MM30_WORKTREE"
```

Expected: output includes `taxon: 9606`, `label: hg38`, and `resolution_status: declared_unresolved`.

Then run:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen science dataset identity show dataset:gse87585-wu2017 --project-root "$MM30_WORKTREE"
```

Expected: output includes `taxon: 9606`, `label: hg19`, and `resolution_status: declared_unresolved`.

- [ ] **Step 7: Commit**

```bash
git add entities/datasets/gse131651-shah2019-nsd2.md entities/datasets/gse87585-wu2017.md tests/test_bio_identity_p5_preflight.py
git commit -m "Declare t665 source dataset identity"
```

## Task 4: Add t665 Workflow Output Identity Contract

**Files:**
- Modify: `entities/workflows/gse131651-3d-locus-ledger.md`
- Modify: `tests/test_bio_identity_p5_preflight.py`

- [ ] **Step 1: Add workflow identity tests**

Append this test to `tests/test_bio_identity_p5_preflight.py`:

```python
def test_gse131651_workflow_declares_cytoband_proxy_output_identity() -> None:
    frontmatter = _frontmatter("entities/workflows/gse131651-3d-locus-ledger.md")
    outputs = frontmatter["outputs"]
    output = next(item for item in outputs if item["slug"] == "gse131651-3d-locus-ledger")
    identity = output["identity"]

    assert identity["taxon"] == 9606
    assert identity["assembly"]["label"] == "mixed-build-cytoband-proxy"
    assert identity["assembly"]["resolution_status"] == "declared_unresolved"
    assert identity["assembly"]["seqcol_digest"] == "UNKNOWN"
    assert identity["assembly"]["proxy"] == {
        "type": "cytoband_proxy",
        "via": "dataset:cytoband-hg19",
        "sources": [
            {"dataset": "dataset:gse131651-shah2019-nsd2", "assembly": "inherit"},
            {"dataset": "dataset:gse87585-wu2017", "assembly": "inherit"},
        ],
    }
    assert identity["molecular_ids"]["gene"]["namespace"] == "hgnc_symbol"
    assert identity["molecular_ids"]["gene"]["registry"] == "dataset:gene-crosswalk-hgnc"
    assert identity["molecular_ids"]["gene"]["resolution_status"] == "resolved"
```

- [ ] **Step 2: Run test and verify it fails**

Run from the MM30 worktree:

```bash
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py::test_gse131651_workflow_declares_cytoband_proxy_output_identity -q
```

Expected: fail with missing `identity`.

- [ ] **Step 3: Add output identity contract**

In `entities/workflows/gse131651-3d-locus-ledger.md`, add this block under the existing output item, next to `resource_names`:

```yaml
  identity:
    taxon: 9606
    assembly:
      label: mixed-build-cytoband-proxy
      registry: dataset:assembly-registry
      resolution_status: declared_unresolved
      seqcol_digest: UNKNOWN
      proxy:
        type: cytoband_proxy
        via: dataset:cytoband-hg19
        sources:
        - dataset: dataset:gse131651-shah2019-nsd2
          assembly: inherit
        - dataset: dataset:gse87585-wu2017
          assembly: inherit
    molecular_ids:
      gene:
        namespace: hgnc_symbol
        registry: dataset:gene-crosswalk-hgnc
        resolution_status: resolved
```

Do not add `transform.from: input` in this task. The current t665 output contract only needs the gene namespace/tier declaration; per-symbol remap provenance belongs in a separate reviewed slice after the implementation identifies a concrete source dataset and transform target. This avoids introducing a multi-input `from: input` validation error.

- [ ] **Step 4: Run focused workflow test**

Run from the MM30 worktree:

```bash
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py::test_gse131651_workflow_declares_cytoband_proxy_output_identity -q
```

Expected: pass.

- [ ] **Step 5: Run all P5 preflight tests**

Run from the MM30 worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add entities/workflows/gse131651-3d-locus-ledger.md tests/test_bio_identity_p5_preflight.py
git commit -m "Declare t665 proxy output identity"
```

## Task 5: Register The Real t665 Derived Output

**Files:**
- Create if absent, using a real run id: `entities/workflow-runs/gse131651-3d-locus-ledger-$RUN_ID.md`
- Modify if generated by `science dataset register-run`: `entities/datasets/gse131651-3d-locus-ledger-$RUN_ID-gse131651-3d-locus-ledger.md`
- Do not add bulk runtime output directories in this task.

- [ ] **Step 1: Find a completed t665 runtime output**

Run from the MM30 worktree:

```bash
find results/gse131651-3d-locus-ledger -maxdepth 2 -name datapackage.yaml -print
```

Expected: at least one path like `results/gse131651-3d-locus-ledger/$RUN_ID/datapackage.yaml`.

If no datapackage is present, stop Task 5 and record this as a gated runtime-output blocker in Task 7's report. Do not run `science dataset register-run` against a synthetic workflow-run entity. The command is not a dry run; it requires `results/gse131651-3d-locus-ledger/$RUN_ID/datapackage.yaml` and the resource files named by the aggregate datapackage to exist on disk.

- [ ] **Step 2: Verify the aggregate datapackage contains declared resources**

Set `RUN_ID` to the newest real directory name found in Step 1:

```bash
export RUN_DATAPACKAGE="$(find results/gse131651-3d-locus-ledger -maxdepth 2 -name datapackage.yaml -print | sort | tail -n 1)"
export RUN_ID="$(basename "$(dirname "$RUN_DATAPACKAGE")")"
test -n "$RUN_ID"
python - <<'PY'
from pathlib import Path
import yaml

run_root = Path("results/gse131651-3d-locus-ledger") / Path(__import__("os").environ["RUN_ID"])
dp = yaml.safe_load((run_root / "datapackage.yaml").read_text())
resources = {resource["name"]: resource for resource in dp.get("resources", [])}
required = {
    "gse131651_locus_ledger",
    "gse131651_track_inventory",
    "gse131651_question_crosswalk",
}
missing = sorted(required - resources.keys())
if missing:
    raise SystemExit(f"missing resources in aggregate datapackage: {missing}")
for name in sorted(required):
    path = run_root / resources[name]["path"]
    if not path.exists():
        raise SystemExit(f"resource {name} missing file: {path}")
print(f"verified t665 aggregate datapackage for run {run_root.name}")
PY
```

Expected: prints `verified t665 aggregate datapackage for run $RUN_ID`.

- [ ] **Step 3: Find or create matching workflow-run entity**

The run entity slug must be `gse131651-3d-locus-ledger-$RUN_ID`, because `register-run` maps that slug to `results/gse131651-3d-locus-ledger/$RUN_ID/`.

Check for an existing entity:

```bash
ls "entities/workflow-runs/gse131651-3d-locus-ledger-$RUN_ID.md"
```

If the file does not exist, create `entities/workflow-runs/gse131651-3d-locus-ledger-$RUN_ID.md`:

```yaml
---
type: workflow-run
id: workflow-run:gse131651-3d-locus-ledger-RUN_ID
title: GSE131651 3D locus ledger RUN_ID
status: active
created: '2026-07-03'
updated: '2026-07-03'
workflow: workflow:gse131651-3d-locus-ledger
inputs:
- dataset:gse131651-shah2019-nsd2
- dataset:gse87585-wu2017
---

# GSE131651 3D locus ledger RUN_ID

This run registers the real t665 runtime output at `results/gse131651-3d-locus-ledger/RUN_ID/`.
```

Replace both `RUN_ID` occurrences in the file content with the actual `$RUN_ID` value.

- [ ] **Step 4: Run register-run**

Run from `~/d/science` or the Science worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen science dataset register-run "workflow-run:gse131651-3d-locus-ledger-$RUN_ID" --project-root "$MM30_WORKTREE"
```

Expected: the command creates or updates the derived t665 dataset entity and per-output datapackage. If it reports `run-aggregate datapackage not found` or a missing resource file, return to Steps 1-2; do not patch frontmatter to bypass missing runtime files.

- [ ] **Step 5: Inspect generated derivation routing**

Run from the MM30 worktree:

```bash
rg -n "dataset:cytoband-hg19|dataset:gse131651-shah2019-nsd2|dataset:gse87585-wu2017|identity_context|science.identity_context|proxy_via" entities data results outputs -S
```

Expected:

- `dataset:gse131651-shah2019-nsd2` and `dataset:gse87585-wu2017` appear as data ancestors / derivation inputs for the derived t665 output.
- `dataset:cytoband-hg19` appears as transformation/reference proxy machinery, not as a data ancestor.
- the derived dataset entity has `identity_context`.
- the derived datapackage has `science.identity_context`.

- [ ] **Step 6: Commit register-run metadata**

```bash
git status --short
git add entities/workflow-runs entities/datasets
git commit -m "Register t665 identity-bearing output"
```

If generated runtime output directories are intentionally untracked or too large, leave them untracked. Commit only the tracked entity/datapackage metadata required by the project convention and record skipped generated paths in the P5a adoption report from Task 7.

## Task 6: Prevent Datapackage Helper From Owning Science Identity

**Files:**
- Modify: `scripts/shared/datapackage.py`
- Test: `tests/test_bio_identity_datapackage_helper.py`

- [ ] **Step 1: Add a regression test that the helper does not emit the Science stamp**

Create `tests/test_bio_identity_datapackage_helper.py`:

```python
from __future__ import annotations

from scripts.shared.datapackage import build_base_metadata


def test_base_metadata_does_not_emit_science_identity_context() -> None:
    metadata = build_base_metadata(
        stage="3d-genome",
        qualifier="gse131651-locus-ledger",
        title="GSE131651 locus ledger",
        stage_type="result",
        version="8.0",
        tool="scripts/analyses/t665_gse131651_3d_locus_ledger.py",
    )

    assert "science" not in metadata or "identity_context" not in metadata.get("science", {})


def test_mm30_species_fields_do_not_create_science_identity_authority() -> None:
    metadata = build_base_metadata(
        stage="3d-genome",
        qualifier="gse131651-locus-ledger",
        title="GSE131651 locus ledger",
        stage_type="result",
        version="8.0",
    )

    assert metadata["mm30"].get("species") == "Homo sapiens"
    assert metadata["mm30"].get("taxonomy_id") == 9606
    assert "science" not in metadata or "identity_context" not in metadata.get("science", {})
```

- [ ] **Step 2: Run the helper test**

Run from the MM30 worktree:

```bash
uv run --frozen pytest tests/test_bio_identity_datapackage_helper.py -q
```

Expected: pass if the helper does not emit `science.identity_context`. If this test fails, the helper is writing the authoritative Science stamp and must be fixed before continuing.

- [ ] **Step 3: Clarify the helper boundary in code**

In `scripts/shared/datapackage.py`, add this comment immediately above the `"mm30": {` block:

```python
# `mm30` is descriptive project metadata. Biological identity authority lives
# in dataset/workflow entity `identity_context` and the derived
# `science.identity_context` datapackage stamp written by Science tooling.
```

Do not add `science.identity_context` here. Do not remove `species` / `taxonomy_id` in this task unless downstream tests prove those fields are unused; preserving them as descriptive MM30 metadata is lower-risk.

- [ ] **Step 4: Run helper tests**

Run from the MM30 worktree:

```bash
uv run --frozen pytest tests/test_bio_identity_datapackage_helper.py -q
```

Expected: pass.

- [ ] **Step 5: Run existing datapackage tests**

Run from the MM30 worktree:

```bash
uv run --frozen pytest tests/test_external_scrna_datapackage_source.py tests/test_t214_signatures_hardcoded_path_cleanup.py tests/test_stage_helper_metadata.py -q
```

Expected: pass. If these tests fail, inspect the failure before editing fixtures; this task preserves `mm30.species` / `mm30.taxonomy_id` as descriptive metadata and should not require fixture removal for those fields.

- [ ] **Step 6: Commit**

```bash
git add scripts/shared/datapackage.py tests/test_bio_identity_datapackage_helper.py
git commit -m "Document MM30 datapackage identity boundary"
```

## Task 7: Add MM30 Identity Migration Report

**Files:**
- Create: `scripts/qa/bio_identity_inventory.py`
- Create: `doc/reports/bio-identity-p5-migration-report.md` or the nearest existing MM30 report directory.
- Test: `tests/test_bio_identity_inventory.py`

- [ ] **Step 1: Add inventory script test**

Create `tests/test_bio_identity_inventory.py`:

```python
from __future__ import annotations

from pathlib import Path

from scripts.qa.bio_identity_inventory import classify_dataset_entity


def test_classify_t665_sources_from_frontmatter() -> None:
    gse131651 = classify_dataset_entity(Path("entities/datasets/gse131651-shah2019-nsd2.md"))
    gse87585 = classify_dataset_entity(Path("entities/datasets/gse87585-wu2017.md"))

    assert gse131651["dataset_id"] == "dataset:gse131651-shah2019-nsd2"
    assert gse131651["has_identity_context"] is True
    assert "coordinate" in gse131651["identity_shape"]
    assert "gene" in gse131651["identity_shape"]

    assert gse87585["dataset_id"] == "dataset:gse87585-wu2017"
    assert gse87585["has_identity_context"] is True
    assert "coordinate" in gse87585["identity_shape"]


def test_classify_non_identity_dataset_without_error(tmp_path: Path) -> None:
    entity = tmp_path / "clinical.md"
    entity.write_text(
        "---\n"
        "type: dataset\n"
        "id: dataset:clinical\n"
        "title: Clinical table\n"
        "ontology_terms: []\n"
        "---\n",
        encoding="utf-8",
    )

    row = classify_dataset_entity(entity)

    assert row["dataset_id"] == "dataset:clinical"
    assert row["has_identity_context"] is False
    assert row["identity_shape"] == ["unclassified"]
```

- [ ] **Step 2: Run test and verify it fails**

Run from the MM30 worktree:

```bash
uv run --frozen pytest tests/test_bio_identity_inventory.py -q
```

Expected: fail because `scripts.qa.bio_identity_inventory` does not exist.

- [ ] **Step 3: Add inventory script**

Create `scripts/qa/bio_identity_inventory.py`:

```python
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import yaml


COORDINATE_TERMS = {
    "3d-genome",
    "Hi-C",
    "HiChIP",
    "CTCF",
    "copy-number",
    "structural-variant",
    "chromatin-accessibility",
    "histone-modification",
}
GENE_TERMS = {"gene-expression", "bulk-rna", "single-cell"}


def _load_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    return yaml.safe_load(text.split("---", 2)[1]) or {}


def _terms(frontmatter: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("ontology_terms", "accessions"):
        raw = frontmatter.get(key)
        if isinstance(raw, list):
            values.update(str(item) for item in raw)
    for item in frontmatter.get("provided_capabilities") or []:
        if isinstance(item, dict):
            values.update(str(value) for value in item.values())
    return values


def classify_dataset_entity(path: Path) -> dict[str, Any]:
    frontmatter = _load_frontmatter(path)
    dataset_id = str(frontmatter.get("id") or f"dataset:{path.stem}")
    identity_context = frontmatter.get("identity_context")
    has_identity = isinstance(identity_context, dict)
    terms = _terms(frontmatter)
    shape: list[str] = []
    if terms & COORDINATE_TERMS:
        shape.append("coordinate")
    if terms & GENE_TERMS:
        shape.append("gene")
    if not shape:
        shape.append("unclassified")
    assembly_status = ""
    gene_status = ""
    if has_identity:
        assembly = identity_context.get("assembly")
        if isinstance(assembly, dict):
            assembly_status = str(assembly.get("resolution_status") or "")
        gene = (identity_context.get("molecular_ids") or {}).get("gene")
        if isinstance(gene, dict):
            gene_status = str(gene.get("resolution_status") or "")
    return {
        "path": path.as_posix(),
        "dataset_id": dataset_id,
        "has_identity_context": has_identity,
        "identity_shape": shape,
        "assembly_status": assembly_status,
        "gene_status": gene_status,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    dataset_paths = sorted((args.project_root / "entities" / "datasets").glob("*.md"))
    rows = [classify_dataset_entity(path.relative_to(args.project_root)) for path in dataset_paths]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path",
                "dataset_id",
                "has_identity_context",
                "identity_shape",
                "assembly_status",
                "gene_status",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "identity_shape": "|".join(row["identity_shape"])})


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run inventory tests**

Run from the MM30 worktree:

```bash
uv run --frozen pytest tests/test_bio_identity_inventory.py -q
```

Expected: pass.

- [ ] **Step 5: Generate the inventory CSV**

Run from the MM30 worktree:

```bash
uv run --frozen python scripts/qa/bio_identity_inventory.py --project-root . --out data/qa/bio_identity_inventory.csv
```

Expected: `data/qa/bio_identity_inventory.csv` exists and includes rows for `dataset:gse131651-shah2019-nsd2` and `dataset:gse87585-wu2017`.

- [ ] **Step 6: Add a human-readable migration report**

Create `doc/reports/bio-identity-p5-migration-report.md`:

```markdown
# Bio Identity P5 Migration Report

Date: 2026-07-03

## Scope

This report covers the first MM30 bio identity adoption slice:

- P5a t665 vertical proof;
- P5b migration scaffold for the dataset backlog.

## t665 Result

- `dataset:gse131651-shah2019-nsd2` declares human hg38 identity and HGNC-symbol gene namespace.
- `dataset:gse87585-wu2017` declares human hg19 identity.
- `workflow:gse131651-3d-locus-ledger` declares a structured `cytoband_proxy` output via `dataset:cytoband-hg19`.
- hg19/hg38 are intentionally not aliased to the current NCBI GRCh37/GRCh38 registry rows.

## Resolver Preflight

The P5a resolver preflight sets both:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data
```

The positive control resolves `GRCh38` to `XemD97fxYMS4q-FBm_n5CHQgmzh1_67a`.

## Migration Window

Touched t665 identity-bearing entities are strict immediately. Untouched identity-bearing backlog rows are reported by `data/qa/bio_identity_inventory.csv` and remain in the warn/report window until a later P5c rollout changes project policy to error.

## Known Remaining Gaps

- Exact UCSC hg19/hg38 assembly registry rows are not present in the current registry.
- Gene tier `resolved` means namespace/tier/registry support, not per-symbol content membership.
- Broader MM30 entity backfill is deferred to P5c after this report is reviewed.
```

- [ ] **Step 7: Commit**

```bash
git add scripts/qa/bio_identity_inventory.py tests/test_bio_identity_inventory.py data/qa/bio_identity_inventory.csv doc/reports/bio-identity-p5-migration-report.md
git commit -m "Report MM30 bio identity migration state"
```

## Task 8: Validate The P5a/P5b Slice

**Files:**
- Modify only if verification reveals a concrete issue in files touched by Tasks 2-7.

- [ ] **Step 1: Run all new focused tests**

Run from the MM30 worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen pytest \
  tests/test_bio_identity_p5_preflight.py \
  tests/test_bio_identity_datapackage_helper.py \
  tests/test_bio_identity_inventory.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run existing affected tests**

Run from the MM30 worktree:

```bash
uv run --frozen pytest \
  tests/test_external_scrna_datapackage_source.py \
  tests/test_t214_signatures_hardcoded_path_cleanup.py \
  tests/test_stage_helper_metadata.py \
  -q
```

Expected: pass, or fixture-only failures that are fixed before continuing.

- [ ] **Step 3: Run Science validation over MM30**

Run from `~/d/science` or the Science worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen science validate --project-root "$MM30_WORKTREE" --format text
```

Expected: no errors on touched t665 identity surfaces. Existing unrelated warnings/errors must be listed in the migration report if they remain.

- [ ] **Step 4: Run a strictness regression by temporary edit**

Temporarily remove this line from `entities/workflows/gse131651-3d-locus-ledger.md`:

```yaml
        via: dataset:cytoband-hg19
```

Run from `~/d/science` or the Science worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen science validate --project-root "$MM30_WORKTREE" --format text
```

Expected: validation fails or reports an error for the invalid proxy contract.

Restore the removed line immediately after the check:

```bash
git restore entities/workflows/gse131651-3d-locus-ledger.md
```

- [ ] **Step 5: Re-run focused tests after restore**

Run from the MM30 worktree:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons \
SCIENCE_COMMONS_DATA_ROOT=~/d/science-commons-data \
uv run --frozen pytest tests/test_bio_identity_p5_preflight.py -q
```

Expected: pass.

- [ ] **Step 6: Check diffs**

Run from the MM30 worktree:

```bash
git status --short
git diff --check HEAD
```

Expected: only intended committed changes or clean status; no whitespace errors.

## Task 9: Update Science Umbrella After P5a/P5b Lands

**Files:**
- Modify: `~/d/science/docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`

- [ ] **Step 1: Update the P5 status**

In `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`, change:

```markdown
**Status:** Re-plan after P4.1-P4.4 shape is known.
```

to:

```markdown
**Status:** P5a/P5b landed; P5c broader rollout gated on review of the MM30 migration report.
```

- [ ] **Step 2: Add a progress ledger entry**

Append this entry under `## Progress ledger`:

```markdown
- 2026-07-03: P5a/P5b MM30/t665 adoption landed. The t665 source entities declare identity; the workflow output declares a structured `cytoband_proxy` via `dataset:cytoband-hg19`; resolver preflight sets both commons roots and includes a GRCh38 positive control; MM30 has a migration report for the untouched backlog. P5c broader rollout remains gated on review of that report and any exact hg19/hg38 registry-row decision.
```

- [ ] **Step 3: Run doc diff check**

Run from the Science worktree:

```bash
git diff --check HEAD -- docs/plans/2026-07-03-bio-identity-adoption-umbrella.md
```

Expected: no output.

- [ ] **Step 4: Commit the umbrella update**

Run from the Science worktree:

```bash
git add docs/plans/2026-07-03-bio-identity-adoption-umbrella.md
git commit -m "Record MM30 bio identity P5 progress"
```

## Task 10: Final Review Gate Before P5c

**Files:**
- No edits unless review finds a concrete issue.

- [ ] **Step 1: Summarize P5a/P5b evidence**

Collect these outputs:

```bash
git -C "$MM30_WORKTREE" log --oneline -6
git -C "$MM30_WORKTREE" status --short
git -C ~/d/science/.worktrees/bio-identity-p5-mm30-replan status --short
```

Expected: MM30 has the P5a/P5b commits; Science worktree has the design/plan and any umbrella update.

- [ ] **Step 2: Request review before P5c**

Do not start broad MM30 backfill in the same execution pass. Hand off:

- P5a validation output;
- P5b inventory CSV/report;
- exact hg19/hg38 registry-row decision status;
- whether per-symbol gene content verification is needed.

Expected: user reviews the report and decides whether P5c starts with exact UCSC assembly registry rows, broader entity backfill, or t665 runtime-output cleanup.

## Acceptance Checklist

- [ ] Resolver preflight sets both `SCIENCE_COMMONS_ROOT` and `SCIENCE_COMMONS_DATA_ROOT`.
- [ ] Positive-control `GRCh38` resolution returns `XemD97fxYMS4q-FBm_n5CHQgmzh1_67a`.
- [ ] `hg19` does not silently resolve to the NCBI `GRCh37` row.
- [ ] `dataset:gse131651-shah2019-nsd2` declares human hg38 identity and HGNC-symbol gene namespace.
- [ ] `dataset:gse87585-wu2017` declares human hg19 identity.
- [ ] `workflow:gse131651-3d-locus-ledger` declares structured `cytoband_proxy` via `dataset:cytoband-hg19`.
- [ ] `dataset:cytoband-hg19` is reference/proxy machinery, not a data ancestor.
- [ ] MM30 datapackage helper no longer hardcodes species/taxonomy as identity authority.
- [ ] MM30 migration report exists and lists the untouched backlog policy.
- [ ] P5c starts only after review of P5a/P5b evidence.
