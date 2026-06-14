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
  `science datasets search` with no CLI changes.
- Signal access tier (public vs. credentialed/controlled) where the repository
  forces the distinction (PhysioNet, SRA).

### Non-goals

- No relevance ranking, scoring, or cross-source dedup (that is Phase 2).
- No NSRR / NHANES adapters — DUA-gated cohort portals and fixed file portals do
  not fit the search-adapter shape; they stay manual.
- No CLI surface changes.

## 2. Architecture

Unchanged core. Each adapter is a self-contained class implementing the existing
`DatasetAdapter` protocol, constructed with its own `httpx.Client`, registered
in `datasets/__init__.py::_auto_register()` via a `try/except ImportError`
block. `search_all` already provides per-source error degradation; the CLI is
adapter-agnostic, so the new sources appear automatically in
`science datasets sources` and participate in `search`. Each adapter file is
~80–130 lines, matching `zenodo.py` / `geo.py`.

### 2.1 Shared-schema change (additive)

Add one optional field to `DatasetResult` in `datasets/_base.py`:

```python
access: str | None = None   # "public" | "credentialed" | "controlled" | None
```

Rationale: PhysioNet (open vs. credentialed projects) and SRA (dbGaP controlled
tiers) force the public-vs-gated distinction, and `/find-datasets` already maps
an `access` tier into dataset entities, so surfacing it from search is directly
useful and feeds Phase 2 ranking. The field is optional and defaulted, so no
existing adapter or test breaks. Existing adapters leave it `None`; `zenodo`,
`dryad`, `figshare`, `arrayexpress` may set `"public"` since their search
surfaces public records only.

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

Base: `https://physionet.org` — **no first-class search API**; this is the
highest-maintenance-risk adapter.

| Method | Approach | Notes |
|---|---|---|
| `search` | fetch the published-projects index, substring/keyword-match `query` against project titles | parse access policy (open vs. credentialed) and version from the listing |
| `metadata` | fetch + parse the project landing page | title, version, access policy → `access` |
| `files` | parse the `/files/{slug}/{version}/` directory listing | filename, size where available |
| `download` | stream open-access file URLs; **raise `PermissionError` with the access URL for credentialed projects** | never write a 403 HTML body to disk |

HTML parsing is isolated in a private helper (`_parse_project_index`,
`_parse_file_listing`) and pinned to small saved HTML fixtures in tests. This
adapter is flagged as the most fragile — index/landing-page markup changes will
break it first; the fixture-pinned tests localize the failure.

`access`: `"public"` for open projects, `"credentialed"` for credentialed ones.

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
- Edge cases: empty search results; gated-access path raises for `physionet`
  (credentialed project) and `sra` (controlled).

Fixtures: PhysioNet project-index + file-listing HTML, and an SRA `esummary`
XML with an `ExpXml` blob — small, representative, saved as test fixtures.

Registry: extend the existing registry test to assert `figshare`,
`arrayexpress`, `physionet`, `sra` all appear in `available_adapters()`.

## 6. Documentation

- Update `commands/find-datasets.md` — the "Adapters cover …" line (currently
  ~line 73) and the limitations note — to list the four new sources and the
  PhysioNet/SRA access caveats.
- Mirror the adapter-list change into `codex-skills/science-find-datasets/SKILL.md`
  if it duplicates the list.

## 7. Validation

From `~/d/science`:

```bash
uv run pytest science/tests/test_datasets.py
uv run ruff check science/src/science_tool/datasets
```

## 8. Out of scope → Phase 2 (separate spec)

- Relevance scoring / ranking inside `search_all` (today it concatenates; the
  LLM ranks in the skill).
- Cross-source dedup (same DOI surfacing from Zenodo + Dryad + figshare).
- Richer result fields surfaced in the CLI `search` table (modality, organism,
  sample_count, access).
- Optional follow-on adapters: `osf`, and a generalized `biostudies` toggle.
