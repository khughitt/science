# CPTAC GBM Deposit Recipe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a concrete commons deposit candidate and recipe for `dataset:cptac-gbm-2021-proteogenomics`, using the proven cBioPortal/DataHub Git LFS batch path to stage aligned mRNA and protein matrices.

**Architecture:** Keep `dataset:cptac-proteogenomics` as the program-level reference record and add a child study-specific deposit in `~/d/science-commons`. The recipe fetches public cBioPortal metadata, parses DataHub LFS pointers, downloads exact LFS objects through the batch API, verifies hashes and sample alignment, then emits local analysis-ready parquet resources under `~/d/science-commons-data`.

**Tech Stack:** Python 3.13, pandas/pyarrow, pytest, YAML frontmatter dataset entities, Data Package metadata, cBioPortal public API, GitHub Git LFS batch API.

---

## Scope And Repositories

Implementation changes live in the commons repository, not this `science` repository:

- Commons repo: `~/d/science-commons`
- Generated local data root: `~/d/science-commons-data`
- Planning/audit docs: `~/d/science/docs/audits/benchmark-cptac-gbm-fetchability-spike-2026-07-03.md`

In this sandbox, editing `~/d/science-commons` requires approval because it is outside the writable root. Ask for escalation before the first file edit in that repository.

Create or use a commons worktree for implementation:

```bash
cd ~/d/science-commons
git status --short
git check-ignore -q .worktrees || printf ".worktrees/\n" >> .gitignore
git worktree add .worktrees/cptac-gbm-2021-proteogenomics -b cptac-gbm-2021-proteogenomics
cd .worktrees/cptac-gbm-2021-proteogenomics
```

If `.gitignore` is changed because `.worktrees/` was not ignored, commit that change before continuing.

## File Structure

Create the dataset directory:

```text
datasets/cptac-gbm-2021-proteogenomics/
  entity.md
  datapackage.yaml
  recipe/
    README.md
    fetch_manifest.py
    build.py
    build_datapackage.py
    manifest.schema.yaml
    test_cptac_gbm_recipe.py
    fixtures/
      lfs_batch_response.json
      molecular_profiles.json
      sample_lists.json
      study.json
      data_mrna_seq_fpkm.txt
      data_protein_quantification.txt
```

Responsibilities:

- `entity.md`: shared commons dataset metadata and benchmark task.
- `datapackage.yaml`: remote/local resource contract; initially points at recipe-generated local resources with `${OUTPUT_ROOT}` source refs after build verification.
- `recipe/fetch_manifest.py`: metadata dry run, LFS pointer parsing, LFS batch API request creation, payload download/verification, and validation report emission.
- `recipe/build.py`: parse verified raw matrices into normalized parquet resources and enforce exact sample alignment.
- `recipe/build_datapackage.py`: render/update `datapackage.yaml` from generated local resources and validation reports.
- `recipe/manifest.schema.yaml`: machine-readable validation/report contract for the recipe.
- `recipe/test_cptac_gbm_recipe.py`: fixture-driven tests for every fail-early invariant and CLI mode.
- `recipe/README.md`: operator docs with exact dry-run/build/datapackage commands.

---

### Task 0: Commons Worktree And Baseline

**Files:**
- Modify only if needed: `~/d/science-commons/.gitignore`

- [ ] **Step 1: Create an isolated commons worktree**

Run:

```bash
cd ~/d/science-commons
git status --short
git check-ignore -q .worktrees || printf ".worktrees/\n" >> .gitignore
git worktree add .worktrees/cptac-gbm-2021-proteogenomics -b cptac-gbm-2021-proteogenomics
cd .worktrees/cptac-gbm-2021-proteogenomics
```

Expected:

- `git status --short` is clean before worktree creation, or only `.gitignore` changes because `.worktrees/` needed to be ignored.
- Worktree path is `~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics`.

- [ ] **Step 2: Commit ignore setup if it changed**

Run:

```bash
git status --short
git add .gitignore
git commit -m "chore: ignore local worktrees"
```

Expected:

- Run this step only if Step 1 changed `.gitignore`.

- [ ] **Step 3: Verify the dataset slug is new**

Run:

```bash
test ! -e datasets/cptac-gbm-2021-proteogenomics
```

Expected: command exits 0.

---

### Task 1: Metadata Entity And Report Visibility

**Files:**
- Create: `datasets/cptac-gbm-2021-proteogenomics/entity.md`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py`

- [ ] **Step 1: Create the recipe test skeleton**

Create `datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py`:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

RECIPE_DIR = Path(__file__).parent
DATASET_DIR = RECIPE_DIR.parent
sys.path.insert(0, str(RECIPE_DIR))


def _fixture(name: str) -> Path:
    return RECIPE_DIR / "fixtures" / name


def _load_json(name: str) -> dict | list:
    return json.loads(_fixture(name).read_text(encoding="utf-8"))


def test_entity_declares_concrete_child_deposit_and_cross_modal_task():
    text = (DATASET_DIR / "entity.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])

    assert frontmatter["id"] == "dataset:cptac-gbm-2021-proteogenomics"
    assert frontmatter["dataset_class"] == "deposit"
    assert frontmatter["source_class"] == "derived"
    assert frontmatter["license"] == "ODbL-1.0"
    assert frontmatter["datapackage"] == "datapackage.yaml"
    assert frontmatter["access"] == {
        "level": "public",
        "availability": "available",
        "verified": True,
        "verification_method": "metadata-confirmed",
        "source_url": "https://github.com/cBioPortal/datahub/tree/master/public/gbm_cptac_2021",
    }

    benchmark = frontmatter["benchmark"]
    assert "dataset:cptac-proteogenomics" in benchmark["source_datasets"]
    assert {"proteomics", "bulk-rna-seq", "multimodal"}.issubset(set(benchmark["modalities"]))
    assert "multi-omic" in benchmark["signal_types"]

    tasks = {task["id"]: task for task in benchmark["tasks"]}
    task = tasks["protein-rna-cross-modal"]
    assert task["task_type"] == "cross-modal-prediction"
    assert task["prediction_target"] == "mass-spectrometry protein abundance from mRNA expression"
    assert task["held_out_unit"] == "gene-by-sample protein measurements"
    assert task["metric"] == "held-out Pearson correlation"
    assert task["baseline"] == "per-protein training-set mean"
    assert task["ground_truth"]["type"] == "measured-proteomics"
    assert task["support"]["state"] == "candidate"
    assert task["support"]["reason"] == "recipe-staged-validation-needed"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py::test_entity_declares_concrete_child_deposit_and_cross_modal_task -q
```

Expected: FAIL because `entity.md` does not exist.

- [ ] **Step 3: Create `entity.md`**

Create `datasets/cptac-gbm-2021-proteogenomics/entity.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:cptac-gbm-2021-proteogenomics"
type: "dataset"
title: "CPTAC GBM proteogenomics (cBioPortal, Cell 2021)"
version: "1.0.0"
status: "active"
created: "2026-07-03"
updated: "2026-07-03"
scope: "shared"
origin: "external"
source_class: "derived"
dataset_class: "deposit"
tier: "evaluate-next"
license: "ODbL-1.0"
access:
  level: "public"
  availability: "available"
  verified: true
  verification_method: "metadata-confirmed"
  source_url: "https://github.com/cBioPortal/datahub/tree/master/public/gbm_cptac_2021"
ontology_terms: []
tags: []
datapackage: datapackage.yaml
benchmark:
  domains: ["biology", "cancer", "glioblastoma"]
  modalities: ["proteomics", "bulk-rna-seq", "genomics", "multimodal"]
  signal_types: ["cross-sectional", "multi-omic"]
  benchmark_kinds: ["cross-modal-prediction", "mechanism-discrimination"]
  source_datasets: ["dataset:cptac-proteogenomics"]
  related_beliefs: []
  notes:
    - "Study-specific CPTAC GBM package derived from cBioPortal DataHub gbm_cptac_2021."
    - "Fetchability spike on 2026-07-03 verified direct GitHub LFS object downloads for mRNA and protein matrices."
    - "cBioPortal DataHub publishes its study data under the Open Data Commons Open Database License."
  limitations:
    - "cBioPortal-derived package; DataHub uses ODbL terms, so attribution and share-alike terms apply."
    - "Cross-modal prediction is observational and cross-sectional, not causal perturbation evidence."
  tasks:
    - id: protein-rna-cross-modal
      task_type: "cross-modal-prediction"
      prediction_target: "mass-spectrometry protein abundance from mRNA expression"
      held_out_unit: "gene-by-sample protein measurements"
      metric: "held-out Pearson correlation"
      baseline: "per-protein training-set mean"
      ground_truth:
        type: "measured-proteomics"
        description: "protein abundance ratio measured by mass spectrometry in the matched CPTAC GBM sample"
      interpretation_limits:
        - "Cross-sectional association benchmark; do not interpret mRNA-to-protein prediction as causal regulation."
        - "Feature and target matrices are cBioPortal-transformed derivatives of CPTAC GBM source data."
      contexts: ["glioblastoma", "matched tumor sample", "mRNA expression", "protein abundance"]
      support:
        state: candidate
        reason: recipe-staged-validation-needed
        checked_at: "2026-07-03"
        evidence:
          - "~/d/science/docs/audits/benchmark-cptac-gbm-fetchability-spike-2026-07-03.md"
          - "https://github.com/cBioPortal/datahub/blob/master/LICENSE"
        notes:
          - "Direct GitHub LFS batch downloads verified mRNA SHA-256 235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722 and protein SHA-256 b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e."
          - "After live dry-run/download/build validation, update this support reason to recipe-staged if benchmark reports classify the task as stage-needed or runnable."
---
# CPTAC GBM proteogenomics
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py::test_entity_declares_concrete_child_deposit_and_cross_modal_task -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add datasets/cptac-gbm-2021-proteogenomics/entity.md \
  datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py
git commit -m "feat: add CPTAC GBM benchmark metadata"
```

---

### Task 2: Fetch Manifest And LFS Verification

**Files:**
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/fetch_manifest.py`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/fixtures/study.json`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/fixtures/molecular_profiles.json`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/fixtures/sample_lists.json`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/fixtures/lfs_batch_response.json`
- Modify: `datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py`

- [ ] **Step 1: Add fixture files**

Create `recipe/fixtures/study.json`:

```json
{
  "studyId": "gbm_cptac_2021",
  "name": "Glioblastoma (CPTAC, Cell 2021)",
  "publicStudy": true,
  "pmid": "33577785",
  "citation": "Wang et al. Cell 2021",
  "importDate": "2026-01-07 13:14:46",
  "allSampleCount": 99,
  "mrnaRnaSeqSampleCount": 99,
  "massSpectrometrySampleCount": 99
}
```

Create `recipe/fixtures/molecular_profiles.json`:

```json
[
  {
    "molecularAlterationType": "MRNA_EXPRESSION",
    "datatype": "CONTINUOUS",
    "name": "mRNA expression (FPKM UQ)",
    "description": "Gene expression by mRNA abundance in upper-quartile (UQ)-normalized FPKM values, median-centered by gene.",
    "molecularProfileId": "gbm_cptac_2021_mrna",
    "studyId": "gbm_cptac_2021"
  },
  {
    "molecularAlterationType": "PROTEIN_LEVEL",
    "datatype": "LOG2-VALUE",
    "name": "Protein abundance ratio",
    "description": "Protein abundance ratio measured by mass spectrometry",
    "molecularProfileId": "gbm_cptac_2021_protein_quantification",
    "studyId": "gbm_cptac_2021"
  }
]
```

Create `recipe/fixtures/sample_lists.json`:

```json
[
  {
    "category": "all_cases_with_mrna_rnaseq_data",
    "name": "Samples with gene expression data",
    "description": "Samples with gene expression data by RNA-Seq",
    "sampleListId": "gbm_cptac_2021_rna_seq_mrna",
    "studyId": "gbm_cptac_2021"
  },
  {
    "category": "other",
    "name": "Samples with protein quantification data",
    "description": "Samples with protein quantification data by mass spectrometry (99 samples)",
    "sampleListId": "gbm_cptac_2021_protein_quantification",
    "studyId": "gbm_cptac_2021"
  }
]
```

Create `recipe/fixtures/lfs_batch_response.json`:

```json
{
  "objects": [
    {
      "oid": "235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722",
      "size": 29693169,
      "actions": {
        "download": {
          "href": "https://example.invalid/mrna"
        }
      }
    },
    {
      "oid": "b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e",
      "size": 6852651,
      "actions": {
        "download": {
          "href": "https://example.invalid/protein"
        }
      }
    }
  ]
}
```

- [ ] **Step 2: Add failing fetch tests**

Append to `recipe/test_cptac_gbm_recipe.py`:

```python
def test_parse_lfs_pointer_extracts_oid_and_size():
    from fetch_manifest import parse_lfs_pointer

    pointer = """version https://git-lfs.github.com/spec/v1
oid sha256:235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722
size 29693169
"""
    parsed = parse_lfs_pointer(pointer, label="mrna")
    assert parsed == {
        "label": "mrna",
        "oid": "235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722",
        "size": 29693169,
    }


def test_parse_lfs_pointer_rejects_non_pointer_payload():
    from fetch_manifest import parse_lfs_pointer

    with pytest.raises(ValueError, match="not a git LFS pointer"):
        parse_lfs_pointer("Hugo_Symbol\tC3L-00104\nEGFR\t1.0\n", label="mrna")


def test_build_lfs_batch_request_uses_exact_objects():
    from fetch_manifest import build_lfs_batch_payload

    payload = build_lfs_batch_payload(
        [
            {
                "label": "mrna",
                "oid": "235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722",
                "size": 29693169,
            },
            {
                "label": "protein",
                "oid": "b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e",
                "size": 6852651,
            },
        ]
    )
    assert payload == {
        "operation": "download",
        "transfers": ["basic"],
        "objects": [
            {
                "oid": "235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722",
                "size": 29693169,
            },
            {
                "oid": "b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e",
                "size": 6852651,
            },
        ],
    }


def test_batch_response_maps_download_urls_by_oid():
    from fetch_manifest import download_urls_from_batch_response

    urls = download_urls_from_batch_response(_load_json("lfs_batch_response.json"))
    assert urls == {
        "235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722": "https://example.invalid/mrna",
        "b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e": "https://example.invalid/protein",
    }


def test_verify_downloaded_payload_checks_size_hash_and_pointer(tmp_path):
    from fetch_manifest import verify_downloaded_payload

    payload = tmp_path / "matrix.txt"
    payload.write_text("gene\tS1\nEGFR\t1.0\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    report = verify_downloaded_payload(payload, expected_oid=digest, expected_size=payload.stat().st_size)
    assert report == {
        "path": str(payload),
        "bytes": payload.stat().st_size,
        "sha256": digest,
        "is_lfs_pointer": False,
    }

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_downloaded_payload(payload, expected_oid="0" * 64, expected_size=payload.stat().st_size)

    pointer = tmp_path / "pointer.txt"
    pointer.write_text("version https://git-lfs.github.com/spec/v1\n", encoding="utf-8")
    pointer_digest = hashlib.sha256(pointer.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="still a git LFS pointer"):
        verify_downloaded_payload(pointer, expected_oid=pointer_digest, expected_size=pointer.stat().st_size)


def test_write_dry_run_records_metadata_and_validation(tmp_path):
    from fetch_manifest import StaticCbioPortalClient, write_dry_run

    client = StaticCbioPortalClient(
        study=_load_json("study.json"),
        molecular_profiles=_load_json("molecular_profiles.json"),
        sample_lists=_load_json("sample_lists.json"),
        pointers={
            "mrna": "version https://git-lfs.github.com/spec/v1\noid sha256:235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722\nsize 29693169\n",
            "protein": "version https://git-lfs.github.com/spec/v1\noid sha256:b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e\nsize 6852651\n",
        },
    )

    report = write_dry_run(tmp_path, client=client)
    assert report["promotable"] is True
    assert report["study_id"] == "gbm_cptac_2021"
    assert report["import_date"] == "2026-01-07 13:14:46"
    assert report["profiles"] == {
        "mrna": "gbm_cptac_2021_mrna",
        "protein": "gbm_cptac_2021_protein_quantification",
    }

    validation = json.loads((tmp_path / "reports" / "validation.json").read_text(encoding="utf-8"))
    assert validation["promotable"] is True
    assert validation["lfs_objects"]["mrna"]["size"] == 29693169
    assert validation["lfs_objects"]["protein"]["size"] == 6852651
    assert (tmp_path / "manifest" / "study.json").is_file()
    assert (tmp_path / "manifest" / "molecular_profiles.json").is_file()
    assert (tmp_path / "manifest" / "sample_lists.json").is_file()
```

- [ ] **Step 3: Run fetch tests and verify they fail**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py \
  -k "lfs or dry_run" -q
```

Expected: FAIL because `fetch_manifest.py` does not exist.

- [ ] **Step 4: Implement `fetch_manifest.py`**

Create `recipe/fetch_manifest.py`:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib import request

CBIOPORTAL_API_BASE = "https://www.cbioportal.org/api"
DATAHUB_RAW_BASE = "https://raw.githubusercontent.com/cBioPortal/datahub/master/public/gbm_cptac_2021"
LFS_BATCH_URL = "https://github.com/cBioPortal/datahub.git/info/lfs/objects/batch"
DATASET_NAME = "cptac-gbm-2021-proteogenomics"
STUDY_ID = "gbm_cptac_2021"
DEFAULT_TIMEOUT_SECONDS = 60

MATRIX_FILES = {
    "mrna": "data_mrna_seq_fpkm.txt",
    "protein": "data_protein_quantification.txt",
}
REQUIRED_PROFILES = {
    "mrna": "gbm_cptac_2021_mrna",
    "protein": "gbm_cptac_2021_protein_quantification",
}
REQUIRED_SAMPLE_LISTS = {
    "mrna": "gbm_cptac_2021_rna_seq_mrna",
    "protein": "gbm_cptac_2021_protein_quantification",
}


def resolve_output_dir(output_dir: str | Path | None, env: Mapping[str, str] | None = None) -> Path:
    if output_dir:
        return Path(output_dir)
    environ = env or os.environ
    data_root = environ.get("SCIENCE_COMMONS_DATA_ROOT")
    if data_root:
        return Path(data_root) / DATASET_NAME
    raise ValueError("--output-dir is required unless SCIENCE_COMMONS_DATA_ROOT is set")


def _get_json(url: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    with request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def _post_json(url: str, payload: Mapping[str, Any], *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> Any:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.git-lfs+json",
            "Content-Type": "application/vnd.git-lfs+json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def _get_text(url: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    with request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")


class CbioPortalClient:
    def study(self) -> Mapping[str, Any]:
        payload = _get_json(f"{CBIOPORTAL_API_BASE}/studies/{STUDY_ID}")
        if not isinstance(payload, Mapping):
            raise ValueError("Study response must be a JSON object")
        return payload

    def molecular_profiles(self) -> list[Mapping[str, Any]]:
        payload = _get_json(f"{CBIOPORTAL_API_BASE}/studies/{STUDY_ID}/molecular-profiles")
        if not isinstance(payload, list):
            raise ValueError("Molecular profiles response must be a JSON list")
        return [profile for profile in payload if isinstance(profile, Mapping)]

    def sample_lists(self) -> list[Mapping[str, Any]]:
        payload = _get_json(f"{CBIOPORTAL_API_BASE}/studies/{STUDY_ID}/sample-lists")
        if not isinstance(payload, list):
            raise ValueError("Sample lists response must be a JSON list")
        return [sample_list for sample_list in payload if isinstance(sample_list, Mapping)]

    def lfs_pointer(self, label: str) -> str:
        return _get_text(f"{DATAHUB_RAW_BASE}/{MATRIX_FILES[label]}")

    def lfs_batch(self, objects: list[Mapping[str, Any]]) -> Mapping[str, Any]:
        payload = build_lfs_batch_payload(objects)
        response = _post_json(LFS_BATCH_URL, payload)
        if not isinstance(response, Mapping):
            raise ValueError("LFS batch response must be a JSON object")
        return response


class StaticCbioPortalClient:
    def __init__(
        self,
        *,
        study: Mapping[str, Any],
        molecular_profiles: list[Mapping[str, Any]],
        sample_lists: list[Mapping[str, Any]],
        pointers: Mapping[str, str],
        batch_response: Mapping[str, Any] | None = None,
    ) -> None:
        self._study = study
        self._molecular_profiles = molecular_profiles
        self._sample_lists = sample_lists
        self._pointers = pointers
        self._batch_response = batch_response or {"objects": []}

    def study(self) -> Mapping[str, Any]:
        return self._study

    def molecular_profiles(self) -> list[Mapping[str, Any]]:
        return self._molecular_profiles

    def sample_lists(self) -> list[Mapping[str, Any]]:
        return self._sample_lists

    def lfs_pointer(self, label: str) -> str:
        return self._pointers[label]

    def lfs_batch(self, objects: list[Mapping[str, Any]]) -> Mapping[str, Any]:
        return self._batch_response


def parse_lfs_pointer(text: str, *, label: str) -> dict[str, Any]:
    if not text.startswith("version https://git-lfs.github.com/spec/v1"):
        raise ValueError(f"{label} is not a git LFS pointer")
    oid_match = re.search(r"^oid sha256:([0-9a-f]{64})$", text, flags=re.MULTILINE)
    size_match = re.search(r"^size ([0-9]+)$", text, flags=re.MULTILINE)
    if not oid_match or not size_match:
        raise ValueError(f"{label} LFS pointer is missing oid or size")
    return {"label": label, "oid": oid_match.group(1), "size": int(size_match.group(1))}


def build_lfs_batch_payload(objects: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "operation": "download",
        "transfers": ["basic"],
        "objects": [{"oid": str(obj["oid"]), "size": int(obj["size"])} for obj in objects],
    }


def download_urls_from_batch_response(payload: Mapping[str, Any]) -> dict[str, str]:
    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise ValueError("LFS batch response is missing objects")
    urls: dict[str, str] = {}
    for obj in objects:
        if not isinstance(obj, Mapping):
            raise ValueError("LFS batch object must be a JSON object")
        oid = str(obj.get("oid") or "")
        href = (((obj.get("actions") or {}).get("download") or {}).get("href"))
        if not re.fullmatch(r"[0-9a-f]{64}", oid) or not href:
            raise ValueError(f"LFS batch object {oid or '<missing>'} is missing a download action")
        urls[oid] = str(href)
    return urls


def verify_downloaded_payload(path: str | Path, *, expected_oid: str, expected_size: int) -> dict[str, Any]:
    target = Path(path)
    data = target.read_bytes()
    byte_count = len(data)
    digest = hashlib.sha256(data).hexdigest()
    if byte_count != expected_size:
        raise ValueError(f"{target} byte count mismatch: expected {expected_size}, found {byte_count}")
    if digest != expected_oid:
        raise ValueError(f"{target} SHA-256 mismatch: expected {expected_oid}, found {digest}")
    is_pointer = data.startswith(b"version https://git-lfs.github.com/spec/v1")
    if is_pointer:
        raise ValueError(f"{target} is still a git LFS pointer")
    return {"path": str(target), "bytes": byte_count, "sha256": digest, "is_lfs_pointer": False}


def _profile_ids(profiles: list[Mapping[str, Any]]) -> set[str]:
    return {str(profile.get("molecularProfileId")) for profile in profiles}


def _sample_list_ids(sample_lists: list[Mapping[str, Any]]) -> set[str]:
    return {str(sample_list.get("sampleListId")) for sample_list in sample_lists}


def _validate_source_surface(
    study: Mapping[str, Any],
    profiles: list[Mapping[str, Any]],
    sample_lists: list[Mapping[str, Any]],
) -> None:
    if study.get("studyId") != STUDY_ID:
        raise ValueError(f"Unexpected study id: {study.get('studyId')}")
    if study.get("publicStudy") is not True:
        raise ValueError(f"{STUDY_ID} is not public")
    missing_profiles = sorted(set(REQUIRED_PROFILES.values()) - _profile_ids(profiles))
    if missing_profiles:
        raise ValueError(f"Missing required molecular profiles: {', '.join(missing_profiles)}")
    missing_sample_lists = sorted(set(REQUIRED_SAMPLE_LISTS.values()) - _sample_list_ids(sample_lists))
    if missing_sample_lists:
        raise ValueError(f"Missing required sample lists: {', '.join(missing_sample_lists)}")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_dry_run(output_dir: str | Path, *, client: CbioPortalClient | StaticCbioPortalClient | None = None) -> dict[str, Any]:
    out = Path(output_dir)
    active_client = client or CbioPortalClient()
    study = active_client.study()
    profiles = active_client.molecular_profiles()
    sample_lists = active_client.sample_lists()
    _validate_source_surface(study, profiles, sample_lists)
    objects = [parse_lfs_pointer(active_client.lfs_pointer(label), label=label) for label in ("mrna", "protein")]

    _write_json(out / "manifest" / "study.json", study)
    _write_json(out / "manifest" / "molecular_profiles.json", profiles)
    _write_json(out / "manifest" / "sample_lists.json", sample_lists)
    validation = {
        "study_id": STUDY_ID,
        "import_date": study.get("importDate"),
        "sample_counts": {
            "all": study.get("allSampleCount"),
            "mrna": study.get("mrnaRnaSeqSampleCount"),
            "mass_spectrometry": study.get("massSpectrometrySampleCount"),
        },
        "profiles": REQUIRED_PROFILES,
        "sample_lists": REQUIRED_SAMPLE_LISTS,
        "lfs_objects": {str(obj["label"]): {"oid": obj["oid"], "size": obj["size"]} for obj in objects},
        "promotable": True,
    }
    _write_json(out / "reports" / "validation.json", validation)
    return validation


def download_lfs_payloads(
    output_dir: str | Path,
    *,
    client: CbioPortalClient | StaticCbioPortalClient | None = None,
) -> dict[str, Any]:
    out = Path(output_dir)
    active_client = client or CbioPortalClient()
    validation_path = out / "reports" / "validation.json"
    if not validation_path.is_file():
        write_dry_run(out, client=active_client)
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    objects = [
        {"label": label, "oid": spec["oid"], "size": spec["size"]}
        for label, spec in validation["lfs_objects"].items()
    ]
    urls = download_urls_from_batch_response(active_client.lfs_batch(objects))
    raw_dir = out / "_src" / "datahub"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reports: dict[str, Any] = {}
    for obj in objects:
        label = str(obj["label"])
        target = raw_dir / MATRIX_FILES[label]
        with request.urlopen(urls[str(obj["oid"])], timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            target.write_bytes(response.read())
        reports[label] = verify_downloaded_payload(
            target,
            expected_oid=str(obj["oid"]),
            expected_size=int(obj["size"]),
        )
    _write_json(out / "reports" / "download-summary.json", reports)
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch CPTAC GBM cBioPortal/DataHub metadata and payloads.")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    output_dir = resolve_output_dir(args.output_dir)
    if args.dry_run and args.download:
        parser.error("--dry-run is not allowed with --download")
    if args.download:
        report = download_lfs_payloads(output_dir)
    else:
        report = write_dry_run(output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run fetch tests and verify they pass**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py \
  -k "lfs or dry_run" -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add datasets/cptac-gbm-2021-proteogenomics/recipe
git commit -m "feat: add CPTAC GBM fetch manifest recipe"
```

---

### Task 3: Matrix Build And Sample Alignment

**Files:**
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/build.py`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/fixtures/data_mrna_seq_fpkm.txt`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/fixtures/data_protein_quantification.txt`
- Modify: `datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py`

- [ ] **Step 1: Add small matrix fixtures**

Create `recipe/fixtures/data_mrna_seq_fpkm.txt`:

```text
Hugo_Symbol	C3L-00104	C3L-00365	C3L-00674
EGFR	2273268.1	11135934.5	1337185.9
TP53	121103.3	97896	161630
```

Create `recipe/fixtures/data_protein_quantification.txt`:

```text
Composite.Element.REF	C3L-00104	C3L-00365	C3L-00674
EGFR|EGFR	1.055	2.22	0.137
TP53|TP53	0.045	0.118	-0.121
```

- [ ] **Step 2: Add failing build tests**

Append to `recipe/test_cptac_gbm_recipe.py`:

```python
def test_read_matrix_reports_feature_and_sample_counts():
    from build import read_matrix

    matrix = read_matrix(_fixture("data_mrna_seq_fpkm.txt"), feature_column="Hugo_Symbol")
    assert matrix.feature_column == "Hugo_Symbol"
    assert matrix.sample_ids == ["C3L-00104", "C3L-00365", "C3L-00674"]
    assert len(matrix.rows) == 2
    assert matrix.rows[0]["feature_id"] == "EGFR"
    assert matrix.rows[0]["C3L-00104"] == 2273268.1


def test_read_matrix_ignores_known_non_sample_id_columns(tmp_path):
    from build import read_matrix

    matrix_path = tmp_path / "matrix.txt"
    matrix_path.write_text(
        "Hugo_Symbol\tEntrez_Gene_Id\tC3L-00104\tC3L-00365\n"
        "EGFR\t1956\t1.0\t2.0\n",
        encoding="utf-8",
    )

    matrix = read_matrix(matrix_path, feature_column="Hugo_Symbol")
    assert matrix.sample_ids == ["C3L-00104", "C3L-00365"]
    assert matrix.skipped_blank_feature_rows == 0


def test_validate_aligned_samples_requires_identical_order():
    from build import MatrixTable, validate_aligned_samples

    left = MatrixTable(feature_column="x", sample_ids=["S1", "S2"], rows=[], skipped_blank_feature_rows=0)
    right = MatrixTable(feature_column="y", sample_ids=["S1", "S2"], rows=[], skipped_blank_feature_rows=0)
    validate_aligned_samples(left, right)

    mismatched = MatrixTable(feature_column="y", sample_ids=["S2", "S1"], rows=[], skipped_blank_feature_rows=0)
    with pytest.raises(ValueError, match="sample order mismatch"):
        validate_aligned_samples(left, mismatched)


def test_build_package_writes_normalized_resources(tmp_path):
    from build import build_package

    src = tmp_path / "_src" / "datahub"
    src.mkdir(parents=True)
    src.joinpath("data_mrna_seq_fpkm.txt").write_text(_fixture("data_mrna_seq_fpkm.txt").read_text(encoding="utf-8"), encoding="utf-8")
    src.joinpath("data_protein_quantification.txt").write_text(_fixture("data_protein_quantification.txt").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "validation.json").write_text(
        json.dumps({"import_date": "2026-01-07 13:14:46", "promotable": True}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "reports" / "download-summary.json").write_text(
        json.dumps({"mrna": {"sha256": "fixture"}, "protein": {"sha256": "fixture"}}) + "\n",
        encoding="utf-8",
    )

    summary = build_package(tmp_path)
    assert summary["sample_rows"] == 3
    assert summary["mrna_feature_rows"] == 2
    assert summary["protein_feature_rows"] == 2
    assert summary["matched_feature_rows"] == 2
    assert summary["sample_alignment"] == "identical-order"
    assert (tmp_path / "expression" / "mrna_fpkm_uq.parquet").is_file()
    assert (tmp_path / "proteomics" / "protein_abundance_log2.parquet").is_file()
    assert (tmp_path / "metadata" / "samples.parquet").is_file()
    assert (tmp_path / "reports" / "build-summary.json").is_file()
```

- [ ] **Step 3: Run build tests and verify they fail**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py \
  -k "matrix or aligned or build_package" -q
```

Expected: FAIL because `build.py` does not exist.

- [ ] **Step 4: Implement `build.py`**

Create `recipe/build.py`:

```python
from __future__ import annotations

import argparse
import csv
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DATASET_NAME = "cptac-gbm-2021-proteogenomics"
MRNA_FILE = "data_mrna_seq_fpkm.txt"
PROTEIN_FILE = "data_protein_quantification.txt"
KNOWN_NON_SAMPLE_COLUMNS = frozenset({"Entrez_Gene_Id"})


@dataclass(frozen=True)
class MatrixTable:
    feature_column: str
    sample_ids: list[str]
    rows: list[dict[str, Any]]
    skipped_blank_feature_rows: int


def resolve_output_dir(output_dir: str | Path | None, env: Mapping[str, str] | None = None) -> Path:
    if output_dir:
        return Path(output_dir)
    environ = env or os.environ
    data_root = environ.get("SCIENCE_COMMONS_DATA_ROOT")
    if data_root:
        return Path(data_root) / DATASET_NAME
    raise ValueError("--output-dir is required unless SCIENCE_COMMONS_DATA_ROOT is set")


def _parse_float(value: str, *, feature_id: str, sample_id: str) -> float | None:
    if value in {"", "NA", "NaN", "nan"}:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value for {feature_id}/{sample_id}: {value!r}") from exc


def read_matrix(path: str | Path, *, feature_column: str) -> MatrixTable:
    source = Path(path)
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"{source} is missing a header row")
        if feature_column not in reader.fieldnames:
            raise ValueError(f"{source} is missing feature column {feature_column}")
        sample_ids = [name for name in reader.fieldnames if name != feature_column and name not in KNOWN_NON_SAMPLE_COLUMNS]
        if not sample_ids:
            raise ValueError(f"{source} has no sample columns")
        rows: list[dict[str, Any]] = []
        skipped_blank_feature_rows = 0
        for raw in reader:
            feature_id = str(raw.get(feature_column) or "").strip()
            if not feature_id:
                skipped_blank_feature_rows += 1
                continue
            row: dict[str, Any] = {"feature_id": feature_id}
            for sample_id in sample_ids:
                row[sample_id] = _parse_float(str(raw.get(sample_id) or ""), feature_id=feature_id, sample_id=sample_id)
            rows.append(row)
    if not rows:
        raise ValueError(f"{source} contains no feature rows")
    return MatrixTable(
        feature_column=feature_column,
        sample_ids=sample_ids,
        rows=rows,
        skipped_blank_feature_rows=skipped_blank_feature_rows,
    )


def _protein_symbol(feature_id: str) -> str:
    return feature_id.split("|", 1)[0]


def validate_aligned_samples(mrna: MatrixTable, protein: MatrixTable) -> None:
    if mrna.sample_ids != protein.sample_ids:
        raise ValueError("mRNA/protein sample order mismatch")


def _matrix_to_long(table: MatrixTable, *, value_name: str, feature_transform=lambda value: value) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in table.rows:
        feature_id = feature_transform(str(row["feature_id"]))
        for sample_id in table.sample_ids:
            records.append({"feature_id": feature_id, "sample_id": sample_id, value_name: row[sample_id]})
    return pd.DataFrame.from_records(records)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_package(output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir)
    validation_path = out / "reports" / "validation.json"
    download_summary_path = out / "reports" / "download-summary.json"
    if not validation_path.is_file():
        raise ValueError(f"Missing validation report: {validation_path}")
    if not download_summary_path.is_file():
        raise ValueError(f"Missing download summary: {download_summary_path}")

    mrna = read_matrix(out / "_src" / "datahub" / MRNA_FILE, feature_column="Hugo_Symbol")
    protein = read_matrix(out / "_src" / "datahub" / PROTEIN_FILE, feature_column="Composite.Element.REF")
    validate_aligned_samples(mrna, protein)

    expression = _matrix_to_long(mrna, value_name="mrna_fpkm_uq")
    proteomics = _matrix_to_long(protein, value_name="protein_abundance_log2", feature_transform=_protein_symbol)
    samples = pd.DataFrame({"sample_id": mrna.sample_ids})
    matched_features = sorted(set(expression["feature_id"]) & set(proteomics["feature_id"]))

    (out / "expression").mkdir(parents=True, exist_ok=True)
    (out / "proteomics").mkdir(parents=True, exist_ok=True)
    (out / "metadata").mkdir(parents=True, exist_ok=True)
    expression.to_parquet(out / "expression" / "mrna_fpkm_uq.parquet", index=False)
    proteomics.to_parquet(out / "proteomics" / "protein_abundance_log2.parquet", index=False)
    samples.to_parquet(out / "metadata" / "samples.parquet", index=False)

    summary = {
        "sample_rows": int(len(samples)),
        "mrna_feature_rows": int(len(mrna.rows)),
        "protein_feature_rows": int(len(protein.rows)),
        "matched_feature_rows": int(len(matched_features)),
        "sample_alignment": "identical-order",
        "skipped_blank_mrna_feature_rows": int(mrna.skipped_blank_feature_rows),
        "skipped_blank_protein_feature_rows": int(protein.skipped_blank_feature_rows),
        "resources": [
            "expression/mrna_fpkm_uq.parquet",
            "proteomics/protein_abundance_log2.parquet",
            "metadata/samples.parquet",
        ],
    }
    _write_json(out / "reports" / "build-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build CPTAC GBM aligned mRNA/protein resources.")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    output_dir = resolve_output_dir(args.output_dir)
    summary = build_package(output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run build tests and verify they pass**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py \
  -k "matrix or aligned or build_package" -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add datasets/cptac-gbm-2021-proteogenomics/recipe
git commit -m "feat: build CPTAC GBM aligned matrices"
```

---

### Task 4: Datapackage Rendering And Recipe Docs

**Files:**
- Create: `datasets/cptac-gbm-2021-proteogenomics/datapackage.yaml`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/build_datapackage.py`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/manifest.schema.yaml`
- Create: `datasets/cptac-gbm-2021-proteogenomics/recipe/README.md`
- Modify: `datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py`

- [ ] **Step 1: Add failing datapackage/docs tests**

Append to `recipe/test_cptac_gbm_recipe.py`:

```python
def test_manifest_schema_documents_validation_and_build_reports():
    schema = yaml.safe_load((RECIPE_DIR / "manifest.schema.yaml").read_text(encoding="utf-8"))
    assert schema["dataset"]["id"] == "dataset:cptac-gbm-2021-proteogenomics"
    assert schema["dataset"]["task"] == "protein-rna-cross-modal"
    assert schema["validation_report"]["required_fields"] == [
        "study_id",
        "import_date",
        "sample_counts",
        "profiles",
        "sample_lists",
        "lfs_objects",
        "promotable",
    ]
    assert schema["build_summary"]["required_fields"] == [
        "sample_rows",
        "mrna_feature_rows",
        "protein_feature_rows",
        "matched_feature_rows",
        "sample_alignment",
        "resources",
    ]


def test_build_datapackage_doc_records_local_resource_hashes(tmp_path):
    from build_datapackage import build_datapackage_doc

    for rel_path, content in {
        "expression/mrna_fpkm_uq.parquet": b"mrna",
        "proteomics/protein_abundance_log2.parquet": b"protein",
        "metadata/samples.parquet": b"samples",
        "reports/validation.json": b"{}",
        "reports/download-summary.json": b"{}",
        "reports/build-summary.json": b"{}",
    }.items():
        target = tmp_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    doc = build_datapackage_doc(tmp_path, import_date="2026-01-07 13:14:46")
    assert doc["name"] == "cptac-gbm-2021-proteogenomics"
    assert doc["profile"] == "data-package"
    assert doc["cBioPortal"]["study_id"] == "gbm_cptac_2021"
    assert doc["cBioPortal"]["import_date"] == "2026-01-07 13:14:46"
    resources = {resource["name"]: resource for resource in doc["resources"]}
    assert resources["mrna_fpkm_uq"]["source"]["ref"] == "${OUTPUT_ROOT}/cptac-gbm-2021-proteogenomics/expression/mrna_fpkm_uq.parquet"
    assert resources["mrna_fpkm_uq"]["hash"].startswith("sha256:")
    assert resources["mrna_fpkm_uq"]["format"] == "parquet"
    assert resources["protein_abundance_log2"]["path"] == "proteomics/protein_abundance_log2.parquet"
    assert resources["build_summary"]["path"] == "reports/build-summary.json"


def test_recipe_readme_documents_required_commands_and_no_committed_data():
    text = (RECIPE_DIR / "README.md").read_text(encoding="utf-8")
    assert "--output-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics" in text
    assert "fetch_manifest.py --dry-run" in text
    assert "fetch_manifest.py --download" in text
    assert "build.py" in text
    assert "build_datapackage.py" in text
    assert "Do not commit generated data" in text
```

- [ ] **Step 2: Run datapackage/docs tests and verify they fail**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py \
  -k "datapackage or schema or readme" -q
```

Expected: FAIL because `build_datapackage.py`, `manifest.schema.yaml`, `README.md`, and `datapackage.yaml` do not exist.

- [ ] **Step 3: Create `build_datapackage.py`**

Create `recipe/build_datapackage.py`:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple

import yaml

OUTPUT_ROOT_TOKEN = "${OUTPUT_ROOT}"
DATASET_NAME = "cptac-gbm-2021-proteogenomics"
STUDY_ID = "gbm_cptac_2021"


class ResourceFile(NamedTuple):
    name: str
    rel_path: str


RESOURCE_FILES = (
    ResourceFile("mrna_fpkm_uq", "expression/mrna_fpkm_uq.parquet"),
    ResourceFile("protein_abundance_log2", "proteomics/protein_abundance_log2.parquet"),
    ResourceFile("samples", "metadata/samples.parquet"),
    ResourceFile("validation", "reports/validation.json"),
    ResourceFile("download_summary", "reports/download-summary.json"),
    ResourceFile("build_summary", "reports/build-summary.json"),
)


def stream_sha256_and_bytes(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            byte_count += len(chunk)
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}", byte_count


def build_datapackage_doc(data_dir: str | Path, *, import_date: str) -> dict[str, Any]:
    root = Path(data_dir)
    resources: list[dict[str, Any]] = []
    for resource in RESOURCE_FILES:
        path = root / resource.rel_path
        digest, byte_count = stream_sha256_and_bytes(path)
        resources.append(
            {
                "name": resource.name,
                "path": resource.rel_path,
                "hash": digest,
                "bytes": byte_count,
                "format": "parquet" if resource.rel_path.endswith(".parquet") else "json",
                "mediatype": "application/vnd.apache.parquet" if resource.rel_path.endswith(".parquet") else "application/json",
                "source": {
                    "type": "local",
                    "ref": f"{OUTPUT_ROOT_TOKEN}/{DATASET_NAME}/{resource.rel_path}",
                },
            }
        )
    return {
        "name": DATASET_NAME,
        "title": "CPTAC GBM proteogenomics aligned mRNA/protein package",
        "profile": "data-package",
        "licenses": [{"name": "ODbL-1.0"}],
        "cBioPortal": {"study_id": STUDY_ID, "import_date": import_date},
        "provenance": [{"tool": "recipe/fetch_manifest.py"}, {"tool": "recipe/build.py"}],
        "resources": resources,
    }


def render_datapackage_text(doc: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(doc), sort_keys=False, allow_unicode=False)


def resolve_data_dir(data_dir: str | Path | None, env: Mapping[str, str] | None = None) -> Path:
    if data_dir:
        return Path(data_dir)
    environ = env or os.environ
    data_root = environ.get("SCIENCE_COMMONS_DATA_ROOT")
    if data_root:
        return Path(data_root) / DATASET_NAME
    raise ValueError("--data-dir is required unless SCIENCE_COMMONS_DATA_ROOT is set")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render CPTAC GBM datapackage metadata.")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("../datapackage.yaml"))
    parser.add_argument("--import-date", required=True)
    args = parser.parse_args(argv)
    data_dir = resolve_data_dir(args.data_dir)
    doc = build_datapackage_doc(data_dir, import_date=args.import_date)
    args.output.write_text(render_datapackage_text(doc), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create `manifest.schema.yaml`**

Create `recipe/manifest.schema.yaml`:

```yaml
dataset:
  id: dataset:cptac-gbm-2021-proteogenomics
  study_id: gbm_cptac_2021
  task: protein-rna-cross-modal
  source_datasets:
    - dataset:cptac-proteogenomics
validation_report:
  required_fields:
    - study_id
    - import_date
    - sample_counts
    - profiles
    - sample_lists
    - lfs_objects
    - promotable
  fields:
    lfs_objects:
      required_labels:
        - mrna
        - protein
      required_object_fields:
        - oid
        - size
    profiles:
      mrna: gbm_cptac_2021_mrna
      protein: gbm_cptac_2021_protein_quantification
    sample_lists:
      mrna: gbm_cptac_2021_rna_seq_mrna
      protein: gbm_cptac_2021_protein_quantification
build_summary:
  required_fields:
    - sample_rows
    - mrna_feature_rows
    - protein_feature_rows
    - matched_feature_rows
    - sample_alignment
    - resources
  invariants:
    - sample_alignment must be identical-order
    - matched_feature_rows must be nonzero
    - output resources must remain outside git-tracked commons metadata
```

- [ ] **Step 5: Create initial `datapackage.yaml`**

Create `datapackage.yaml`:

```yaml
name: cptac-gbm-2021-proteogenomics
title: CPTAC GBM proteogenomics aligned mRNA/protein package
profile: data-package
licenses:
  - name: ODbL-1.0
cBioPortal:
  study_id: gbm_cptac_2021
  import_date: "2026-01-07 13:14:46"
provenance:
  - tool: recipe/fetch_manifest.py
  - tool: recipe/build.py
resources:
  - name: mrna_fpkm_uq
    path: expression/mrna_fpkm_uq.parquet
    hash: sha256:0000000000000000000000000000000000000000000000000000000000000000
    bytes: 0
    format: parquet
    mediatype: application/vnd.apache.parquet
    source:
      type: local
      ref: ${OUTPUT_ROOT}/cptac-gbm-2021-proteogenomics/expression/mrna_fpkm_uq.parquet
  - name: protein_abundance_log2
    path: proteomics/protein_abundance_log2.parquet
    hash: sha256:0000000000000000000000000000000000000000000000000000000000000000
    bytes: 0
    format: parquet
    mediatype: application/vnd.apache.parquet
    source:
      type: local
      ref: ${OUTPUT_ROOT}/cptac-gbm-2021-proteogenomics/proteomics/protein_abundance_log2.parquet
  - name: samples
    path: metadata/samples.parquet
    hash: sha256:0000000000000000000000000000000000000000000000000000000000000000
    bytes: 0
    format: parquet
    mediatype: application/vnd.apache.parquet
    source:
      type: local
      ref: ${OUTPUT_ROOT}/cptac-gbm-2021-proteogenomics/metadata/samples.parquet
```

- [ ] **Step 6: Create `README.md`**

Create `recipe/README.md`:

````markdown
# CPTAC GBM Proteogenomics Recipe

This recipe stages a study-specific cBioPortal/DataHub-derived CPTAC GBM
package for `dataset:cptac-gbm-2021-proteogenomics`.

Do not commit generated data. Keep generated files under
`~/d/science-commons-data/cptac-gbm-2021-proteogenomics` or another explicit
output directory outside git-tracked commons metadata.

## Dry Run

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python fetch_manifest.py --dry-run \
  --output-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics
```

The dry run writes:

```text
manifest/study.json
manifest/molecular_profiles.json
manifest/sample_lists.json
reports/validation.json
```

## Download

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python fetch_manifest.py --download \
  --output-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics
```

The download step parses DataHub LFS pointers, requests signed direct URLs from
the GitHub LFS batch API, downloads the mRNA and protein payloads, and verifies
byte counts plus SHA-256 hashes.

## Build

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python build.py \
  --output-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics
```

The build writes:

```text
expression/mrna_fpkm_uq.parquet
proteomics/protein_abundance_log2.parquet
metadata/samples.parquet
reports/build-summary.json
```

## Datapackage

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python build_datapackage.py \
  --data-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics \
  --import-date "2026-01-07 13:14:46" \
  --output ../datapackage.yaml
```

## Validation

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_cptac_gbm_recipe.py -q
```
````

- [ ] **Step 7: Run datapackage/docs tests and verify they pass**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest datasets/cptac-gbm-2021-proteogenomics/recipe/test_cptac_gbm_recipe.py \
  -k "datapackage or schema or readme" -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add datasets/cptac-gbm-2021-proteogenomics
git commit -m "feat: document CPTAC GBM datapackage contract"
```

---

### Task 5: Full Validation And Smoke Run

**Files:**
- Modify only if validation exposes issues:
  - `datasets/cptac-gbm-2021-proteogenomics/entity.md`
  - `datasets/cptac-gbm-2021-proteogenomics/datapackage.yaml`
  - `datasets/cptac-gbm-2021-proteogenomics/recipe/*.py`
  - `datasets/cptac-gbm-2021-proteogenomics/recipe/*.yaml`
  - `datasets/cptac-gbm-2021-proteogenomics/recipe/README.md`

- [ ] **Step 1: Run the complete recipe test suite**

Run:

```bash
cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics/datasets/cptac-gbm-2021-proteogenomics/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_cptac_gbm_recipe.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run a live dry run**

Run:

```bash
cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics/datasets/cptac-gbm-2021-proteogenomics/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python fetch_manifest.py --dry-run \
  --output-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics
```

Expected:

- `reports/validation.json` exists.
- `reports/validation.json` contains `promotable: true`.
- `reports/validation.json` records both LFS object IDs:
  - `235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722`
  - `b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e`

- [ ] **Step 3: Run the live download**

Run:

```bash
cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics/datasets/cptac-gbm-2021-proteogenomics/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python fetch_manifest.py --download \
  --output-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics
```

Expected:

- `_src/datahub/data_mrna_seq_fpkm.txt` exists and is 29,693,169 bytes.
- `_src/datahub/data_protein_quantification.txt` exists and is 6,852,651 bytes.
- `reports/download-summary.json` exists.
- Downloaded files are not git LFS pointer files.

- [ ] **Step 4: Run the live build**

Run:

```bash
cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics/datasets/cptac-gbm-2021-proteogenomics/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python build.py \
  --output-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics
```

Expected:

- `expression/mrna_fpkm_uq.parquet` exists.
- `proteomics/protein_abundance_log2.parquet` exists.
- `metadata/samples.parquet` exists.
- `reports/build-summary.json` contains:
  - `sample_rows: 99`
  - `sample_alignment: identical-order`
  - nonzero `matched_feature_rows`

- [ ] **Step 5: Render datapackage metadata from the live build**

Run:

```bash
cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics/datasets/cptac-gbm-2021-proteogenomics/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python build_datapackage.py \
  --data-dir ~/d/science-commons-data/cptac-gbm-2021-proteogenomics \
  --import-date "2026-01-07 13:14:46" \
  --output ../datapackage.yaml
```

Expected:

- `../datapackage.yaml` includes hashes and bytes for generated resources.
- No generated parquet or raw payload files appear under `git status --short`.

- [ ] **Step 6: Register the local data override**

Run from `~/d/science`:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science \
  python -c 'from pathlib import Path; from science_tool.commons.config import upsert_data_override; upsert_data_override(slug="cptac-gbm-2021-proteogenomics", absolute_path=(Path.home() / "d" / "science-commons-data" / "cptac-gbm-2021-proteogenomics"), op_id="cptac-gbm-2021-proteogenomics")'
```

Expected:

- `~/.config/science/data.yaml` contains a
  `cptac-gbm-2021-proteogenomics` entry.
- The stored value is the absolute path corresponding to
  `~/d/science-commons-data/cptac-gbm-2021-proteogenomics`; do not store a
  literal `~`, because `data.yaml` validation requires absolute paths.

- [ ] **Step 7: Run commons validation smoke checks**

Run from `~/d/science`:

```bash
SCIENCE_COMMONS_ROOT="$(cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics && pwd -P)" \
OUTPUT_ROOT="$(cd ~/d/science-commons-data && pwd -P)" \
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science \
  science commons validate --type dataset --slug cptac-gbm-2021-proteogenomics --format json
```

Expected:

- Commons entity validation reports zero errors for the dataset.
- Validation accepts every `source.ref` using `${OUTPUT_ROOT}/...`.
- Validation accepts every resource hash as `sha256:<64 lowercase hex>`.

- [ ] **Step 8: Run benchmark report smoke checks**

Run from `~/d/science`:

```bash
SCIENCE_COMMONS_ROOT="$(cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics && pwd -P)" \
SCIENCE_COMMONS_DATA_ROOT="$(cd ~/d/science-commons-data && pwd -P)" \
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science \
  science benchmark list --commons --format json | rg "cptac-gbm-2021-proteogenomics"

SCIENCE_COMMONS_ROOT="$(cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics && pwd -P)" \
SCIENCE_COMMONS_DATA_ROOT="$(cd ~/d/science-commons-data && pwd -P)" \
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science \
  science benchmark tests --commons --format json \
  --benchmark dataset:cptac-gbm-2021-proteogenomics \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma
```

Expected:

- The benchmark list includes `dataset:cptac-gbm-2021-proteogenomics`.
- The benchmark tests command returns at least one row for `protein-rna-cross-modal`.
- Because `SCIENCE_COMMONS_ROOT` points at the commons feature worktree, the commands see the branch-local entity before merge.
- After generated resources are visible through `SCIENCE_COMMONS_DATA_ROOT`, readiness should be `runnable`; if it is not, inspect the datapackage refs, hashes, and data override before committing.

- [ ] **Step 9: Commit validation updates**

Run:

```bash
cd ~/d/science-commons/.worktrees/cptac-gbm-2021-proteogenomics
git status --short
git add datasets/cptac-gbm-2021-proteogenomics
git commit -m "feat: stage CPTAC GBM benchmark recipe"
```

Expected:

- Commit includes metadata, recipe code, tests, fixtures, docs, and `datapackage.yaml`.
- Commit does not include generated raw payloads, parquet files, or `~/d/science-commons-data` content.

---

## Self-Review

- Spec coverage: The plan covers the new child deposit, LFS batch fetch route, hash verification, sample alignment, local-only generated resources, datapackage rendering, operator docs, `science commons validate`, and benchmark report smoke checks.
- Placeholder scan: No deferred-work markers or vague "add tests" steps are present. The initial zero hashes in `datapackage.yaml` are intentionally replaced by `build_datapackage.py` before commons validation.
- Type consistency: Dataset id, task id, profile ids, sample-list ids, file names, LFS object ids, and output resource paths match the 2026-07-03 fetchability spike.

## Execution Handoff

Plan complete and saved to `docs/plans/2026-07-03-cptac-gbm-deposit-recipe-implementation-plan.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

The implementation edits `~/d/science-commons`, so request filesystem escalation before writing commons files in this sandbox.
