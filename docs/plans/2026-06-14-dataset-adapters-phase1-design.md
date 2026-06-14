---
title: Dataset adapters — Phase 1 (domain repositories)
date: 2026-06-14
status: design
---

# Dataset Adapters · Phase 1 Design

## 1. Intent

The `science_tool.datasets` package already implements the generalized
repository-adapter system: a `DatasetAdapter` protocol (`search` / `metadata` /
`files` / `download`), normalized `DatasetResult` / `FileInfo` types, a registry
(`register` / `get_adapter` / `available_adapters`), a fan-out `search_all` with
per-source error degradation, and an adapter-agnostic CLI
(`science datasets sources | search | metadata | files | download | validate`).
Five adapters are wired in: `zenodo`, `dryad`, `geo`, `semantic_scholar`,
`cbioportal`.

The gap is **coverage**, exposed concretely by task `t001` (rhythm-aware
health-state datasets) in the `health-cycles` project: the repositories that
actually hold chronobiology / physiological-rhythm data had to be verified
*manually against source records* because no adapter covers them — PhysioNet
(MMASH actigraphy + clock genes), ArrayExpress/BioStudies (E-MTAB-* circadian
omics), figshare (CGM datasets), and others. GEO is the only domain-relevant
source currently wired in.

This phase adds **four adapters** — `figshare`, `arrayexpress`, `physionet`,
`sra` — to close that gap. A later **Phase 2** (separate spec) will improve the
search *quality* layer (relevance scoring, cross-source dedup, richer fields
surfaced in the CLI). Phase 1 is breadth only.

### Goals

- Add four self-contained adapters following the existing `zenodo.py` / `geo.py`
  pattern, each independently testable with no live network in tests.
- Make the rhythm-relevant repositories that `t001` needs discoverable through
  `science datasets search` (no new CLI commands; one small output change in §2.2).
- Signal access tier (public / restricted / controlled) where the repository
  forces the distinction (PhysioNet, SRA), via a canonical vocabulary (§2.1).

### Non-goals

- No relevance ranking, scoring, or cross-source dedup (that is Phase 2).
- No NSRR / NHANES adapters — DUA-gated cohort portals and fixed file portals do
  not fit the search-adapter shape; they stay manual.
- No new CLI commands. The only CLI edit is surfacing `access` in `search` /
  `metadata` output rows (§2.2).

## 2. Architecture

Mostly-unchanged core. Each adapter is a self-contained class implementing the
existing `DatasetAdapter` protocol, constructed with its own `httpx.Client`,
registered in `datasets/__init__.py::_auto_register()` via a `try/except
ImportError` block. `search_all` already provides per-source error degradation;
adapter *discovery/search/download* is adapter-agnostic, so the new sources
participate in `science datasets sources` / `search` / `download` with no change.
Each adapter file is ~80–130 lines, matching `zenodo.py` / `geo.py`.

One small CLI change *is* required (see §2.2): the new `access` field is dropped
by the current output unless `search` and `metadata` rows are extended to carry
it.

### 2.1 Shared-schema change (additive)

Add one optional field to `DatasetResult` in `datasets/_base.py`:

```python
access: str | None = None   # canonical: "public" | "restricted" | "controlled" | None
```

Rationale: PhysioNet (Open/Restricted/Credentialed projects) and SRA (dbGaP
controlled tiers) force the public-vs-gated distinction, and `/find-datasets`
already maps an `access` tier into dataset entities, so surfacing it from search
is directly useful and feeds Phase 2 ranking. The field is optional and
defaulted, so no existing adapter or test breaks. Existing adapters leave it
`None`.

**Canonical access vocabulary.** To prevent adapters from encoding tiers
inconsistently (and to give the entity layer one thing to translate),
`DatasetResult.access` uses exactly three values plus `None`:

| Canonical | Meaning | Maps from |
|---|---|---|
| `public` | freely downloadable, no agreement | figshare, arrayexpress, zenodo, dryad; PhysioNet `Open`; SRA public |
| `restricted` | self-serve gate (click-through DUA / login), no application | PhysioNet `Restricted` |
| `controlled` | application/approval required | PhysioNet `Credentialed`; SRA dbGaP |
| `None` | unknown / not determined | any adapter that cannot tell |

**Crosswalk to the dataset-entity vocabulary** (`commands/find-datasets.md`
uses `access.level ∈ {public, controlled, mixed}`):

- `public` → `public`
- `restricted` → `controlled`
- `controlled` → `controlled`
- `mixed` is **not** an adapter-level value — it is emergent at entity-emission
  time when sibling artefacts differ in level, per the existing emission rules.

This crosswalk is the single canonical mapping; the `/find-datasets` step
applies it when populating `access.level`.

### 2.2 CLI change (surface `access`)

The current CLI builds explicit rows that omit `access`, and JSON output
(`output.py::emit_query_rows`) serializes exactly those rows — so the field is
silently dropped without this change:

- `datasets_search` (`cli.py` ~line 2974): add `"access": r.access or ""` to each
  row and an `("access", "Access")` column.
- `datasets_metadata` (`cli.py` ~line 3010): add an
  `{"field": "Access", "value": result.access or ""}` row.

No change to `output.py` or `files`/`download` commands.

## 3. The four adapters

### 3.1 `figshare`

Base: `https://api.figshare.com/v2` — clean public REST API.

| Method | Endpoint | Notes |
|---|---|---|
| `search` | `POST /articles/search` | body `{search_for: query, item_type: 3, page_size: max_results}` — `item_type: 3` restricts to datasets |
| `metadata` | `GET /articles/{id}` | title, `doi`, `published_date`→year, `license.name`→license, `tags`→keywords, `url`→`url_public_html` |
| `files` | from `GET /articles/{id}` `files[]` | `name`, `download_url`, `size`, `computed_md5`→checksum |
| `download` | stream `download_url` | standard streaming pattern |

`access`: always `"public"` (search returns public articles only).

### 3.2 `arrayexpress`

Base: `https://www.ebi.ac.uk/biostudies/api/v1` — EBI BioStudies REST, scoped to
the **ArrayExpress collection**.

| Method | Endpoint | Notes |
|---|---|---|
| `search` | `GET /arrayexpress/search?query=&pageSize=` | hits with `accession` (E-MTAB-*), `title`, `release_date`→year |
| `metadata` | `GET /studies/{accession}` | parse section attributes: `organism` attribute → organism; experiment/study type → modality |
| `files` | study `files[]` listing | `path`→filename, `size` |
| `download` | stream file URL under `/files/{accession}/...` | standard streaming pattern |

**Design decision (confirmed):** scope to the `arrayexpress` collection rather
than a general `biostudies` adapter — the full BioStudies collection is mostly
irrelevant submissions, and `t001` needs the E-MTAB circadian omics
specifically. Adapter `name = "arrayexpress"`. Generalizing to all of BioStudies
later is a one-line endpoint change.

`access`: `"public"`.

### 3.3 `physionet`

Base: `https://physionet.org/api/v1` — **first-class JSON API** (verified live;
matches the official MIT-LCP `physionet` client's `projects` endpoints). No HTML
scraping is required.

| Method | Endpoint | Notes |
|---|---|---|
| `search` | `GET /projects/search/?search_term=&resource_type=` | array of projects; fields: `slug`, `version`, `title`, `abstract`/`short_description`, `version_doi`/`core_doi`, `publish_date`→year, `license.name`, `access_policy`, `topics`→keywords, `main_storage_size`, `source_url` |
| `metadata` | `GET /projects/{slug}/versions/{version}/` | full project detail (the client's `get_details`) |
| `files` | `GET /projects/published/{slug}/{version}/sha256sums/` | parse `<sha256>␠␠<path>` lines → `FileInfo(filename=path, url=…/files/{slug}/{version}/{path}, checksum=sha256, format=<ext inferred from path>, size_bytes=None)`. The `sha256sums` body carries **only** checksum + path, so `size_bytes` is `None` unless a future JSON/file-listing source provides per-file bytes |
| `download` | stream `https://physionet.org/files/{slug}/{version}/{path}` | for `Restricted`/`Credentialed` projects, **raise `PermissionError` with `source_url`** instead of persisting a 403/login body |

Adapter `id` is the project `slug`; `metadata("slug")` resolves to the latest
version via `GET /projects/{slug}/versions/` when no version is pinned.

`access`: from `access_policy` — `Open`→`public`, `Restricted`→`restricted`,
`Credentialed`→`controlled` (per the §2.1 canonical vocabulary).

This adapter is now pure-JSON like the others; the only residual fragility is the
plain-text `sha256sums` parsing, isolated in a private `_parse_sha256sums`
helper and fixture-pinned in tests.

### 3.4 `sra`

Base: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` — reuses the `geo.py`
E-utilities pattern, including `NCBI_API_KEY` handling.

| Method | Endpoint | Notes |
|---|---|---|
| `search` | `esearch.fcgi?db=sra&term=&retmax=` → UIDs → `esummary.fcgi?db=sra&id=...` | parse the embedded `ExpXml` blob (Title, Organism, Platform→modality) and `Runs` (SRR accessions, spots/bases/size) |
| `metadata` | `esearch` with `{acc}[Accession]` then `esummary` | accession = SRR/SRX/SRP/SRA |
| `files` | per-run `.sra` URLs: `https://sra-pub-run-odp.s3.amazonaws.com/sra/{SRR}/{SRR}` | `format="sra"`; downstream `fasterq-dump` conversion is noted, not performed here |
| `download` | stream the per-run `.sra` URL | standard streaming pattern |

`access`: `"public"`, or `"controlled"` when the summary flags dbGaP /
controlled access.

## 4. Cross-cutting concerns

- **Rate limits:** SRA shares GEO's NCBI budget (3 req/s, 10 with key). Honor
  `NCBI_API_KEY` exactly as `geo.py` does (client constructed with the key in
  default params).
- **Error degradation:** adapters call `raise_for_status()` and let `search_all`
  skip a failing source (existing behavior, already tested for the rate-limited
  case). Gated `download()` raises actionable `PermissionError` / `ValueError`
  rather than persisting an error body.
- **Registration:** four new `try/except ImportError` blocks in
  `_auto_register()` registering `figshare`, `arrayexpress`, `physionet`, `sra`.

## 5. Testing

Per adapter, following the established `MagicMock` + `patch.object(adapter,
"_client")` style (no live network) in `science/tests/test_datasets.py`:

- `test_name`
- `test_search_parses_response`
- `test_metadata_parses_record`
- `test_files`
- `test_access_tier` for `physionet` (Open→public, Restricted→restricted,
  Credentialed→controlled) and `sra` (dbGaP→controlled).
- Edge cases: empty search results; gated-access `download()` raises for
  `physionet` (restricted/credentialed) and `sra` (controlled).

Fixtures: a PhysioNet `projects/search/` JSON response and a `sha256sums`
text body; an SRA `esummary` XML with an `ExpXml` blob — small, representative,
saved as test fixtures.

Registry: extend the existing registry test to assert `figshare`,
`arrayexpress`, `physionet`, `sra` all appear in `available_adapters()`.

CLI: extend `science/tests/test_datasets_cli.py` to assert the `Access` column
appears in `datasets search` output and the `Access` field in `datasets
metadata` output (both table and JSON), so the §2.2 change is regression-guarded.

## 6. Documentation

- Update `commands/find-datasets.md` — the "Adapters cover …" line (currently
  ~line 73) and the limitations note — to list the four new sources and the
  PhysioNet/SRA access caveats.
- Document the §2.1 access crosswalk in `commands/find-datasets.md` near the
  `access` entity-field guidance (~line 119), so the step that populates
  `access.level` applies `public→public`, `restricted→controlled`,
  `controlled→controlled` consistently.
- Mirror the adapter-list change into `codex-skills/science-find-datasets/SKILL.md`
  if it duplicates the list.

## 7. Validation

From `~/d/science`:

```bash
uv run pytest science/tests/test_datasets.py science/tests/test_datasets_cli.py
uv run ruff check science/src/science_tool/datasets science/src/science_tool/cli.py
```

## 8. Out of scope → Phase 2 (separate spec)

- Relevance scoring / ranking inside `search_all` (today it concatenates; the
  LLM ranks in the skill).
- Cross-source dedup (same DOI surfacing from Zenodo + Dryad + figshare).
- Richer result fields surfaced in the CLI `search` table (modality, organism,
  sample_count). `access` is already surfaced in Phase 1 (§2.2).
- Optional follow-on adapters: `osf`, and a generalized `biostudies` toggle.
