# Phase 4c: Operationalization — Design Document

## Goal

Add dataset discovery, acquisition, and validation tooling to Science, completing Stage C ("Operationalize") of the staged research model.
Researchers should be able to find relevant public datasets, download them with provenance tracking, validate them against Frictionless Data Package standards, and connect them into reproducible pipelines via Snakemake and Marimo.

## Scope

1. **Dataset adapter system** — Unified Python interface for searching and downloading from public repositories
2. **`/science:find-datasets` command** — LLM-driven dataset discovery orchestrated by adapter searches
3. **Data validation tooling** — Frictionless Data Package checks + dataset-variable mapping against inquiry graphs
4. **Skills** — `skills/data/frictionless.md`, `skills/pipelines/snakemake.md`, `skills/pipelines/marimo.md`
5. **Templates** — `templates/pipeline-step.md`, `templates/experiment.md`

## Non-goals

- Building a full ETL framework — adapters handle discovery and download, not transformation
- Wrapping every possible data source — tiered rollout, start with 4
- Automated pipeline generation — skills guide the agent, which writes pipelines
- PyMC export — deferred unless needed by a real project

---

## 1. Dataset Adapter System

### Architecture

```
science_tool/
  datasets/
    __init__.py          # Registry, shared types, pooch-based download
    _base.py             # AdapterBase protocol + DatasetResult/FileInfo types
    zenodo.py            # Zenodo REST adapter
    dryad.py             # Dryad REST adapter
    geo.py               # GEO E-utilities + FTP adapter
    semantic_scholar.py  # Semantic Scholar Graph API adapter
```

All adapters are **optional** — installed via `[datasets]` extra.
Core dependency: `httpx` (async HTTP, already used by distill).
Download/cache: `pooch` (hash verification, DOI resolution, caching).

### Adapter Protocol

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from pathlib import Path


@dataclass(frozen=True)
class DatasetResult:
    """A dataset found by search."""
    source: str                          # e.g. "zenodo", "geo"
    id: str                              # Source-specific ID (DOI, accession, etc.)
    title: str
    description: str = ""
    doi: str | None = None
    url: str | None = None               # Landing page
    year: int | None = None
    license: str | None = None
    keywords: list[str] = field(default_factory=list)
    organism: str | None = None          # For bio datasets
    modality: str | None = None          # e.g. "RNA-seq", "proteomics", "survey"
    sample_count: int | None = None
    file_count: int | None = None
    total_size_bytes: int | None = None


@dataclass(frozen=True)
class FileInfo:
    """A downloadable file within a dataset."""
    filename: str
    url: str
    size_bytes: int | None = None
    checksum: str | None = None          # "sha256:abc..." or "md5:abc..."
    format: str | None = None            # e.g. "csv", "h5ad", "fastq.gz"


@runtime_checkable
class DatasetAdapter(Protocol):
    """Common interface for dataset repository adapters."""

    name: str  # e.g. "zenodo"

    def search(self, query: str, *, max_results: int = 20) -> list[DatasetResult]:
        """Search for datasets matching a query string."""
        ...

    def metadata(self, dataset_id: str) -> DatasetResult:
        """Get full metadata for a dataset by its source-specific ID."""
        ...

    def files(self, dataset_id: str) -> list[FileInfo]:
        """List downloadable files in a dataset."""
        ...

    def download(self, file_info: FileInfo, dest_dir: Path) -> Path:
        """Download a file to dest_dir. Returns local path. Uses pooch for caching/verification."""
        ...
```

### Source-Specific Notes

**Zenodo** (`zenodo.py`)
- Base: `https://zenodo.org/api/`
- Search: `GET /records?q={query}&type=dataset&sort=mostrecent`
- Metadata: `GET /records/{id}` — files included in response
- Download: direct HTTP via file URLs, pooch for caching
- IDs: Zenodo record ID, DOI

**Dryad** (`dryad.py`)
- Base: `https://datadryad.org/api/v2`
- Search: `GET /search?q={query}`
- Metadata: `GET /datasets/{doi}` (URL-encoded DOI)
- Files: `GET /versions/{version_id}/files`
- Download: `GET /files/{file_id}/download`
- IDs: DOI

**GEO** (`geo.py`)
- Search: E-utilities `esearch.fcgi?db=gds&term={query}`
- Metadata: `esummary.fcgi?db=gds&id={uid}`
- Files: Parse FTP directory structure from metadata
- Download: HTTPS mirror of FTP (`https://ftp.ncbi.nlm.nih.gov/geo/series/...`)
- IDs: GSE/GSM/GPL accessions
- Rate limit: 3 req/s (no key), 10 req/s (with NCBI API key from env)

**Semantic Scholar** (`semantic_scholar.py`)
- Base: `https://api.semanticscholar.org/graph/v1`
- Search: `GET /paper/search?query={query}&fields=...`
- Metadata: `GET /paper/{id}` (accepts DOI, PMID, S2 ID, ArXiv ID)
- Files: n/a (literature, not data files — but links datasets via openAccessPdf, externalIds)
- This adapter is literature-focused: useful for finding papers that reference datasets, complementing OpenAlex/PubMed
- IDs: S2 Paper ID, DOI, PMID

### Registry

```python
# datasets/__init__.py

_ADAPTERS: dict[str, type[DatasetAdapter]] = {}

def register(name: str, cls: type[DatasetAdapter]) -> None:
    _ADAPTERS[name] = cls

def get_adapter(name: str) -> DatasetAdapter:
    return _ADAPTERS[name]()

def available_adapters() -> list[str]:
    return sorted(_ADAPTERS)

def search_all(query: str, *, sources: list[str] | None = None, max_per_source: int = 10) -> list[DatasetResult]:
    """Fan out search across multiple adapters, merge results."""
    targets = sources or list(_ADAPTERS)
    results: list[DatasetResult] = []
    for name in targets:
        adapter = _ADAPTERS[name]()
        results.extend(adapter.search(query, max_results=max_per_source))
    return results
```

Adapters self-register at import time.
`search_all` is the main entry point for the CLI and command.

### CLI Surface

New command group `datasets` under `science-tool`:

```
science-tool datasets search <query> [--source zenodo,geo,...] [--max N] [--format table|json]
science-tool datasets metadata <source>:<id> [--format table|json]
science-tool datasets files <source>:<id> [--format table|json]
science-tool datasets download <source>:<id> [--file PATTERN] [--dest data/raw/]
science-tool datasets sources                    # list available adapters
```

The `<source>:<id>` convention (e.g. `zenodo:12345`, `geo:GSE12345`, `dryad:doi:10.5061/dryad.abc123`) keeps addressing unambiguous.

### Dependencies

New optional extra in `pyproject.toml`:

```toml
[project.optional-dependencies]
datasets = [
    "httpx>=0.27",
    "pooch>=1.8",
]
```

No heavy dependencies — `httpx` for HTTP, `pooch` for download/cache/hash.
GEO may optionally use `GEOparse` for SOFT parsing, but the adapter itself only needs httpx.

---

## 2. `/science:find-datasets` Command

### Purpose

Agent-driven dataset discovery.
The agent uses project context (research question, hypotheses, inquiry variables) to suggest candidate datasets, then uses the adapter tools to verify availability and document findings.

### Workflow

1. **Setup** — Follow command preamble (role: `research-assistant`). Load `skills/data/SKILL.md` and `skills/data/frictionless.md`.
2. **Context gathering** — Read `specs/research-question.md`, active hypotheses, inquiry variables (if any inquiry exists). Identify what data the project needs.
3. **LLM candidate generation** — Based on context, suggest 5-10 candidate datasets with rationale. Include known accessions/DOIs where possible.
4. **Adapter-driven search** — Run `science-tool datasets search` across relevant sources to find matching datasets. Cross-reference LLM suggestions with actual search results.
5. **Ranking** — Rank candidates by: relevance to project variables, data quality signals, accessibility (license, format), sample size, recency.
6. **Documentation** — For top candidates, create dataset notes in `doc/datasets/` using `templates/dataset.md`. Update `science.yaml` data sources.
7. **Variable mapping** — If an inquiry exists, map dataset variables to inquiry variables and flag gaps (datasets that don't cover needed variables, or variables with no dataset coverage).
8. **Next steps** — Suggest download commands, preprocessing needs, and pipeline planning.

### Output

- `doc/datasets/data-<slug>.md` for each selected dataset (using existing template)
- `doc/searches/YYYY-MM-DD-datasets-<slug>.json` machine-readable search results
- Updates to `science.yaml` data_sources section

---

## 3. Data Validation Tooling

### Frictionless Data Package Checks

Add a `science-tool datasets validate` command that checks:

1. **Schema presence** — `data/raw/datapackage.json` and `data/processed/datapackage.json` exist
2. **Schema validity** — Each `datapackage.json` is valid per Frictionless spec (uses `frictionless` Python library)
3. **Resource integrity** — Files referenced in the descriptor exist and match declared checksums/sizes
4. **Field type conformance** — Tabular resources match their declared schema (column names, types)

```
science-tool datasets validate [--path data/] [--format table|json]
```

This integrates with `validate.sh` — the script can call `science-tool datasets validate` as an additional check.

### Dataset-Variable Mapping

When an inquiry exists, validate that declared datasets cover the inquiry's variables:

```
science-tool datasets check-coverage <inquiry-slug> [--format table|json]
```

This reads:
- Inquiry variables from the knowledge graph
- Dataset field schemas from `datapackage.json` files
- Dataset-variable mappings from `science.yaml` or `doc/datasets/*.md` metadata

Output: a coverage matrix showing which datasets provide which variables, and flagging unmapped variables.

### Dependencies

New optional extra:

```toml
[project.optional-dependencies]
datasets = [
    "httpx>=0.27",
    "pooch>=1.8",
    "frictionless>=5.0",   # data package validation
]
```

---

## 4. Skills

### `skills/data/frictionless.md`

Teaches the agent how to:
- Create and maintain `datapackage.json` descriptors
- Define tabular resource schemas (field names, types, constraints)
- Use `frictionless describe` to auto-generate schemas from data files
- Validate data packages and interpret validation reports
- Connect data package resources to inquiry variables
- When to use Frictionless vs. ad-hoc data loading

### `skills/pipelines/snakemake.md`

Teaches the agent how to:
- Structure a `Snakefile` in `code/pipelines/`
- Write rules that consume `data/raw/` and produce `data/processed/`
- Use config files for parameters (connect to inquiry AnnotatedParams)
- Handle conda/container environments per rule
- Integrate with `science-tool datasets download` for data acquisition rules
- Run and debug Snakemake workflows
- Best practices: rule naming, wildcards, checkpoints, benchmarks

### `skills/pipelines/marimo.md`

Teaches the agent how to:
- Create reactive notebooks in `code/notebooks/`
- Structure notebooks for reproducible analysis (data loading → processing → visualization → export)
- Use `marimo.ui` for interactive parameter exploration
- Connect to inquiry variables and data packages
- Export results to `data/processed/` with provenance
- When to use marimo vs. Snakemake (exploration vs. production)

---

## 5. Templates

### `templates/pipeline-step.md`

Compact documentation template for a single pipeline step/rule:
- Input/output files
- Tool/library used
- Parameters (linked to inquiry AnnotatedParams)
- Validation criteria
- Runtime estimates

### `templates/experiment.md`

Documentation template for a computational experiment:
- Hypothesis being tested
- Pipeline steps involved
- Expected vs. actual results
- Interpretation and next steps

---

## 6. Tiered Rollout

### Tier 1 (this implementation)
- Dataset adapter system with Zenodo, Dryad, GEO, Semantic Scholar
- `/science:find-datasets` command
- `science-tool datasets` CLI group (search, metadata, files, download, sources, validate)
- `skills/data/frictionless.md`
- `skills/pipelines/snakemake.md`
- `skills/pipelines/marimo.md`
- `templates/pipeline-step.md`, `templates/experiment.md`
- Frictionless validation in `science-tool datasets validate`
- Dataset-variable coverage check

### Tier 2 (future)
- Figshare, CKAN, Dataverse, CellxGene adapters
- `gget` integration skill (`skills/data/sources/gget.md`)
- Enhanced download with resume/parallel support
- Automated `datapackage.json` generation from downloaded data

### Tier 3 (future)
- ARCHS4, recount3, PubTator3, OpenCitations adapters
- Cross-source deduplication (same dataset on Zenodo + Dryad)
- Dataset recommendation engine (based on inquiry graph similarity)

---

## 7. How It Connects

```
Research Question
    ↓
/science:find-datasets  ←  LLM suggestions + adapter searches
    ↓
doc/datasets/*.md  +  data/raw/datapackage.json
    ↓
science-tool datasets validate   ← Frictionless checks
    ↓
science-tool datasets check-coverage <inquiry>  ← variable mapping
    ↓
/science:plan-pipeline  ← generates Snakefile structure
    ↓
skills/pipelines/snakemake.md  +  skills/pipelines/marimo.md  ← guide agent
    ↓
code/pipelines/Snakefile  +  code/notebooks/*.py
```

The adapter system is the foundation: it provides reliable, provenance-tracked data acquisition.
The skills teach the agent how to use the tools.
The command orchestrates the workflow.
Validation ensures data quality before it enters pipelines.
