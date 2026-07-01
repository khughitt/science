# MMRF CoMMpass Staging Recipe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative MMRF CoMMpass staging recipe that can dry-run GDC metadata discovery, validate whether the existing `progression-risk` task is promotable, and build/test a tiny fixture package without promoting the commons entity yet.

**Architecture:** The recipe lives with the shared commons dataset at `~/d/science-commons/datasets/mmrf-commpass/recipe/`. `fetch_manifest.py` owns GDC metadata queries, manifest normalization, endpoint discovery, and optional expression-file download; `build.py` owns fixture/full package construction and split validation; `build_datapackage.py` renders a local datapackage only after build outputs exist. The existing `dataset:mmrf-commpass` entity remains `dataset_class: pointer` until a full staged package passes validation gates.

**Tech Stack:** Python 3.13, `urllib.request` for HTTP, `yaml`, `pandas`, `pyarrow`, pytest, existing `science_tool.commons.config.resolve_commons_data_root`, existing `science_tool.commons.datapackage.OUTPUT_ROOT_TOKEN` and `stream_sha256_and_bytes`.

---

## Scope And Repos

Implementation touches two repositories:

- `~/d/science`: plan/design docs only.
- `~/d/science-commons`: recipe implementation and recipe tests.

The active implementation worktree is:

```bash
cd ~/d/science/.worktrees/mmrf-commpass-staging-recipe
```

The commons repo is not inside the writable root for the science worktree. When editing `~/d/science-commons`, use approved/escalated tool execution rather than trying to work around sandbox restrictions.

## File Structure

Create these files in `~/d/science-commons/datasets/mmrf-commpass/recipe/`:

- `README.md` — operator documentation and exact dry-run/build/datapackage commands.
- `manifest.schema.yaml` — schema contract for `manifest/files.parquet` and `reports/validation.json`.
- `fetch_manifest.py` — GDC status/file/case query helpers, manifest normalization, endpoint discovery, dry-run output, optional expression download.
- `build.py` — expression TSV parsing, sample/outcome table construction from manifest + cases payload, deterministic held-out-patient split generation, validation report writing.
- `build_datapackage.py` — render `datasets/mmrf-commpass/datapackage.yaml` from staged output hashes.
- `test_mmrf_recipe.py` — pytest tests for the recipe.
- `fixtures/expression_counts.tsv` — tiny representative GDC augmented STAR-style count TSV.
- `fixtures/files_page.json` — tiny representative GDC files response.
- `fixtures/cases_progression.json` — tiny representative cases response with progression-like fields.
- `fixtures/cases_survival_only.json` — tiny representative cases response with OS-only fields.

Do not edit `~/d/science-commons/datasets/mmrf-commpass/entity.md` in this plan except for comments/docs if a later review explicitly asks. This plan must leave `dataset_class: pointer`.

---

### Task 1: Recipe Test Harness And Fixtures

**Files:**
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures/expression_counts.tsv`
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures/files_page.json`
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures/cases_progression.json`
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures/cases_survival_only.json`

- [ ] **Step 1: Create the fixture directory**

Run:

```bash
mkdir -p ~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures
```

Expected: directory exists.

- [ ] **Step 2: Add representative expression TSV fixture**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures/expression_counts.tsv`:

```text
gene_id	gene_name	gene_type	unstranded	stranded_first	stranded_second	tpm_unstranded	fpkm_unstranded	fpkm_uq_unstranded
N_unmapped		__summary__	10	0	0	0	0	0
ENSG00000141510.18	TP53	protein_coding	100	50	50	12.5	3.1	4.2
ENSG00000171862.13	PTEN	protein_coding	80	40	40	9.0	2.4	3.3
```

- [ ] **Step 3: Add representative files page fixture**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures/files_page.json`:

```json
{
  "data": {
    "hits": [
      {
        "id": "01888e3c-45ec-493f-9a8a-57cada28dc6c",
        "file_id": "01888e3c-45ec-493f-9a8a-57cada28dc6c",
        "file_name": "1b166f66-85d0-4c18-aaee-fe0abe0338d1.rna_seq.augmented_star_gene_counts.tsv",
        "data_category": "Transcriptome Profiling",
        "data_type": "Gene Expression Quantification",
        "data_format": "TSV",
        "experimental_strategy": "RNA-Seq",
        "access": "open",
        "file_size": 12345,
        "md5sum": "5eb63bbbe01eeed093cb22bb8f5acdc3",
        "cases": [
          {
            "case_id": "case-1",
            "submitter_id": "MMRF_0001",
            "samples": [
              {
                "submitter_id": "MMRF_0001_1_BM_CD138pos",
                "sample_type": "Primary Blood Derived Cancer - Bone Marrow"
              }
            ]
          }
        ]
      },
      {
        "id": "cecfa7eb-7774-4acb-a939-7fc2c6e6ef10",
        "file_id": "cecfa7eb-7774-4acb-a939-7fc2c6e6ef10",
        "file_name": "28ee3050-59fa-4b12-ae15-94b8314e6f6b.rna_seq.augmented_star_gene_counts.tsv",
        "data_category": "Transcriptome Profiling",
        "data_type": "Gene Expression Quantification",
        "data_format": "TSV",
        "experimental_strategy": "RNA-Seq",
        "access": "open",
        "file_size": 67890,
        "md5sum": "5eb63bbbe01eeed093cb22bb8f5acdc3",
        "cases": [
          {
            "case_id": "case-2",
            "submitter_id": "MMRF_0002",
            "samples": [
              {
                "submitter_id": "MMRF_0002_1_BM_CD138pos",
                "sample_type": "Primary Blood Derived Cancer - Bone Marrow"
              }
            ]
          }
        ]
      }
    ],
    "pagination": {
      "count": 2,
      "total": 2,
      "size": 2,
      "from": 0,
      "page": 1,
      "pages": 1
    }
  },
  "warnings": {}
}
```

- [ ] **Step 4: Add progression-capable cases fixture**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures/cases_progression.json`:

```json
{
  "data": {
    "hits": [
      {
        "case_id": "case-1",
        "submitter_id": "MMRF_0001",
        "diagnoses": [
          {
            "days_to_progression": 450,
            "progression_or_recurrence": "yes",
            "vital_status": "Alive",
            "days_to_last_follow_up": 700
          }
        ]
      },
      {
        "case_id": "case-2",
        "submitter_id": "MMRF_0002",
        "diagnoses": [
          {
            "days_to_progression": 900,
            "progression_or_recurrence": "no",
            "vital_status": "Alive",
            "days_to_last_follow_up": 900
          }
        ]
      }
    ],
    "pagination": {
      "count": 2,
      "total": 2,
      "size": 2,
      "from": 0,
      "page": 1,
      "pages": 1
    }
  },
  "warnings": {}
}
```

- [ ] **Step 5: Add OS-only cases fixture**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/fixtures/cases_survival_only.json`:

```json
{
  "data": {
    "hits": [
      {
        "case_id": "case-1",
        "submitter_id": "MMRF_0001",
        "diagnoses": [
          {
            "vital_status": "Dead",
            "days_to_death": 500,
            "days_to_last_follow_up": 500
          }
        ]
      },
      {
        "case_id": "case-2",
        "submitter_id": "MMRF_0002",
        "diagnoses": [
          {
            "vital_status": "Alive",
            "days_to_last_follow_up": 900
          }
        ]
      }
    ],
    "pagination": {
      "count": 2,
      "total": 2,
      "size": 2,
      "from": 0,
      "page": 1,
      "pages": 1
    }
  },
  "warnings": {}
}
```

- [ ] **Step 6: Add failing recipe tests**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`:

```python
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

RECIPE_DIR = Path(__file__).parent
sys.path.insert(0, str(RECIPE_DIR))


def _fixture(name: str) -> Path:
    return RECIPE_DIR / "fixtures" / name


def _load_json(name: str) -> dict:
    return json.loads(_fixture(name).read_text(encoding="utf-8"))


def test_file_filter_is_open_rnaseq_gene_expression_tsv():
    from fetch_manifest import build_file_filter

    filt = build_file_filter()
    assert filt == {
        "op": "and",
        "content": [
            {"op": "in", "content": {"field": "cases.project.project_id", "value": ["MMRF-COMMPASS"]}},
            {"op": "in", "content": {"field": "access", "value": ["open"]}},
            {"op": "in", "content": {"field": "data_type", "value": ["Gene Expression Quantification"]}},
            {"op": "in", "content": {"field": "experimental_strategy", "value": ["RNA-Seq"]}},
            {"op": "in", "content": {"field": "data_format", "value": ["TSV"]}},
        ],
    }


def test_normalize_file_hit_extracts_case_sample_and_urls():
    from fetch_manifest import normalize_file_hit

    hit = _load_json("files_page.json")["data"]["hits"][0]
    row = normalize_file_hit(hit)
    assert row["file_id"] == "01888e3c-45ec-493f-9a8a-57cada28dc6c"
    assert row["case_id"] == "case-1"
    assert row["case_submitter_id"] == "MMRF_0001"
    assert row["sample_submitter_id"] == "MMRF_0001_1_BM_CD138pos"
    assert row["access"] == "open"
    assert row["gdc_download_url"].endswith("/data/01888e3c-45ec-493f-9a8a-57cada28dc6c")
    assert row["aws_s3_uri"].endswith("/01888e3c-45ec-493f-9a8a-57cada28dc6c/")


def test_manifest_count_must_match_independent_count():
    from fetch_manifest import validate_manifest_count

    with pytest.raises(ValueError, match="manifest count"):
        validate_manifest_count([{"file_id": "a"}, {"file_id": "b"}], expected_total=3)
    validate_manifest_count([{"file_id": "a"}, {"file_id": "b"}], expected_total=2)


def test_endpoint_discovery_accepts_progression_and_rejects_survival_only():
    from fetch_manifest import discover_endpoint_fields

    progression = discover_endpoint_fields(_load_json("cases_progression.json")["data"]["hits"])
    assert progression["status"] == "progression-ready"
    assert "days_to_progression" in progression["progression_fields"]
    assert "progression_or_recurrence" in progression["progression_fields"]

    survival_only = discover_endpoint_fields(_load_json("cases_survival_only.json")["data"]["hits"])
    assert survival_only["status"] == "survival-only"
    assert "vital_status" in survival_only["survival_fields"]
    assert survival_only["progression_fields"] == []


def test_write_dry_run_outputs_manifest_query_and_validation(tmp_path):
    from fetch_manifest import StaticGdcClient, write_dry_run

    client = StaticGdcClient(
        status_payload={
            "data_release": "Data Release 45.0 - December 04, 2025",
            "commit": "fixture",
            "status": "OK",
        },
        file_total=2,
        file_pages=[_load_json("files_page.json")],
        case_pages=[_load_json("cases_progression.json")],
    )
    report = write_dry_run(output_dir=tmp_path, client=client)
    assert report["endpoint_status"] == "progression-ready"
    assert report["file_count"] == 2
    assert (tmp_path / "manifest" / "files.parquet").is_file()
    assert (tmp_path / "manifest" / "query.json").is_file()
    assert (tmp_path / "reports" / "validation.json").is_file()
    manifest = pd.read_parquet(tmp_path / "manifest" / "files.parquet")
    assert list(manifest["file_id"]) == [
        "01888e3c-45ec-493f-9a8a-57cada28dc6c",
        "cecfa7eb-7774-4acb-a939-7fc2c6e6ef10",
    ]


def test_write_dry_run_refuses_survival_only_for_progression_task(tmp_path):
    from fetch_manifest import StaticGdcClient, write_dry_run

    client = StaticGdcClient(
        status_payload={
            "data_release": "Data Release 45.0 - December 04, 2025",
            "commit": "fixture",
            "status": "OK",
        },
        file_total=2,
        file_pages=[_load_json("files_page.json")],
        case_pages=[_load_json("cases_survival_only.json")],
    )
    with pytest.raises(ValueError, match="overall-survival"):
        write_dry_run(output_dir=tmp_path, client=client)


def test_parse_expression_tsv_selects_measure_and_skips_summary_rows(tmp_path):
    from build import parse_expression_tsv

    rows = parse_expression_tsv(
        _fixture("expression_counts.tsv"),
        sample_submitter_id="MMRF_0001_1_BM_CD138pos",
        case_submitter_id="MMRF_0001",
        measure="tpm_unstranded",
    )
    assert rows == [
        {
            "case_submitter_id": "MMRF_0001",
            "sample_submitter_id": "MMRF_0001_1_BM_CD138pos",
            "gene_id": "ENSG00000141510.18",
            "gene_name": "TP53",
            "measure": "tpm_unstranded",
            "value": 12.5,
        },
        {
            "case_submitter_id": "MMRF_0001",
            "sample_submitter_id": "MMRF_0001_1_BM_CD138pos",
            "gene_id": "ENSG00000171862.13",
            "gene_name": "PTEN",
            "measure": "tpm_unstranded",
            "value": 9.0,
        },
    ]


def test_build_package_writes_tables_and_deterministic_splits(tmp_path):
    from build import build_package

    source_dir = tmp_path / "_src" / "expression"
    source_dir.mkdir(parents=True)
    for file_id in ["01888e3c-45ec-493f-9a8a-57cada28dc6c", "cecfa7eb-7774-4acb-a939-7fc2c6e6ef10"]:
        (source_dir / f"{file_id}.tsv").write_text(_fixture("expression_counts.tsv").read_text(encoding="utf-8"), encoding="utf-8")

    manifest_dir = tmp_path / "manifest"
    manifest_dir.mkdir()
    rows = []
    for hit in _load_json("files_page.json")["data"]["hits"]:
        from fetch_manifest import normalize_file_hit

        rows.append(normalize_file_hit(hit))
    pd.DataFrame(rows).to_parquet(manifest_dir / "files.parquet", index=False)
    (manifest_dir / "cases.json").write_text(json.dumps(_load_json("cases_progression.json")["data"]["hits"]), encoding="utf-8")

    summary = build_package(output_dir=tmp_path, measure="tpm_unstranded", split_salt="fixture-salt")
    assert summary["expression_rows"] == 4
    assert summary["outcome_rows"] == 2
    assert summary["split_salt"] == "fixture-salt"
    assert (tmp_path / "data" / "expression.parquet").is_file()
    assert (tmp_path / "data" / "samples.parquet").is_file()
    assert (tmp_path / "data" / "outcomes.parquet").is_file()
    assert (tmp_path / "splits" / "heldout_patient_v1.parquet").is_file()

    splits = pd.read_parquet(tmp_path / "splits" / "heldout_patient_v1.parquet")
    assert sorted(splits["case_submitter_id"]) == ["MMRF_0001", "MMRF_0002"]
    assert set(splits["split"]) <= {"train", "validation", "test"}


def test_build_package_refuses_patient_leakage():
    from build import validate_no_patient_leakage

    validate_no_patient_leakage(
        pd.DataFrame(
            [
                {"case_submitter_id": "MMRF_0001", "split": "train"},
                {"case_submitter_id": "MMRF_0002", "split": "test"},
            ]
        )
    )
    with pytest.raises(ValueError, match="leakage"):
        validate_no_patient_leakage(
            pd.DataFrame(
                [
                    {"case_submitter_id": "MMRF_0001", "split": "train"},
                    {"case_submitter_id": "MMRF_0001", "split": "test"},
                ]
            )
        )


def test_build_datapackage_doc_records_resources_and_split_method(tmp_path):
    from build_datapackage import build_datapackage_doc

    for rel, payload in {
        "manifest/files.parquet": b"manifest",
        "manifest/query.json": b"{}",
        "data/expression.parquet": b"expr",
        "data/samples.parquet": b"samples",
        "data/outcomes.parquet": b"outcomes",
        "splits/heldout_patient_v1.parquet": b"splits",
        "reports/validation.json": b'{"split_salt":"fixture-salt"}',
    }.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    doc = build_datapackage_doc(tmp_path, split_salt="fixture-salt", gdc_data_release="Data Release 45.0 - December 04, 2025")
    assert doc["name"] == "mmrf-commpass"
    assert doc["gdc_data_release"] == "Data Release 45.0 - December 04, 2025"
    assert doc["split"]["method"] == "sha256(case_submitter_id || split_salt)"
    assert doc["split"]["split_salt"] == "fixture-salt"
    resource_names = {r["name"] for r in doc["resources"]}
    assert resource_names == {"files_manifest", "query", "expression", "samples", "outcomes", "heldout_patient_split", "validation"}
    expression = next(r for r in doc["resources"] if r["name"] == "expression")
    assert expression["hash"] == "sha256:" + hashlib.sha256(b"expr").hexdigest()
    assert expression["source"]["ref"].endswith("/mmrf-commpass/data/expression.parquet")


def test_entity_remains_pointer_until_promoted():
    entity_text = (RECIPE_DIR.parent / "entity.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(entity_text.split("---", 2)[1])
    assert fm["dataset_class"] == "pointer"
    assert "datapackage" not in fm
```

- [ ] **Step 7: Run tests to verify they fail**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py -q
```

Expected: FAIL during collection with missing modules such as `ModuleNotFoundError: No module named 'fetch_manifest'`.

- [ ] **Step 8: Commit failing tests and fixtures**

Run:

```bash
cd ~/d/science-commons
rtk git add datasets/mmrf-commpass/recipe/test_mmrf_recipe.py datasets/mmrf-commpass/recipe/fixtures
rtk git commit -m "test(dataset): add MMRF recipe coverage"
```

Expected: commit succeeds.

---

### Task 2: GDC Manifest Dry-Run

**Files:**
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/fetch_manifest.py`
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`

- [ ] **Step 1: Implement the GDC manifest module**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/fetch_manifest.py`:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

import pandas as pd

from science_tool.commons.config import resolve_commons_data_root

# science:code
# status: exploratory
# science:end

DATASET_NAME = "mmrf-commpass"
PROJECT_ID = "MMRF-COMMPASS"
GDC_API = "https://api.gdc.cancer.gov"
GDC_DATA_ENDPOINT = f"{GDC_API}/data"
AWS_BUCKET_URI = "s3://gdc-mmrf-commpass-phs000748-2-open"
FILE_FIELDS = [
    "file_id",
    "file_name",
    "data_category",
    "data_type",
    "data_format",
    "experimental_strategy",
    "access",
    "file_size",
    "md5sum",
    "cases.case_id",
    "cases.submitter_id",
    "cases.samples.submitter_id",
    "cases.samples.sample_type",
]
CASE_FIELDS = [
    "case_id",
    "submitter_id",
    "diagnoses.days_to_progression",
    "diagnoses.progression_or_recurrence",
    "diagnoses.days_to_recurrence",
    "diagnoses.vital_status",
    "diagnoses.days_to_death",
    "diagnoses.days_to_last_follow_up",
]
PROGRESSION_FIELD_NAMES = frozenset(
    {
        "days_to_progression",
        "progression_or_recurrence",
        "days_to_recurrence",
        "progression_free_survival",
        "pfs",
        "time_to_progression",
    }
)
SURVIVAL_FIELD_NAMES = frozenset({"vital_status", "days_to_death", "days_to_last_follow_up"})


class GdcClient(Protocol):
    def status(self) -> dict[str, Any]:
        raise NotImplementedError

    def count_files(self, filters: dict[str, Any]) -> int:
        raise NotImplementedError

    def iter_files(self, filters: dict[str, Any]) -> Iterable[dict[str, Any]]:
        raise NotImplementedError

    def iter_cases(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class StaticGdcClient:
    status_payload: dict[str, Any]
    file_total: int
    file_pages: list[dict[str, Any]]
    case_pages: list[dict[str, Any]]

    def status(self) -> dict[str, Any]:
        return self.status_payload

    def count_files(self, filters: dict[str, Any]) -> int:
        return self.file_total

    def iter_files(self, filters: dict[str, Any]) -> Iterable[dict[str, Any]]:
        for page in self.file_pages:
            yield from page["data"]["hits"]

    def iter_cases(self) -> Iterable[dict[str, Any]]:
        for page in self.case_pages:
            yield from page["data"]["hits"]


@dataclass(frozen=True, slots=True)
class LiveGdcClient:
    api_base: str = GDC_API
    page_size: int = 500

    def status(self) -> dict[str, Any]:
        return _get_json(f"{self.api_base}/status")

    def count_files(self, filters: dict[str, Any]) -> int:
        params = {"size": 0, "filters": json.dumps(filters, separators=(",", ":"))}
        payload = _get_json(f"{self.api_base}/files?{urllib.parse.urlencode(params)}")
        return int(payload["data"]["pagination"]["total"])

    def iter_files(self, filters: dict[str, Any]) -> Iterable[dict[str, Any]]:
        yield from _iter_endpoint(
            f"{self.api_base}/files",
            params={
                "filters": json.dumps(filters, separators=(",", ":")),
                "fields": ",".join(FILE_FIELDS),
                "expand": "cases.samples",
            },
            page_size=self.page_size,
        )

    def iter_cases(self) -> Iterable[dict[str, Any]]:
        filters = {
            "op": "in",
            "content": {"field": "project.project_id", "value": [PROJECT_ID]},
        }
        yield from _iter_endpoint(
            f"{self.api_base}/cases",
            params={
                "filters": json.dumps(filters, separators=(",", ":")),
                "fields": ",".join(CASE_FIELDS),
                "expand": "diagnoses",
            },
            page_size=self.page_size,
        )


def build_file_filter() -> dict[str, Any]:
    return {
        "op": "and",
        "content": [
            {"op": "in", "content": {"field": "cases.project.project_id", "value": [PROJECT_ID]}},
            {"op": "in", "content": {"field": "access", "value": ["open"]}},
            {"op": "in", "content": {"field": "data_type", "value": ["Gene Expression Quantification"]}},
            {"op": "in", "content": {"field": "experimental_strategy", "value": ["RNA-Seq"]}},
            {"op": "in", "content": {"field": "data_format", "value": ["TSV"]}},
        ],
    }


def normalize_file_hit(hit: dict[str, Any]) -> dict[str, Any]:
    file_id = str(hit.get("file_id") or hit.get("id") or "").strip()
    if not file_id:
        raise ValueError("GDC file hit is missing file_id")
    cases = hit.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{file_id}: missing cases")
    case = cases[0]
    samples = case.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError(f"{file_id}: missing case sample")
    sample = samples[0]
    return {
        "project_id": PROJECT_ID,
        "file_id": file_id,
        "file_name": _required_str(hit, "file_name"),
        "data_category": _required_str(hit, "data_category"),
        "data_type": _required_str(hit, "data_type"),
        "data_format": _required_str(hit, "data_format").upper(),
        "experimental_strategy": _required_str(hit, "experimental_strategy"),
        "access": _required_str(hit, "access"),
        "file_size": int(hit.get("file_size") or 0),
        "md5sum": str(hit.get("md5sum") or "").strip(),
        "case_id": _required_str(case, "case_id"),
        "case_submitter_id": _required_str(case, "submitter_id"),
        "sample_submitter_id": _required_str(sample, "submitter_id"),
        "sample_type": _required_str(sample, "sample_type"),
        "gdc_download_url": f"{GDC_DATA_ENDPOINT}/{file_id}",
        "aws_s3_uri": f"{AWS_BUCKET_URI}/{file_id}/",
    }


def validate_manifest_count(rows: list[dict[str, Any]], *, expected_total: int) -> None:
    file_ids = [str(row["file_id"]) for row in rows]
    if len(file_ids) != len(set(file_ids)):
        raise ValueError("manifest contains duplicate file_id values")
    if len(file_ids) != expected_total:
        raise ValueError(f"manifest count {len(file_ids)} does not match independent GDC total {expected_total}")


def discover_endpoint_fields(cases: list[dict[str, Any]]) -> dict[str, Any]:
    flattened = [_flatten_case(case) for case in cases]
    present = {key for row in flattened for key, value in row.items() if value not in (None, "")}
    progression = sorted(present & PROGRESSION_FIELD_NAMES)
    survival = sorted(present & SURVIVAL_FIELD_NAMES)
    if progression:
        status = "progression-ready"
    elif survival:
        status = "survival-only"
    else:
        status = "missing-endpoint"
    return {
        "status": status,
        "progression_fields": progression,
        "survival_fields": survival,
        "case_count": len(cases),
    }


def write_dry_run(*, output_dir: Path, client: GdcClient) -> dict[str, Any]:
    filters = build_file_filter()
    status = client.status()
    expected_total = client.count_files(filters)
    rows = [normalize_file_hit(hit) for hit in client.iter_files(filters)]
    validate_manifest_count(rows, expected_total=expected_total)
    cases = list(client.iter_cases())
    endpoint = discover_endpoint_fields(cases)
    report = {
        "gdc_data_release": status.get("data_release", ""),
        "gdc_commit": status.get("commit", ""),
        "project_id": PROJECT_ID,
        "file_filter": filters,
        "file_count": len(rows),
        "independent_file_total": expected_total,
        "case_count": len(cases),
        "endpoint_status": endpoint["status"],
        "progression_fields": endpoint["progression_fields"],
        "survival_fields": endpoint["survival_fields"],
        "promotable": endpoint["status"] == "progression-ready",
    }
    if endpoint["status"] == "survival-only":
        _write_metadata_outputs(output_dir=output_dir, rows=rows, cases=cases, filters=filters, report=report)
        raise ValueError("overall-survival fields were found, but progression-risk promotion requires progression/relapse fields")
    if endpoint["status"] != "progression-ready":
        _write_metadata_outputs(output_dir=output_dir, rows=rows, cases=cases, filters=filters, report=report)
        raise ValueError("progression-risk endpoint fields are unavailable in open GDC metadata")
    _write_metadata_outputs(output_dir=output_dir, rows=rows, cases=cases, filters=filters, report=report)
    return report


def download_expression_files(*, output_dir: Path, manifest_rows: list[dict[str, Any]], client: LiveGdcClient | None = None) -> None:
    del client
    source_dir = output_dir / "_src" / "expression"
    source_dir.mkdir(parents=True, exist_ok=True)
    for row in manifest_rows:
        file_id = str(row["file_id"])
        path = source_dir / f"{file_id}.tsv"
        if not path.exists():
            _download(row["gdc_download_url"], path)
        expected_size = int(row.get("file_size") or 0)
        if expected_size and path.stat().st_size != expected_size:
            raise ValueError(f"{path}: byte count mismatch")
        expected_md5 = str(row.get("md5sum") or "").strip()
        if expected_md5 and _md5(path) != expected_md5:
            raise ValueError(f"{path}: md5 mismatch")


def resolve_output_dir(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    if "SCIENCE_COMMONS_DATA_ROOT" in os.environ:
        return resolve_commons_data_root() / DATASET_NAME
    raise ValueError("--output-dir is required unless SCIENCE_COMMONS_DATA_ROOT is set")


def _write_metadata_outputs(
    *,
    output_dir: Path,
    rows: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    filters: dict[str, Any],
    report: dict[str, Any],
) -> None:
    (output_dir / "manifest").mkdir(parents=True, exist_ok=True)
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(output_dir / "manifest" / "files.parquet", index=False)
    (output_dir / "manifest" / "cases.json").write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "manifest" / "query.json").write_text(json.dumps(filters, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "reports" / "validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _iter_endpoint(url: str, *, params: dict[str, str], page_size: int) -> Iterable[dict[str, Any]]:
    offset = 0
    while True:
        merged = {**params, "size": str(page_size), "from": str(offset)}
        payload = _get_json(f"{url}?{urllib.parse.urlencode(merged)}")
        data = payload["data"]
        hits = data["hits"]
        yield from hits
        pagination = data["pagination"]
        offset += len(hits)
        if offset >= int(pagination["total"]) or not hits:
            break


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with urllib.request.urlopen(url) as response, tmp_path.open("wb") as fh:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            fh.write(chunk)
    tmp_path.replace(output_path)


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_str(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"missing required field {key}")
    return value


def _flatten_case(case: dict[str, Any]) -> dict[str, Any]:
    out = {
        "case_id": case.get("case_id"),
        "case_submitter_id": case.get("submitter_id"),
    }
    diagnoses = case.get("diagnoses")
    if isinstance(diagnoses, list) and diagnoses:
        diagnosis = diagnoses[0]
        if isinstance(diagnosis, dict):
            out.update(diagnosis)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an MMRF CoMMpass GDC manifest and optional open expression download.")
    parser.add_argument("--output-dir", type=str)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Write manifest and validation report only.")
    mode.add_argument("--download-expression", action="store_true", help="Write manifest, validation report, and expression TSV downloads.")
    args = parser.parse_args()
    output_dir = resolve_output_dir(args.output_dir)
    client = LiveGdcClient()
    report = write_dry_run(output_dir=output_dir, client=client)
    if args.download_expression:
        manifest = pd.read_parquet(output_dir / "manifest" / "files.parquet").to_dict(orient="records")
        download_expression_files(output_dir=output_dir, manifest_rows=manifest, client=client)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run focused dry-run tests**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py \
  -k 'file_filter or normalize_file_hit or manifest_count or endpoint_discovery or write_dry_run' -q
```

Expected: PASS for dry-run tests, FAIL/DESELECT for tests needing `build.py` or `build_datapackage.py` if the full file is run without `-k`.

- [ ] **Step 3: Run all recipe tests to verify remaining failures**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py -q
```

Expected: FAIL with missing module/function errors for `build` and `build_datapackage`.

- [ ] **Step 4: Commit manifest dry-run implementation**

Run:

```bash
cd ~/d/science-commons
rtk git add datasets/mmrf-commpass/recipe/fetch_manifest.py datasets/mmrf-commpass/recipe/test_mmrf_recipe.py
rtk git commit -m "feat(dataset): add MMRF GDC manifest dry run"
```

Expected: commit succeeds.

---

### Task 3: Build Fixture Package And Split Validation

**Files:**
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/build.py`
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`

- [ ] **Step 1: Implement package build module**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/build.py`:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from fetch_manifest import DATASET_NAME, discover_endpoint_fields
from science_tool.commons.config import resolve_commons_data_root

# science:code
# status: exploratory
# science:end

DEFAULT_MEASURE = "tpm_unstranded"
DEFAULT_SPLIT_SALT = "mmrf-commpass-heldout-patient-v1"


def parse_expression_tsv(
    path: Path,
    *,
    sample_submitter_id: str,
    case_submitter_id: str,
    measure: str,
) -> list[dict[str, Any]]:
    table = pd.read_csv(path, sep="\t", dtype={"gene_id": "string", "gene_name": "string"})
    required = {"gene_id", "gene_name", measure}
    missing = required - set(table.columns)
    if missing:
        raise ValueError(f"{path}: missing expression columns {sorted(missing)}")
    rows: list[dict[str, Any]] = []
    for row in table.to_dict(orient="records"):
        gene_id = str(row["gene_id"])
        if gene_id.startswith("N_"):
            continue
        rows.append(
            {
                "case_submitter_id": case_submitter_id,
                "sample_submitter_id": sample_submitter_id,
                "gene_id": gene_id,
                "gene_name": str(row["gene_name"]),
                "measure": measure,
                "value": float(row[measure]),
            }
        )
    return rows


def build_package(*, output_dir: Path, measure: str = DEFAULT_MEASURE, split_salt: str = DEFAULT_SPLIT_SALT) -> dict[str, Any]:
    manifest_path = output_dir / "manifest" / "files.parquet"
    cases_path = output_dir / "manifest" / "cases.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing manifest: {manifest_path}")
    if not cases_path.is_file():
        raise ValueError(f"missing cases metadata: {cases_path}")

    manifest = pd.read_parquet(manifest_path)
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    endpoint = discover_endpoint_fields(cases)
    if endpoint["status"] != "progression-ready":
        raise ValueError(f"progression-risk endpoint is not promotable: {endpoint['status']}")

    expression_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    for row in manifest.to_dict(orient="records"):
        file_id = str(row["file_id"])
        source_path = output_dir / "_src" / "expression" / f"{file_id}.tsv"
        if not source_path.is_file():
            raise ValueError(f"missing expression source file: {source_path}")
        expression_rows.extend(
            parse_expression_tsv(
                source_path,
                sample_submitter_id=str(row["sample_submitter_id"]),
                case_submitter_id=str(row["case_submitter_id"]),
                measure=measure,
            )
        )
        sample_rows.append(
            {
                "case_id": str(row["case_id"]),
                "case_submitter_id": str(row["case_submitter_id"]),
                "sample_submitter_id": str(row["sample_submitter_id"]),
                "sample_type": str(row["sample_type"]),
                "file_id": file_id,
                "file_name": str(row["file_name"]),
            }
        )

    outcomes = _build_outcomes(cases)
    expression = pd.DataFrame(expression_rows)
    samples = pd.DataFrame(sample_rows).drop_duplicates()
    outcomes_df = pd.DataFrame(outcomes).drop_duplicates()
    split_df = build_patient_splits(sorted(outcomes_df["case_submitter_id"].unique()), split_salt=split_salt)
    validate_no_patient_leakage(split_df)

    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "splits").mkdir(parents=True, exist_ok=True)
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)
    expression.to_parquet(output_dir / "data" / "expression.parquet", index=False)
    samples.to_parquet(output_dir / "data" / "samples.parquet", index=False)
    outcomes_df.to_parquet(output_dir / "data" / "outcomes.parquet", index=False)
    split_df.to_parquet(output_dir / "splits" / "heldout_patient_v1.parquet", index=False)

    summary = {
        "expression_rows": int(len(expression)),
        "sample_rows": int(len(samples)),
        "outcome_rows": int(len(outcomes_df)),
        "split_rows": int(len(split_df)),
        "measure": measure,
        "split_method": "sha256(case_submitter_id || split_salt)",
        "split_salt": split_salt,
    }
    (output_dir / "reports" / "build-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def build_patient_splits(case_submitter_ids: list[str], *, split_salt: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for case_id in case_submitter_ids:
        digest = hashlib.sha256(f"{case_id}{split_salt}".encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        if bucket < 0.8:
            split = "train"
        elif bucket < 0.9:
            split = "validation"
        else:
            split = "test"
        rows.append({"case_submitter_id": case_id, "split": split, "split_basis": digest})
    return pd.DataFrame(rows)


def validate_no_patient_leakage(split_df: pd.DataFrame) -> None:
    counts = split_df.groupby("case_submitter_id")["split"].nunique()
    leaked = sorted(counts[counts > 1].index)
    if leaked:
        raise ValueError(f"held-out-patient split leakage for cases: {leaked}")


def resolve_output_dir(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    if "SCIENCE_COMMONS_DATA_ROOT" in os.environ:
        return resolve_commons_data_root() / DATASET_NAME
    raise ValueError("--output-dir is required unless SCIENCE_COMMONS_DATA_ROOT is set")


def _build_outcomes(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        diagnoses = case.get("diagnoses")
        diagnosis = diagnoses[0] if isinstance(diagnoses, list) and diagnoses else {}
        if not isinstance(diagnosis, dict):
            diagnosis = {}
        days = diagnosis.get("days_to_progression") or diagnosis.get("days_to_recurrence")
        status = diagnosis.get("progression_or_recurrence")
        if days in (None, "") or status in (None, ""):
            continue
        rows.append(
            {
                "case_id": str(case.get("case_id") or ""),
                "case_submitter_id": str(case.get("submitter_id") or ""),
                "endpoint": "progression_or_recurrence",
                "time_to_event_days": int(days),
                "event_observed": str(status).strip().lower() in {"yes", "true", "1", "progression", "recurrence"},
                "source_days_field": "days_to_progression" if diagnosis.get("days_to_progression") not in (None, "") else "days_to_recurrence",
                "source_status_field": "progression_or_recurrence",
            }
        )
    if not rows:
        raise ValueError("no progression outcome rows could be derived")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the MMRF CoMMpass progression-risk package from a GDC manifest.")
    parser.add_argument("--output-dir", type=str)
    parser.add_argument("--measure", default=DEFAULT_MEASURE)
    parser.add_argument("--split-salt", default=DEFAULT_SPLIT_SALT)
    args = parser.parse_args()
    summary = build_package(output_dir=resolve_output_dir(args.output_dir), measure=args.measure, split_salt=args.split_salt)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run build-focused tests**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py \
  -k 'parse_expression or build_package or patient_leakage' -q
```

Expected: PASS.

- [ ] **Step 3: Run all recipe tests to verify remaining failures**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py -q
```

Expected: FAIL only for `test_build_datapackage_doc_records_resources_and_split_method` because `build_datapackage.py` does not exist yet.

- [ ] **Step 4: Commit build implementation**

Run:

```bash
cd ~/d/science-commons
rtk git add datasets/mmrf-commpass/recipe/build.py datasets/mmrf-commpass/recipe/test_mmrf_recipe.py
rtk git commit -m "feat(dataset): build MMRF fixture package"
```

Expected: commit succeeds.

---

### Task 4: Datapackage Renderer

**Files:**
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/build_datapackage.py`
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`

- [ ] **Step 1: Implement datapackage renderer**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/build_datapackage.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.config import resolve_commons_data_root
from science_tool.commons.datapackage import OUTPUT_ROOT_TOKEN, stream_sha256_and_bytes

# science:code
# status: exploratory
# science:end

DATASET_NAME = "mmrf-commpass"
RESOURCE_FILES = {
    "files_manifest": ("manifest/files.parquet", "parquet", "application/vnd.apache.parquet"),
    "query": ("manifest/query.json", "json", "application/json"),
    "expression": ("data/expression.parquet", "parquet", "application/vnd.apache.parquet"),
    "samples": ("data/samples.parquet", "parquet", "application/vnd.apache.parquet"),
    "outcomes": ("data/outcomes.parquet", "parquet", "application/vnd.apache.parquet"),
    "heldout_patient_split": ("splits/heldout_patient_v1.parquet", "parquet", "application/vnd.apache.parquet"),
    "validation": ("reports/validation.json", "json", "application/json"),
}


def build_datapackage_doc(data_dir: Path, *, split_salt: str, gdc_data_release: str) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    for name, (rel_path, fmt, mediatype) in RESOURCE_FILES.items():
        path = data_dir / rel_path
        sha256, byte_count = stream_sha256_and_bytes(path)
        resources.append(
            {
                "name": name,
                "path": rel_path,
                "format": fmt,
                "mediatype": mediatype,
                "source": {
                    "type": "local",
                    "ref": f"{OUTPUT_ROOT_TOKEN}/{DATASET_NAME}/{rel_path}",
                },
                "hash": sha256,
                "bytes": byte_count,
            }
        )
    return {
        "name": DATASET_NAME,
        "gdc_data_release": gdc_data_release,
        "split": {
            "method": "sha256(case_submitter_id || split_salt)",
            "split_salt": split_salt,
            "thresholds": {"train": "<0.8", "validation": ">=0.8 and <0.9", "test": ">=0.9"},
        },
        "resources": resources,
    }


def render_datapackage_text(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render MMRF CoMMpass datapackage.yaml from staged package outputs.")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output-path", type=Path, default=Path(__file__).parent.parent / "datapackage.yaml")
    parser.add_argument("--split-salt", required=True)
    parser.add_argument("--gdc-data-release", required=True)
    args = parser.parse_args()
    data_dir = args.data_dir or resolve_commons_data_root() / DATASET_NAME
    doc = build_datapackage_doc(data_dir, split_salt=args.split_salt, gdc_data_release=args.gdc_data_release)
    args.output_path.write_text(render_datapackage_text(doc), encoding="utf-8")
    print(f"wrote {args.output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run datapackage-focused test**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py \
  -k 'build_datapackage' -q
```

Expected: PASS.

- [ ] **Step 3: Run all recipe tests**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit datapackage renderer**

Run:

```bash
cd ~/d/science-commons
rtk git add datasets/mmrf-commpass/recipe/build_datapackage.py datasets/mmrf-commpass/recipe/test_mmrf_recipe.py
rtk git commit -m "feat(dataset): render MMRF datapackage metadata"
```

Expected: commit succeeds.

---

### Task 5: Recipe Documentation And Manifest Schema

**Files:**
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/README.md`
- Create: `~/d/science-commons/datasets/mmrf-commpass/recipe/manifest.schema.yaml`

- [ ] **Step 1: Add manifest schema**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/manifest.schema.yaml`:

```yaml
manifest_files:
  required_columns:
    - project_id
    - file_id
    - file_name
    - data_category
    - data_type
    - data_format
    - experimental_strategy
    - access
    - file_size
    - md5sum
    - case_id
    - case_submitter_id
    - sample_submitter_id
    - sample_type
    - gdc_download_url
    - aws_s3_uri
  filters:
    cases.project.project_id: MMRF-COMMPASS
    access: open
    data_type: Gene Expression Quantification
    experimental_strategy: RNA-Seq
    data_format: TSV
validation_report:
  required_fields:
    - gdc_data_release
    - project_id
    - file_count
    - independent_file_total
    - case_count
    - endpoint_status
    - progression_fields
    - survival_fields
    - promotable
split:
  method: "sha256(case_submitter_id || split_salt)"
  default_split_salt: "mmrf-commpass-heldout-patient-v1"
```

- [ ] **Step 2: Add README**

Create `~/d/science-commons/datasets/mmrf-commpass/recipe/README.md`:

```markdown
# MMRF CoMMpass Progression-Risk Recipe

This recipe prepares an open-access, task-specific staging package for
`dataset:mmrf-commpass#progression-risk`.

The commons entity remains `dataset_class: pointer` until a full package passes
the validation gates. The recipe uses GDC metadata as the source of truth and
uses AWS Open Data only as an optional transport mirror once file ids are known.

## Outputs

Tracked files live in `~/d/science-commons/datasets/mmrf-commpass/recipe/`.
Staged data belongs outside git, for example:

```bash
~/d/science-commons-data/mmrf-commpass
```

The output tree is:

```text
manifest/files.parquet
manifest/query.json
manifest/cases.json
data/expression.parquet
data/samples.parquet
data/outcomes.parquet
splits/heldout_patient_v1.parquet
reports/validation.json
reports/build-summary.json
```

## Dry Run

The dry run queries GDC, writes the manifest, records the GDC data release, and
checks whether open clinical metadata contains progression/relapse fields.

```bash
cd ~/d/science-commons/datasets/mmrf-commpass
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python recipe/fetch_manifest.py \
  --dry-run \
  --output-dir ~/d/science-commons-data/mmrf-commpass
```

If only overall-survival fields are available, the dry run writes a validation
report and exits nonzero. Do not use overall-survival-only metadata to promote
the existing `progression-risk` task.

## Download Open Expression Files

This can download hundreds of files. Run it only after reviewing the dry-run
manifest.

```bash
cd ~/d/science-commons/datasets/mmrf-commpass
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python recipe/fetch_manifest.py \
  --download-expression \
  --output-dir ~/d/science-commons-data/mmrf-commpass
```

## Build Package

```bash
cd ~/d/science-commons/datasets/mmrf-commpass
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python recipe/build.py \
  --output-dir ~/d/science-commons-data/mmrf-commpass \
  --measure tpm_unstranded \
  --split-salt mmrf-commpass-heldout-patient-v1
```

## Render Datapackage

Only render and commit `datapackage.yaml` after the staged package passes the
validation gates.

```bash
cd ~/d/science-commons/datasets/mmrf-commpass
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python recipe/build_datapackage.py \
  --data-dir ~/d/science-commons-data/mmrf-commpass \
  --split-salt mmrf-commpass-heldout-patient-v1 \
  --gdc-data-release "Data Release 45.0 - December 04, 2025" \
  --output-path datapackage.yaml
```

## Promotion Gate

Promotion requires all of these:

- independent GDC count equals manifest file count;
- expression files are present and byte/hash checks pass when source metadata
  provides those values;
- expression rows join to sample metadata;
- progression/relapse outcome rows are nonempty;
- held-out-patient splits are deterministic and have no patient leakage;
- `science commons validate --type dataset --slug mmrf-commpass --json` passes
  after the future entity/datapackage promotion.
```

- [ ] **Step 3: Run recipe tests**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit docs/schema**

Run:

```bash
cd ~/d/science-commons
rtk git add datasets/mmrf-commpass/recipe/README.md datasets/mmrf-commpass/recipe/manifest.schema.yaml
rtk git commit -m "docs(dataset): document MMRF staging recipe"
```

Expected: commit succeeds.

---

### Task 6: Live Dry-Run Smoke And No-Promotion Verification

**Files:**
- No code files.
- Generated local output under: `~/d/science-commons-data/mmrf-commpass/`

- [ ] **Step 1: Run live dry run against GDC**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python recipe/fetch_manifest.py \
  --dry-run \
  --output-dir ~/d/science-commons-data/mmrf-commpass
```

Expected outcomes:

- If GDC open clinical contains progression/relapse fields, command exits 0 and writes `reports/validation.json` with `"endpoint_status": "progression-ready"`.
- If GDC open clinical is OS-only, command exits nonzero with an overall-survival/progression-risk message and still writes `manifest/files.parquet`, `manifest/query.json`, `manifest/cases.json`, and `reports/validation.json`.
- In both cases, no commons entity metadata is mutated.

- [ ] **Step 2: Inspect validation report**

Run:

```bash
python - <<'PY'
from pathlib import Path
import json

path = Path('~/d/science-commons-data/mmrf-commpass/reports/validation.json').expanduser()
report = json.loads(path.read_text(encoding='utf-8'))
print(json.dumps({
    'gdc_data_release': report.get('gdc_data_release'),
    'file_count': report.get('file_count'),
    'independent_file_total': report.get('independent_file_total'),
    'endpoint_status': report.get('endpoint_status'),
    'progression_fields': report.get('progression_fields'),
    'survival_fields': report.get('survival_fields'),
    'promotable': report.get('promotable'),
}, indent=2, sort_keys=True))
PY
```

Expected: printed JSON explains whether MMRF is promotable for `progression-risk`. If `promotable` is false, stop before download/build work and report that MMRF remains a metadata-only benchmark target.

- [ ] **Step 3: Verify entity is unchanged**

Run:

```bash
python - <<'PY'
from pathlib import Path
import yaml

entity = Path('~/d/science-commons/datasets/mmrf-commpass/entity.md').expanduser()
fm = yaml.safe_load(entity.read_text(encoding='utf-8').split('---', 2)[1])
print({'dataset_class': fm.get('dataset_class'), 'datapackage': fm.get('datapackage')})
assert fm.get('dataset_class') == 'pointer'
assert 'datapackage' not in fm
PY
```

Expected: prints `{'dataset_class': 'pointer', 'datapackage': None}` and exits 0.

- [ ] **Step 4: Run full recipe tests**

Run:

```bash
cd ~/d/science-commons/datasets/mmrf-commpass/recipe
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science pytest test_mmrf_recipe.py -q
```

Expected: PASS.

- [ ] **Step 5: Run commons validation for MMRF entity**

Run:

```bash
cd ~/d/science
rtk uv run --frozen --project science science commons validate --type dataset --slug mmrf-commpass --json
```

Expected: JSON reports `"checked": 1` and `"errors": []`.

- [ ] **Step 6: Check git status in both repos**

Run:

```bash
cd ~/d/science-commons
rtk git status --short --branch
cd ~/d/science/.worktrees/mmrf-commpass-staging-recipe
rtk git status --short --branch
```

Expected:

- `science-commons` has only intended commits and no uncommitted recipe files.
- science worktree has only the plan file changes, if not already committed.
- generated data under `~/d/science-commons-data/mmrf-commpass/` does not appear in git status.

---

## Self-Review Checklist

Spec coverage:

- GDC as metadata source of truth: Task 2.
- AWS as transport mirror only after file ids are known: Task 2 `aws_s3_uri` and README wording.
- Open RNA-seq GEQ TSV filter: Task 2 `build_file_filter`.
- Independent count-only total vs paginated manifest count: Task 2 `validate_manifest_count`.
- Endpoint-label crux and OS-only refusal: Task 1 tests, Task 2 endpoint discovery, Task 6 live dry-run inspection.
- Expression-measure selection: Task 3 `measure`, README build command.
- Separate tracked recipe and out-of-git data locations: Task 5 README.
- Explicit output dir / `SCIENCE_COMMONS_DATA_ROOT`: Task 2 and Task 3 `resolve_output_dir`, Task 5 commands.
- Deterministic split basis: Task 3 `build_patient_splits`, Task 4 datapackage split metadata.
- No promotion of `dataset:mmrf-commpass`: Task 1 `test_entity_remains_pointer_until_promoted`, Task 6 entity verification.
- Datapackage rendering after validation: Task 4, but no entity promotion in this plan.

Placeholder scan:

- The plan intentionally avoids reserved placeholder markers and ellipsis
  placeholders.

Type consistency:

- `output_dir`, `measure`, and `split_salt` are used consistently across tests, `build.py`, `build_datapackage.py`, and README commands.
- `file_id`, `case_submitter_id`, and `sample_submitter_id` are the stable join keys across manifest, expression, samples, outcomes, and splits.
